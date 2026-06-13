from __future__ import annotations

import re
from pathlib import Path


DART_API_BASE_PATH_RE = re.compile(r"\bconst\s+(?P<name>_[A-Za-z_]\w*)\s*=\s*['\"](?P<path>/[^'\"]*)['\"]")
DART_API_ROUTE_ENUM_RE = re.compile(r"\benum\s+ApiRoute\s*\{(?P<body>[\s\S]*?)^\s*;", re.MULTILINE)
DART_API_ROUTE_ENTRY_RE = re.compile(
    r"(?m)^\s*(?P<name>[A-Za-z_]\w*)\s*\(\s*['\"](?P<path>[^'\"]+)['\"]\s*(?:,\s*['\"](?P<legacy>[^'\"]+)['\"])?\s*\)"
)


def dart_api_route_map(root: Path) -> dict[tuple[str, str], str]:
    routes: dict[tuple[str, str], str] = {}
    for path in root.rglob("api_route*.dart"):
        if any(part in {"build", ".dart_tool"} for part in path.parts):
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        routes.update(_dart_api_route_map_from_source(source))
    return routes


def _dart_api_route_map_from_source(source: str) -> dict[tuple[str, str], str]:
    enum_match = DART_API_ROUTE_ENUM_RE.search(source)
    if not enum_match:
        return {}
    base_path = _dart_api_base_path(source)
    if not base_path:
        return {}
    routes: dict[tuple[str, str], str] = {}
    for match in DART_API_ROUTE_ENTRY_RE.finditer(enum_match.group("body")):
        name = match.group("name")
        route_path = match.group("path")
        legacy_path = match.group("legacy") or route_path
        routes[(name, "v1")] = f"{base_path}/v1/{legacy_path}"
        routes[(name, "v2")] = f"{base_path}/v2/{route_path}"
    return routes


def _dart_api_base_path(source: str) -> str | None:
    match = DART_API_BASE_PATH_RE.search(source)
    return match.group("path").rstrip("/") if match else None
