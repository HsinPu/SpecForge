from __future__ import annotations

import re
from dataclasses import replace
from urllib.parse import urlparse

from specforge.models import ApiCallFact, ApiLinkFact, ApiRouteFact


def build_api_links(
    api_calls: list[ApiCallFact],
    api_routes: list[ApiRouteFact],
) -> tuple[list[ApiLinkFact], list[ApiCallFact]]:
    links: list[ApiLinkFact] = []
    linked_calls: list[ApiCallFact] = []

    for call in api_calls:
        match = _best_match(call, api_routes)
        if match:
            route, match_type, confidence = match
            matched_route = f"{route.method} {route.path}"
            links.append(
                ApiLinkFact(
                    source=call.path,
                    endpoint=call.endpoint,
                    method=call.method,
                    matched_route=route.path,
                    matched_method=route.method,
                    matched_framework=route.framework,
                    match_type=match_type,
                    confidence=confidence,
                    evidence=[call.evidence, route.evidence],
                )
            )
            linked_calls.append(replace(call, matched_route=matched_route))
        else:
            links.append(
                ApiLinkFact(
                    source=call.path,
                    endpoint=call.endpoint,
                    method=call.method,
                    matched_route=None,
                    matched_method=None,
                    matched_framework=None,
                    match_type="unmatched",
                    confidence="low",
                    evidence=[call.evidence],
                )
            )
            linked_calls.append(call)

    return links, linked_calls


def _best_match(
    call: ApiCallFact,
    routes: list[ApiRouteFact],
) -> tuple[ApiRouteFact, str, str] | None:
    endpoint = _normalize_path(call.endpoint)
    if not endpoint:
        return None

    exact_matches = [route for route in routes if _normalize_path(route.path) == endpoint]
    if exact_matches:
        return _best_method_match(call, exact_matches, "exact")

    param_matches = [route for route in routes if _route_regex(route.path).match(endpoint)]
    if param_matches:
        return _best_method_match(call, param_matches, "param")

    return None


def _best_method_match(
    call: ApiCallFact,
    routes: list[ApiRouteFact],
    match_type: str,
) -> tuple[ApiRouteFact, str, str]:
    call_method = call.method.upper() if call.method else None
    for route in routes:
        route_method = route.method.upper()
        if route_method in {"ANY", "ALL"} or call_method == route_method:
            confidence = "high" if match_type == "exact" else "medium"
            return route, match_type, confidence
    if call_method is None:
        confidence = "medium" if match_type == "exact" else "low"
        return routes[0], match_type, confidence
    return routes[0], "method-mismatch", "low"


def _normalize_path(value: str) -> str:
    stripped = value.strip().strip("'\"`")
    if not stripped:
        return ""
    if stripped.startswith(("http://", "https://")):
        parsed = urlparse(stripped)
        stripped = parsed.path or "/"
    stripped = stripped.split("?", 1)[0].split("#", 1)[0]
    if not stripped.startswith("/"):
        stripped = "/" + stripped
    if len(stripped) > 1:
        stripped = stripped.rstrip("/")
    return stripped


def _route_regex(path: str) -> re.Pattern[str]:
    normalized = _normalize_path(path)
    parts = normalized.strip("/").split("/") if normalized.strip("/") else []
    pattern_parts: list[str] = []
    for part in parts:
        if (
            re.fullmatch(r":\w+", part)
            or re.fullmatch(r"\{[^/{}]+\}", part)
            or re.fullmatch(r"<[^/<>]+>", part)
            or re.fullmatch(r"\[[^/\[\]]+\]", part)
        ):
            pattern_parts.append(r"[^/]+")
        elif part == "*":
            pattern_parts.append(r".+")
        else:
            pattern_parts.append(re.escape(part))
    pattern = "^/" + "/".join(pattern_parts) + "$"
    if not pattern_parts:
        pattern = "^/$"
    return re.compile(pattern)
