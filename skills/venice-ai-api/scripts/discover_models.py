#!/usr/bin/env python3
"""Inspect Venice's live model catalog without making inference calls.

The script uses only Python's standard library. By default it reads the API key
from VENICE_API_KEY and calls /api/v1/models. Use --catalog-file to inspect a
saved response without network access.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

DEFAULT_BASE_URL = "https://api.venice.ai/api/v1"
DEFAULT_TIMEOUT_SECONDS = 30.0


class CatalogError(RuntimeError):
    """Raised when the catalog cannot be fetched or decoded."""


@dataclass(frozen=True)
class CapabilityFilter:
    key: str
    expected: Any = True


def parse_scalar(value: str) -> Any:
    """Parse a command-line scalar while keeping unknown values as strings."""
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def parse_capability(value: str) -> CapabilityFilter:
    """Parse KEY or KEY=VALUE capability filters."""
    if "=" not in value:
        return CapabilityFilter(value, True)
    key, expected = value.split("=", 1)
    if not key:
        raise argparse.ArgumentTypeError("capability key cannot be empty")
    return CapabilityFilter(key, parse_scalar(expected))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch and filter Venice's model catalog. This performs discovery "
            "only; it never calls a paid inference endpoint."
        )
    )
    parser.add_argument(
        "--type",
        default="text",
        dest="model_type",
        help=(
            "Catalog type, for example text, image, inpaint, upscale, "
            "video, music, tts, asr, embedding, or all (default: text)."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Venice API base URL (default: {DEFAULT_BASE_URL}).",
    )
    parser.add_argument(
        "--api-key-env",
        default="VENICE_API_KEY",
        help="Environment variable containing the Bearer key (default: VENICE_API_KEY).",
    )
    parser.add_argument(
        "--catalog-file",
        type=Path,
        help="Read a saved /models JSON response instead of calling Venice.",
    )
    parser.add_argument(
        "--capability",
        action="append",
        default=[],
        type=parse_capability,
        metavar="KEY[=VALUE]",
        help=(
            "Require a capability/metadata value. May be repeated. Keys are "
            "looked up in model_spec.capabilities, model_spec.constraints, then "
            "model_spec. Example: --capability supportsFunctionCalling."
        ),
    )
    parser.add_argument(
        "--privacy",
        help="Require an exact model_spec.privacy value, such as private or anonymized.",
    )
    parser.add_argument(
        "--minimum-context",
        type=int,
        default=0,
        help="Require at least this many availableContextTokens (default: 0).",
    )
    parser.add_argument(
        "--search",
        help="Case-insensitive substring match against ID, name, and description.",
    )
    parser.add_argument(
        "--include-offline",
        action="store_true",
        help="Include rows marked offline.",
    )
    parser.add_argument(
        "--include-beta",
        action="store_true",
        help="Include rows marked beta/betaModel.",
    )
    parser.add_argument(
        "--exclude-deprecated",
        action="store_true",
        help="Hide rows with a model_spec.deprecation object.",
    )
    parser.add_argument(
        "--show-traits",
        action="store_true",
        help="Also fetch and print /models/traits for the selected type.",
    )
    parser.add_argument(
        "--show-compatibility",
        action="store_true",
        help="Also fetch and print /models/compatibility_mapping.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="In JSON mode, retain complete model rows instead of compact summaries.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON rather than a table.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum models to print after filtering; 0 means all.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"HTTP timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS:g}).",
    )
    return parser


def get_api_key(env_name: str) -> str:
    key = os.environ.get(env_name)
    if not key:
        raise CatalogError(
            f"{env_name} is not set. Export a Venice Bearer key or use --catalog-file."
        )
    return key


def request_json(
    base_url: str,
    path: str,
    *,
    params: Optional[Mapping[str, str]],
    api_key: str,
    timeout: float,
) -> Any:
    query = urllib.parse.urlencode(params or {})
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    if query:
        url = f"{url}?{query}"

    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "venice-ai-api-skill/discover-models",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:2000]
        raise CatalogError(f"Venice returned HTTP {exc.code} for {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise CatalogError(f"Could not reach {url}: {exc.reason}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        preview = raw.decode("utf-8", errors="replace")[:500]
        raise CatalogError(f"Venice returned invalid JSON for {url}: {preview}") from exc


def read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CatalogError(f"Could not read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise CatalogError(f"{path} does not contain valid JSON: {exc}") from exc


def extract_model_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict) and isinstance(payload.get("data"), list):
        rows = payload["data"]
    else:
        raise CatalogError("Expected /models response with a data array.")

    return [row for row in rows if isinstance(row, dict)]


def extract_mapping(payload: Any, label: str) -> dict[str, str]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise CatalogError(f"Expected {label} response with a data object.")
    return {
        str(key): str(value)
        for key, value in payload["data"].items()
        if isinstance(key, str) and isinstance(value, str)
    }


def lookup_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def lookup_model_value(spec: Mapping[str, Any], key: str) -> Any:
    """Look up a filter key across common model_spec containers."""
    if "." in key:
        return lookup_path(spec, key)

    capabilities = spec.get("capabilities")
    if isinstance(capabilities, Mapping) and key in capabilities:
        return capabilities[key]

    constraints = spec.get("constraints")
    if isinstance(constraints, Mapping) and key in constraints:
        return constraints[key]

    return spec.get(key)


def is_beta(spec: Mapping[str, Any]) -> bool:
    return spec.get("beta") is True or spec.get("betaModel") is True


def deprecation_date(spec: Mapping[str, Any]) -> Optional[str]:
    value = spec.get("deprecation")
    if isinstance(value, Mapping):
        date = value.get("date")
        return str(date) if date is not None else "scheduled"
    return None


def context_tokens(spec: Mapping[str, Any]) -> int:
    value = spec.get("availableContextTokens")
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    return 0


def matches_model(row: Mapping[str, Any], args: argparse.Namespace) -> bool:
    spec_value = row.get("model_spec")
    spec: Mapping[str, Any] = spec_value if isinstance(spec_value, Mapping) else {}

    if not args.include_offline and spec.get("offline") is True:
        return False
    if not args.include_beta and is_beta(spec):
        return False
    if args.exclude_deprecated and deprecation_date(spec):
        return False
    if args.privacy and spec.get("privacy") != args.privacy:
        return False
    if args.minimum_context and context_tokens(spec) < args.minimum_context:
        return False

    for requirement in args.capability:
        actual = lookup_model_value(spec, requirement.key)
        if actual != requirement.expected:
            return False

    if args.search:
        haystack = " ".join(
            str(part)
            for part in (
                row.get("id", ""),
                spec.get("name", ""),
                spec.get("description", ""),
            )
        ).lower()
        if args.search.lower() not in haystack:
            return False

    return True


def status_text(spec: Mapping[str, Any]) -> str:
    labels: list[str] = []
    if spec.get("offline") is True:
        labels.append("offline")
    if is_beta(spec):
        labels.append("beta")
    deprecated = deprecation_date(spec)
    if deprecated:
        labels.append(f"deprecates:{deprecated}")
    return ",".join(labels) or "active"


def compact_pricing(pricing: Any) -> str:
    if not isinstance(pricing, Mapping):
        return "-"

    parts: list[str] = []
    for key in (
        "input",
        "output",
        "generation",
        "inpaint",
        "per_second",
        "per_audio_second",
        "per_thousand_characters",
    ):
        value = pricing.get(key)
        if isinstance(value, Mapping):
            usd = value.get("usd")
            if usd is not None:
                parts.append(f"{key}=${usd}")
        elif value is not None:
            parts.append(f"{key}={value}")

    if pricing.get("quality"):
        parts.append("quality-priced")
    if pricing.get("resolutions"):
        parts.append("resolution-priced")
    if pricing.get("durations"):
        parts.append("duration-priced")
    if pricing.get("extended"):
        parts.append("extended-context")

    return ";".join(parts) or "complex"


def row_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    spec_value = row.get("model_spec")
    spec: Mapping[str, Any] = spec_value if isinstance(spec_value, Mapping) else {}
    capabilities = spec.get("capabilities")
    cap_map: Mapping[str, Any] = capabilities if isinstance(capabilities, Mapping) else {}

    enabled_capabilities = sorted(
        key for key, value in cap_map.items() if value is True
    )

    return {
        "id": row.get("id"),
        "type": row.get("type"),
        "name": spec.get("name"),
        "privacy": spec.get("privacy"),
        "status": status_text(spec),
        "availableContextTokens": spec.get("availableContextTokens"),
        "maxCompletionTokens": spec.get("maxCompletionTokens"),
        "traits": spec.get("traits", []),
        "capabilities": enabled_capabilities,
        "pricing": spec.get("pricing"),
    }


def truncate(value: Any, width: int) -> str:
    text = "-" if value in (None, "") else str(value)
    if len(text) <= width:
        return text
    return text[: max(width - 1, 0)] + "…"


def render_table(rows: Sequence[Mapping[str, Any]]) -> str:
    headers = ("ID", "TYPE", "PRIVACY", "CONTEXT", "STATUS", "TRAITS", "PRICING")
    widths = [38, 10, 12, 10, 28, 24, 34]

    table_rows: list[tuple[str, ...]] = []
    for row in rows:
        spec_value = row.get("model_spec")
        spec: Mapping[str, Any] = spec_value if isinstance(spec_value, Mapping) else {}
        traits = spec.get("traits")
        traits_text = ",".join(str(item) for item in traits) if isinstance(traits, list) else "-"
        table_rows.append(
            (
                truncate(row.get("id"), widths[0]),
                truncate(row.get("type"), widths[1]),
                truncate(spec.get("privacy"), widths[2]),
                truncate(context_tokens(spec) or "-", widths[3]),
                truncate(status_text(spec), widths[4]),
                truncate(traits_text, widths[5]),
                truncate(compact_pricing(spec.get("pricing")), widths[6]),
            )
        )

    def line(values: Iterable[str]) -> str:
        return "  ".join(value.ljust(width) for value, width in zip(values, widths))

    separator = "  ".join("-" * width for width in widths)
    output = [line(headers), separator]
    output.extend(line(row) for row in table_rows)
    return "\n".join(output)


def render_mapping(title: str, mapping: Mapping[str, str]) -> str:
    if not mapping:
        return f"\n{title}: (none)"
    width = max(len(key) for key in mapping)
    lines = [f"\n{title}:"]
    lines.extend(f"  {key.ljust(width)} -> {mapping[key]}" for key in sorted(mapping))
    return "\n".join(lines)


def load_remote_catalog(args: argparse.Namespace) -> tuple[Any, str]:
    key = get_api_key(args.api_key_env)
    payload = request_json(
        args.base_url,
        "/models",
        params={"type": args.model_type},
        api_key=key,
        timeout=args.timeout,
    )
    return payload, key


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.minimum_context < 0:
        parser.error("--minimum-context cannot be negative")
    if args.limit < 0:
        parser.error("--limit cannot be negative")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    try:
        if args.catalog_file:
            catalog_payload = read_json_file(args.catalog_file)
            api_key: Optional[str] = None
        else:
            catalog_payload, api_key = load_remote_catalog(args)

        rows = [row for row in extract_model_rows(catalog_payload) if matches_model(row, args)]
        rows.sort(key=lambda row: (str(row.get("type", "")), str(row.get("id", ""))))
        if args.limit:
            rows = rows[: args.limit]

        traits: Optional[dict[str, str]] = None
        compatibility: Optional[dict[str, str]] = None

        if args.show_traits:
            if api_key is None:
                raise CatalogError("--show-traits requires live API access, not --catalog-file.")
            traits = extract_mapping(
                request_json(
                    args.base_url,
                    "/models/traits",
                    params={"type": args.model_type},
                    api_key=api_key,
                    timeout=args.timeout,
                ),
                "traits",
            )

        if args.show_compatibility:
            if api_key is None:
                raise CatalogError(
                    "--show-compatibility requires live API access, not --catalog-file."
                )
            compatibility = extract_mapping(
                request_json(
                    args.base_url,
                    "/models/compatibility_mapping",
                    params={"type": args.model_type},
                    api_key=api_key,
                    timeout=args.timeout,
                ),
                "compatibility mapping",
            )

        if args.json:
            output = {
                "type": args.model_type,
                "count": len(rows),
                "models": rows if args.raw else [row_summary(row) for row in rows],
            }
            if traits is not None:
                output["traits"] = traits
            if compatibility is not None:
                output["compatibility_mapping"] = compatibility
            json.dump(output, sys.stdout, indent=2, sort_keys=True)
            sys.stdout.write("\n")
        else:
            print(render_table(rows))
            print(f"\n{len(rows)} model(s) matched.")
            if traits is not None:
                print(render_mapping("Traits", traits))
            if compatibility is not None:
                print(render_mapping("Compatibility mappings", compatibility))

        return 0
    except CatalogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
