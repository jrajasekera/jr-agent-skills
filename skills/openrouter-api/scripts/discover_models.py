#!/usr/bin/env python3
"""Inspect OpenRouter model and provider metadata without third-party packages.

Examples:
    python scripts/discover_models.py --query coding --parameter tools
    python scripts/discover_models.py --output-modality embeddings --json
    python scripts/discover_models.py --output-modality all --limit 0
    python scripts/discover_models.py --model author/model-slug --json
    python scripts/discover_models.py --endpoints author/model-slug --json
    python scripts/discover_models.py --image-endpoints author/model-slug --json
    python scripts/discover_models.py --video-models --json

Environment variables:
    OPENROUTER_API_KEY   Optional for public discovery; required for user-specific data.
    OPENROUTER_BASE_URL  Defaults to https://openrouter.ai/api/v1.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
class DiscoveryError(RuntimeError):
    """An actionable discovery failure."""


def csv_values(values: Sequence[str] | None) -> list[str]:
    """Expand repeatable comma-separated CLI values, preserving order."""
    result: list[str] = []
    for value in values or []:
        for part in value.split(","):
            part = part.strip()
            if part and part not in result:
                result.append(part)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Browse OpenRouter models and inspect provider/media endpoints.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--model", metavar="ID", help="Fetch GET /model/{author}/{slug}.")
    mode.add_argument(
        "--endpoints",
        metavar="ID",
        help="Fetch GET /models/{author}/{slug}/endpoints.",
    )
    mode.add_argument(
        "--image-endpoints",
        metavar="ID",
        help="Fetch GET /images/models/{author}/{slug}/endpoints.",
    )
    mode.add_argument(
        "--video-models",
        action="store_true",
        help="Fetch the dedicated GET /videos/models catalog.",
    )

    parser.add_argument("--query", "-q", help="Free-text model search; also filtered locally.")
    parser.add_argument(
        "--input-modality",
        action="append",
        default=[],
        metavar="MODALITY",
        help="Require an input modality; repeat or comma-separate.",
    )
    parser.add_argument(
        "--output-modality",
        action="append",
        default=[],
        metavar="MODALITY",
        help="Require an output modality; repeat or comma-separate.",
    )
    parser.add_argument(
        "--parameter",
        action="append",
        default=[],
        metavar="NAME",
        help="Require a supported parameter; repeat or comma-separate.",
    )
    parser.add_argument("--category", help="Pass a server-side model category filter.")
    parser.add_argument("--sort", help="Pass the current server-side sort expression.")
    parser.add_argument(
        "--context",
        type=int,
        help="Pass the current server-side context-length filter/minimum.",
    )
    parser.add_argument(
        "--max-price",
        help="Pass the current server-side maximum-price expression unchanged.",
    )
    parser.add_argument(
        "--zdr",
        help="Pass the current server-side ZDR filter unchanged (for example true).",
    )
    parser.add_argument("--region", help="Pass a server-side region filter unchanged.")
    parser.add_argument(
        "--page-size",
        type=int,
        default=1000,
        help="Requested page size for /models (default: 1000).",
    )
    parser.add_argument(
        "--all-pages",
        action="store_true",
        help="Follow server-provided next links/cursors for /models.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum rows printed in table mode; 0 means all (default: 50).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON instead of the compact table/pretty object.",
    )
    parser.add_argument(
        "--from-file",
        type=Path,
        metavar="JSON",
        help="Read a saved response instead of making a network request.",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OPENROUTER_BASE_URL", DEFAULT_BASE_URL),
        help="API base URL (default: OPENROUTER_BASE_URL or OpenRouter production).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds (default: 30).",
    )
    return parser


def api_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "openrouter-api-skill/discover-models",
    }
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def load_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DiscoveryError(f"File not found: {path}") from exc
    except OSError as exc:
        raise DiscoveryError(f"Could not read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise DiscoveryError(f"Invalid JSON in {path}: {exc}") from exc


def fetch_json(url: str, timeout: float) -> Any:
    request = Request(url, headers=api_headers(), method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        detail = body[:2000].strip()
        raise DiscoveryError(
            f"OpenRouter returned HTTP {exc.code} for {url}"
            + (f": {detail}" if detail else "")
        ) from exc
    except URLError as exc:
        raise DiscoveryError(f"Could not reach {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise DiscoveryError(f"Timed out fetching {url}") from exc

    try:
        return json.loads(raw.decode(charset))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        preview = raw[:500].decode("utf-8", errors="replace")
        raise DiscoveryError(f"Expected JSON from {url}; received: {preview!r}") from exc


def encode_model_id(model_id: str) -> str:
    model_id = model_id.strip().lstrip("/")
    if not model_id or "/" not in model_id:
        raise DiscoveryError(
            "Model IDs must be full OpenRouter slugs such as 'author/model-slug'."
        )
    return quote(model_id, safe="/:~@._-")


def build_url(args: argparse.Namespace) -> str:
    base = args.base_url.rstrip("/")
    if args.model:
        return f"{base}/model/{encode_model_id(args.model)}"
    if args.endpoints:
        return f"{base}/models/{encode_model_id(args.endpoints)}/endpoints"
    if args.image_endpoints:
        return f"{base}/images/models/{encode_model_id(args.image_endpoints)}/endpoints"
    if args.video_models:
        return f"{base}/videos/models"

    params: list[tuple[str, str]] = []
    if args.query:
        params.append(("q", args.query))
    input_modalities = csv_values(args.input_modality)
    output_modalities = csv_values(args.output_modality)
    parameters = csv_values(args.parameter)
    if input_modalities:
        params.append(("input_modalities", ",".join(input_modalities)))
    if output_modalities:
        params.append(("output_modalities", ",".join(output_modalities)))
    if parameters:
        params.append(("supported_parameters", ",".join(parameters)))
    if args.category:
        params.append(("category", args.category))
    if args.sort:
        params.append(("sort", args.sort))
    if args.context is not None:
        params.append(("context", str(args.context)))
    if args.max_price:
        params.append(("max_price", args.max_price))
    if args.zdr:
        params.append(("zdr", args.zdr))
    if args.region:
        params.append(("region", args.region))
    if args.page_size <= 0:
        raise DiscoveryError("--page-size must be positive.")
    params.append(("limit", str(min(args.page_size, 1000))))
    return f"{base}/models?{urlencode(params)}"


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def model_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    # Dedicated catalogs occasionally use a named array. Keep this permissive.
    for key in ("models", "items", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def next_page_url(payload: Any, current_url: str) -> str | None:
    if not isinstance(payload, dict):
        return None

    links = payload.get("links")
    if isinstance(links, dict) and isinstance(links.get("next"), str):
        candidate = links["next"].strip()
        return urljoin(current_url, candidate) if candidate else None

    for key in ("next", "next_url"):
        candidate = payload.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return urljoin(current_url, candidate.strip())

    # Cursor-style pagination. Only follow it when the response explicitly says more.
    has_more = payload.get("has_more")
    cursor = payload.get("cursor") or payload.get("next_cursor")
    if has_more is True and isinstance(cursor, str) and cursor:
        parsed = urlparse(current_url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["cursor"] = cursor
        return urlunparse(parsed._replace(query=urlencode(query)))

    meta = payload.get("meta")
    if isinstance(meta, dict):
        cursor = meta.get("next_cursor") or meta.get("cursor")
        if isinstance(cursor, str) and cursor:
            parsed = urlparse(current_url)
            query = dict(parse_qsl(parsed.query, keep_blank_values=True))
            query["cursor"] = cursor
            return urlunparse(parsed._replace(query=urlencode(query)))

    return None


def fetch_model_pages(first_url: str, timeout: float, all_pages: bool) -> Any:
    payload = fetch_json(first_url, timeout)
    if not all_pages:
        return payload

    combined = model_rows(payload)
    seen_urls = {first_url}
    current_url = first_url
    current_payload = payload

    while True:
        next_url = next_page_url(current_payload, current_url)
        if not next_url or next_url in seen_urls:
            break
        seen_urls.add(next_url)
        current_payload = fetch_json(next_url, timeout)
        combined.extend(model_rows(current_payload))
        current_url = next_url

    if isinstance(payload, dict):
        result = dict(payload)
        result["data"] = combined
        result["_pages_fetched"] = len(seen_urls)
        return result
    return {"data": combined, "_pages_fetched": len(seen_urls)}


def lower_strings(value: Any) -> set[str]:
    return {str(item).lower() for item in as_list(value)}


def required_output_modalities(values: Sequence[str]) -> list[str]:
    """Treat the API's special `all` value as disabling modality filtering."""
    normalized = [value for value in values if value.lower() != "all"]
    return [] if len(normalized) != len(values) else normalized


def architecture(model: Mapping[str, Any]) -> Mapping[str, Any]:
    value = model.get("architecture")
    return value if isinstance(value, Mapping) else {}


def matches_model(
    model: Mapping[str, Any],
    query: str | None,
    input_modalities: Sequence[str],
    output_modalities: Sequence[str],
    parameters: Sequence[str],
) -> bool:
    if query:
        haystack = " ".join(
            str(model.get(key, ""))
            for key in ("id", "canonical_slug", "name", "description", "hugging_face_id")
        ).lower()
        if query.lower() not in haystack:
            return False

    arch = architecture(model)
    inputs = lower_strings(arch.get("input_modalities"))
    outputs = lower_strings(arch.get("output_modalities"))
    supported = lower_strings(model.get("supported_parameters"))

    if not {item.lower() for item in input_modalities}.issubset(inputs):
        return False
    required_outputs = {
        item.lower() for item in required_output_modalities(output_modalities)
    }
    if not required_outputs.issubset(outputs):
        return False
    if not {item.lower() for item in parameters}.issubset(supported):
        return False
    return True


def filtered_payload(payload: Any, args: argparse.Namespace) -> tuple[Any, list[dict[str, Any]]]:
    rows = model_rows(payload)
    filtered = [
        model
        for model in rows
        if matches_model(
            model,
            args.query,
            csv_values(args.input_modality),
            csv_values(args.output_modality),
            csv_values(args.parameter),
        )
    ]
    if isinstance(payload, dict):
        result = dict(payload)
        result["data"] = filtered
        result["_local_match_count"] = len(filtered)
    else:
        result = filtered
    return result, filtered


def decimal_per_million(value: Any) -> str:
    if value is None or value == "":
        return "-"
    try:
        amount = Decimal(str(value)) * Decimal(1_000_000)
    except (InvalidOperation, ValueError):
        return str(value)
    normalized = f"{amount:.6f}".rstrip("0").rstrip(".")
    return f"${normalized}/M"


def compact_modalities(model: Mapping[str, Any]) -> str:
    arch = architecture(model)
    inputs = ",".join(str(v) for v in as_list(arch.get("input_modalities"))) or "-"
    outputs = ",".join(str(v) for v in as_list(arch.get("output_modalities"))) or "-"
    return f"{inputs}->{outputs}"


def context_value(model: Mapping[str, Any]) -> str:
    value = model.get("context_length")
    if value is None:
        provider = model.get("top_provider")
        if isinstance(provider, Mapping):
            value = provider.get("context_length")
    if isinstance(value, int):
        return f"{value:,}"
    return str(value) if value not in (None, "") else "-"


def expiration_value(model: Mapping[str, Any]) -> str:
    value = model.get("expiration_date")
    return str(value) if value else "-"


def pricing(model: Mapping[str, Any], key: str) -> Any:
    value = model.get("pricing")
    return value.get(key) if isinstance(value, Mapping) else None


def pricing_override_count(model: Mapping[str, Any]) -> str:
    value = model.get("pricing")
    if not isinstance(value, Mapping):
        return "-"
    overrides = value.get("overrides")
    return str(len(overrides)) if isinstance(overrides, list) and overrides else "-"


def print_table(rows: Sequence[Mapping[str, Any]], display_limit: int) -> None:
    selected = list(rows) if display_limit == 0 else list(rows[: max(display_limit, 0)])
    if not selected:
        print("No models matched.")
        return

    table_rows = [
        [
            str(model.get("id", "-")),
            context_value(model),
            compact_modalities(model),
            decimal_per_million(pricing(model, "prompt")),
            decimal_per_million(pricing(model, "completion")),
            pricing_override_count(model),
            expiration_value(model),
        ]
        for model in selected
    ]
    headers = ["MODEL", "CONTEXT", "MODALITIES", "INPUT", "OUTPUT", "OVERRIDES", "EXPIRES"]
    widths = [
        min(max(len(headers[i]), *(len(row[i]) for row in table_rows)), 70)
        for i in range(len(headers))
    ]

    def render(row: Sequence[str]) -> str:
        cells: list[str] = []
        for index, value in enumerate(row):
            clipped = value
            if len(clipped) > widths[index]:
                clipped = clipped[: max(0, widths[index] - 1)] + "…"
            cells.append(clipped.ljust(widths[index]))
        return "  ".join(cells).rstrip()

    print(render(headers))
    print(render(["-" * width for width in widths]))
    for row in table_rows:
        print(render(row))

    omitted = len(rows) - len(selected)
    if omitted > 0:
        print(f"\n{omitted} additional matching model(s) omitted; use --limit 0 or --json.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.limit < 0:
            raise DiscoveryError("--limit cannot be negative.")

        output_modalities = csv_values(args.output_modality)
        if any(value.lower() == "all" for value in output_modalities) and len(output_modalities) > 1:
            raise DiscoveryError("Use --output-modality all by itself.")

        if args.from_file:
            payload = load_json_file(args.from_file)
        else:
            url = build_url(args)
            if not any((args.model, args.endpoints, args.image_endpoints, args.video_models)):
                payload = fetch_model_pages(url, args.timeout, args.all_pages)
            else:
                payload = fetch_json(url, args.timeout)

        list_mode = not any(
            (args.model, args.endpoints, args.image_endpoints, args.video_models)
        )
        if list_mode:
            output, rows = filtered_payload(payload, args)
            if args.json:
                print(json.dumps(output, indent=2, ensure_ascii=False, sort_keys=False))
            else:
                print_table(rows, args.limit)
        else:
            # Endpoint/model details are heterogeneous; preserve their exact live shape.
            print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False))
        return 0
    except DiscoveryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
