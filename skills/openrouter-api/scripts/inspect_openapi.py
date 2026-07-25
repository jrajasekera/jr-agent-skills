#!/usr/bin/env python3
"""Search and inspect OpenRouter's current OpenAPI specification.

Examples:
    python scripts/inspect_openapi.py --list
    python scripts/inspect_openapi.py --search responses
    python scripts/inspect_openapi.py --path /responses
    python scripts/inspect_openapi.py --operation POST /responses --resolve-refs
    python scripts/inspect_openapi.py --schema ResponsesRequest --resolve-refs

Environment variables:
    OPENROUTER_OPENAPI_URL  Defaults to https://openrouter.ai/openapi.json.
    OPENROUTER_API_KEY      Optional; sent only when set.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_OPENAPI_URL = "https://openrouter.ai/openapi.json"
HTTP_METHODS = ("get", "post", "put", "patch", "delete", "options", "head", "trace")


class SpecError(RuntimeError):
    """An actionable OpenAPI inspection failure."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect paths, operations, and schemas in OpenRouter's live OpenAPI.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--list", action="store_true", help="List operations (default).")
    mode.add_argument(
        "--search",
        action="append",
        metavar="TERM",
        help="Search operations; repeat for an AND search.",
    )
    mode.add_argument("--path", metavar="PATH", help="Print one complete path item.")
    mode.add_argument(
        "--operation",
        nargs=2,
        metavar=("METHOD", "PATH"),
        help="Print one operation object.",
    )
    mode.add_argument("--schema", metavar="NAME", help="Print one component schema.")
    mode.add_argument(
        "--schemas",
        action="store_true",
        help="List component schema names.",
    )
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        metavar="TAG",
        help="Limit list/search results to operations with this tag; repeatable.",
    )
    parser.add_argument(
        "--resolve-refs",
        action="store_true",
        help="Inline local $refs in printed path/operation/schema objects.",
    )
    parser.add_argument(
        "--max-ref-depth",
        type=int,
        default=6,
        help="Maximum local $ref expansion depth (default: 6).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON for list/search/schema-name output.",
    )
    parser.add_argument(
        "--from-file",
        type=Path,
        metavar="JSON",
        help="Read a saved OpenAPI JSON file instead of the network.",
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("OPENROUTER_OPENAPI_URL", DEFAULT_OPENAPI_URL),
        help="OpenAPI URL (default: OPENROUTER_OPENAPI_URL or production).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=45.0,
        help="HTTP timeout in seconds (default: 45).",
    )
    return parser


def load_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SpecError(f"File not found: {path}") from exc
    except OSError as exc:
        raise SpecError(f"Could not read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SpecError(f"Invalid JSON in {path}: {exc}") from exc


def fetch_spec(url: str, timeout: float) -> Any:
    headers = {
        "Accept": "application/json",
        "User-Agent": "openrouter-api-skill/inspect-openapi",
    }
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SpecError(
            f"OpenAPI request returned HTTP {exc.code}: {body[:2000].strip()}"
        ) from exc
    except URLError as exc:
        raise SpecError(f"Could not fetch {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise SpecError(f"Timed out fetching {url}") from exc

    try:
        return json.loads(raw.decode(charset))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        preview = raw[:500].decode("utf-8", errors="replace")
        raise SpecError(f"Expected OpenAPI JSON; received: {preview!r}") from exc


def validate_spec(spec: Any) -> Mapping[str, Any]:
    if not isinstance(spec, Mapping):
        raise SpecError("OpenAPI root must be a JSON object.")
    if not isinstance(spec.get("paths"), Mapping):
        raise SpecError("OpenAPI document has no object-valued 'paths'.")
    return spec


def operations(spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    paths = spec.get("paths")
    assert isinstance(paths, Mapping)
    for path in sorted(paths):
        path_item = paths[path]
        if not isinstance(path_item, Mapping):
            continue
        for method in HTTP_METHODS:
            operation = path_item.get(method)
            if not isinstance(operation, Mapping):
                continue
            result.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "operation_id": operation.get("operationId"),
                    "summary": operation.get("summary"),
                    "tags": operation.get("tags", []),
                    "deprecated": bool(operation.get("deprecated", False)),
                }
            )
    return result


def operation_search_text(row: Mapping[str, Any], operation: Mapping[str, Any]) -> str:
    values = [
        row.get("method"),
        row.get("path"),
        row.get("operation_id"),
        row.get("summary"),
        operation.get("description"),
        operation.get("tags"),
    ]
    return json.dumps(values, ensure_ascii=False, default=str).lower()


def operation_object(spec: Mapping[str, Any], method: str, path: str) -> Mapping[str, Any]:
    paths = spec.get("paths")
    assert isinstance(paths, Mapping)
    path_item = paths.get(path)
    if not isinstance(path_item, Mapping):
        raise SpecError(f"Path not found: {path}")
    operation = path_item.get(method.lower())
    if not isinstance(operation, Mapping):
        available = sorted(key.upper() for key in path_item if key.lower() in HTTP_METHODS)
        suffix = f"; available methods: {', '.join(available)}" if available else ""
        raise SpecError(f"Operation not found: {method.upper()} {path}{suffix}")
    return operation


def filter_rows(
    spec: Mapping[str, Any],
    rows: Sequence[dict[str, Any]],
    terms: Sequence[str],
    tags: Sequence[str],
) -> list[dict[str, Any]]:
    normalized_terms = [term.lower() for term in terms if term.strip()]
    normalized_tags = {tag.lower() for tag in tags if tag.strip()}
    result: list[dict[str, Any]] = []
    for row in rows:
        operation = operation_object(spec, str(row["method"]), str(row["path"]))
        row_tags = {str(tag).lower() for tag in operation.get("tags", [])}
        if normalized_tags and not normalized_tags.issubset(row_tags):
            continue
        text = operation_search_text(row, operation)
        if all(term in text for term in normalized_terms):
            result.append(row)
    return result


def unescape_pointer_token(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def resolve_pointer(document: Mapping[str, Any], ref: str) -> Any:
    if not ref.startswith("#/"):
        raise SpecError(f"Only local OpenAPI refs can be expanded: {ref}")
    current: Any = document
    for token in ref[2:].split("/"):
        token = unescape_pointer_token(token)
        if not isinstance(current, Mapping) or token not in current:
            raise SpecError(f"Broken local OpenAPI ref: {ref}")
        current = current[token]
    return current


def resolve_refs(
    value: Any,
    document: Mapping[str, Any],
    max_depth: int,
    depth: int = 0,
    stack: tuple[str, ...] = (),
) -> Any:
    if depth > max_depth:
        return value
    if isinstance(value, list):
        return [resolve_refs(item, document, max_depth, depth + 1, stack) for item in value]
    if not isinstance(value, Mapping):
        return value

    ref = value.get("$ref")
    if isinstance(ref, str):
        if ref in stack:
            return {"$ref": ref, "x-openrouter-inspector-note": "recursive reference"}
        target = copy.deepcopy(resolve_pointer(document, ref))
        resolved = resolve_refs(target, document, max_depth, depth + 1, stack + (ref,))
        if isinstance(resolved, Mapping):
            merged = dict(resolved)
            for key, item in value.items():
                if key != "$ref":
                    merged[key] = resolve_refs(item, document, max_depth, depth + 1, stack)
            return merged
        return resolved

    return {
        key: resolve_refs(item, document, max_depth, depth + 1, stack)
        for key, item in value.items()
    }


def schema_names(spec: Mapping[str, Any]) -> list[str]:
    components = spec.get("components")
    if not isinstance(components, Mapping):
        return []
    schemas = components.get("schemas")
    if not isinstance(schemas, Mapping):
        return []
    return sorted(str(name) for name in schemas)


def get_schema(spec: Mapping[str, Any], name: str) -> Any:
    components = spec.get("components")
    schemas = components.get("schemas") if isinstance(components, Mapping) else None
    if not isinstance(schemas, Mapping) or name not in schemas:
        candidates = [candidate for candidate in schema_names(spec) if name.lower() in candidate.lower()]
        hint = f" Similar names: {', '.join(candidates[:10])}" if candidates else ""
        raise SpecError(f"Schema not found: {name}.{hint}")
    return schemas[name]


def print_operation_table(rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        print("No operations matched.")
        return
    headers = ["METHOD", "PATH", "OPERATION ID", "SUMMARY", "FLAGS"]
    table: list[list[str]] = []
    for row in rows:
        flags = "deprecated" if row.get("deprecated") else ""
        table.append(
            [
                str(row.get("method") or ""),
                str(row.get("path") or ""),
                str(row.get("operation_id") or ""),
                str(row.get("summary") or ""),
                flags,
            ]
        )
    caps = [8, 58, 48, 80, 12]
    widths = [
        min(max(len(headers[i]), *(len(row[i]) for row in table)), caps[i])
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
    for row in table:
        print(render(row))


def print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=False))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.max_ref_depth < 0:
            raise SpecError("--max-ref-depth cannot be negative.")
        raw = load_file(args.from_file) if args.from_file else fetch_spec(args.url, args.timeout)
        spec = validate_spec(raw)

        if args.path:
            path_item = spec["paths"].get(args.path)  # type: ignore[index]
            if not isinstance(path_item, Mapping):
                raise SpecError(f"Path not found: {args.path}")
            output = path_item
            if args.resolve_refs:
                output = resolve_refs(output, spec, args.max_ref_depth)
            print_json(output)
            return 0

        if args.operation:
            method, path = args.operation
            output = operation_object(spec, method, path)
            if args.resolve_refs:
                output = resolve_refs(output, spec, args.max_ref_depth)
            print_json(output)
            return 0

        if args.schema:
            output = get_schema(spec, args.schema)
            if args.resolve_refs:
                output = resolve_refs(output, spec, args.max_ref_depth)
            print_json(output)
            return 0

        if args.schemas:
            names = schema_names(spec)
            if args.json:
                print_json(names)
            else:
                print("\n".join(names))
            return 0

        rows = operations(spec)
        terms = args.search or []
        rows = filter_rows(spec, rows, terms, args.tag)
        if args.json:
            print_json(rows)
        else:
            print_operation_table(rows)
        return 0
    except SpecError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
