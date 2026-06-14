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
    named_route_matches = _named_route_matches(call, routes)
    if named_route_matches:
        return _best_method_match(call, named_route_matches, "named-route")

    phoenix_helper_matches = _phoenix_helper_matches(call, routes)
    if phoenix_helper_matches:
        return _best_method_match(call, phoenix_helper_matches, "phoenix-helper")

    endpoint = _normalize_path(call.endpoint)
    if not endpoint:
        return None

    exact_matches = [route for route in routes if _normalize_path(route.path) == endpoint]
    if exact_matches:
        return _best_method_match(call, exact_matches, "exact")

    aspnet_case_matches = [
        route
        for route in routes
        if route.framework == "aspnetcore" and _normalize_path(route.path).lower() == endpoint.lower()
    ]
    if aspnet_case_matches:
        return _best_method_match(call, aspnet_case_matches, "case-insensitive")

    endpoint_without_format = _without_format_suffix(endpoint)
    format_suffix_matches = [
        route
        for route in routes
        if _without_format_suffix(_normalize_path(route.path)) == endpoint_without_format
    ]
    if format_suffix_matches:
        return _best_method_match(call, format_suffix_matches, "format-suffix")

    param_matches = _param_route_matches(routes, endpoint)
    if param_matches:
        param_match = _best_method_match(call, param_matches, "param")
        if param_match:
            return param_match

    rails_anchored_param_matches = _rails_anchored_text_param_route_matches(routes, endpoint)
    if rails_anchored_param_matches:
        return _best_method_match(call, rails_anchored_param_matches, "rails-anchored-param")

    rails_resource_text_id_matches = _rails_resource_text_id_param_route_matches(routes, endpoint)
    if rails_resource_text_id_matches:
        return _best_method_match(call, rails_resource_text_id_matches, "rails-resource-text-id-param")

    param_format_suffix_matches = [
        route
        for route in routes
        if _route_has_static_overlap(route.path, endpoint_without_format)
        and _route_matches(route.path, endpoint_without_format)
    ]
    if param_format_suffix_matches:
        return _best_method_match(call, param_format_suffix_matches, "param-format-suffix")

    rails_anchored_param_format_suffix_matches = _rails_anchored_text_param_route_matches(
        routes,
        endpoint_without_format,
    )
    if rails_anchored_param_format_suffix_matches:
        return _best_method_match(
            call,
            rails_anchored_param_format_suffix_matches,
            "rails-anchored-param-format-suffix",
        )

    rails_resource_text_id_format_suffix_matches = _rails_resource_text_id_param_route_matches(
        routes,
        endpoint_without_format,
    )
    if rails_resource_text_id_format_suffix_matches:
        return _best_method_match(
            call,
            rails_resource_text_id_format_suffix_matches,
            "rails-resource-text-id-param-format-suffix",
        )

    trpc_matches = _trpc_procedure_matches(call, endpoint, routes)
    if trpc_matches:
        return _best_method_match(call, trpc_matches, "trpc-procedure")

    return None


def _best_method_match(
    call: ApiCallFact,
    routes: list[ApiRouteFact],
    match_type: str,
) -> tuple[ApiRouteFact, str, str] | None:
    call_method = call.method.upper() if call.method else None
    for route in routes:
        route_method = route.method.upper()
        if route_method in {"ANY", "ALL"} or call_method == route_method:
            if match_type in {"exact", "named-route", "phoenix-helper"}:
                confidence = "high"
            elif match_type.startswith("rails-anchored-param") or match_type.startswith("rails-resource-text-id-param"):
                confidence = "low"
            else:
                confidence = "medium"
            return route, match_type, confidence
    for route in routes:
        route_method = route.method.upper()
        if call_method == "STREAM" and route_method == "GET":
            return route, "stream-get", "medium"
    if call_method is None:
        confidence = "medium" if match_type == "exact" else "low"
        return routes[0], match_type, confidence
    if match_type != "exact":
        return None
    return routes[0], "method-mismatch", "low"


def _named_route_matches(call: ApiCallFact, routes: list[ApiRouteFact]) -> list[ApiRouteFact]:
    endpoint = call.endpoint.strip().strip("'\"`")
    if not endpoint.startswith("route:"):
        return []
    route_name = endpoint.removeprefix("route:").strip()
    if not route_name:
        return []
    return [
        route
        for route in routes
        if route.framework == "laravel" and _laravel_route_name(route) == route_name
    ]


def _laravel_route_name(route: ApiRouteFact) -> str | None:
    note = route.evidence.note or ""
    match = re.search(r"(?:^|;)laravel-route-name:([^;]+)", note)
    return match.group(1).strip() if match else None


def _phoenix_helper_matches(call: ApiCallFact, routes: list[ApiRouteFact]) -> list[ApiRouteFact]:
    endpoint = call.endpoint.strip().strip("'\"`")
    match = re.fullmatch(r"phoenix-helper:(?P<helper>[A-Za-z_]\w*(?:_path|_url)):(?P<action>[A-Za-z_]\w*)", endpoint)
    if not match:
        return []
    controller = _phoenix_controller_from_helper(match.group("helper"))
    action = match.group("action")
    handler_matches = [
        route
        for route in routes
        if route.framework == "phoenix" and _phoenix_route_handler_matches(route.handler, controller, action)
    ]
    if not handler_matches:
        return []
    helper_paths = {route.path for route in handler_matches}
    same_path_matches = [
        route
        for route in routes
        if route.framework == "phoenix" and route.path in helper_paths
    ]
    return _dedupe_routes([*handler_matches, *same_path_matches])


def _phoenix_route_handler_matches(handler: str | None, controller: str, action: str) -> bool:
    if not handler:
        return False
    expected = f"{controller}:{action}"
    return handler == expected or handler.endswith(f".{expected}")


def _dedupe_routes(routes: list[ApiRouteFact]) -> list[ApiRouteFact]:
    seen: set[tuple[str, str, str | None, str]] = set()
    result: list[ApiRouteFact] = []
    for route in routes:
        key = (route.method, route.path, route.handler, route.framework)
        if key in seen:
            continue
        seen.add(key)
        result.append(route)
    return result


def _phoenix_controller_from_helper(helper: str) -> str:
    stem = re.sub(r"_(?:path|url)$", "", helper)
    word_overrides = {
        "api": "API",
        "sso": "SSO",
        "oauth": "OAuth",
    }
    return "".join(word_overrides.get(part, part.capitalize()) for part in stem.split("_") if part) + "Controller"


def _normalize_path(value: str) -> str:
    stripped = value.strip().strip("'\"`")
    if not stripped:
        return ""
    if stripped.startswith(("ipc#", "tauri#", "socket.io#", "websocket#", "kafka#", "rabbitmq#", "bullmq#", "redis#", "/graphql#")):
        return stripped
    if stripped.startswith(("http://", "https://")):
        parsed = urlparse(stripped)
        stripped = parsed.path or "/"
    stripped = stripped.split("?", 1)[0].split("#", 1)[0]
    if not stripped.startswith("/"):
        stripped = "/" + stripped
    if len(stripped) > 1:
        stripped = stripped.rstrip("/")
    return stripped


def _without_format_suffix(path: str) -> str:
    for suffix in (".json",):
        if path.endswith(suffix) and len(path) > len(suffix):
            return path[: -len(suffix)]
    return path


def _trpc_procedure_matches(
    call: ApiCallFact,
    endpoint: str,
    routes: list[ApiRouteFact],
) -> list[ApiRouteFact]:
    if call.client != "trpc" or not endpoint.startswith("/trpc/"):
        return []
    procedure_name = endpoint.removeprefix("/trpc/").rsplit(".", 1)[-1]
    matches = [
        route
        for route in routes
        if route.framework == "trpc"
        and _normalize_path(route.path).startswith("/trpc/")
        and _normalize_path(route.path).removeprefix("/trpc/").rsplit(".", 1)[-1] == procedure_name
    ]
    return matches if len(matches) == 1 else []


def _route_matches(route_path: str, endpoint: str) -> bool:
    return any(
        _route_variant_matches(route_variant, endpoint)
        for route_variant in _route_path_variants(route_path)
    )


def _route_variant_matches(route_path: str, endpoint: str) -> bool:
    route = _normalize_path(route_path)
    endpoint = _normalize_path(endpoint)
    route_parts = route.strip("/").split("/") if route.strip("/") else []
    endpoint_parts = endpoint.strip("/").split("/") if endpoint.strip("/") else []
    if len(route_parts) != len(endpoint_parts):
        return False
    for route_part, endpoint_part in zip(route_parts, endpoint_parts):
        if _is_route_param(route_part):
            if not _is_endpoint_param_value(endpoint_part, route_part):
                return False
            continue
        if route_part == "*":
            return True
        if _endpoint_param_can_match_static_route_part(endpoint_part, route_part):
            continue
        if route_part != endpoint_part:
            return False
    return bool(route_parts)


def _route_has_static_overlap(route_path: str, endpoint: str) -> bool:
    return any(
        _route_variant_has_static_overlap(route_variant, endpoint)
        for route_variant in _route_path_variants(route_path)
    )


def _route_variant_has_static_overlap(route_path: str, endpoint: str) -> bool:
    route = _normalize_path(route_path)
    endpoint = _normalize_path(endpoint)
    route_parts = route.strip("/").split("/") if route.strip("/") else []
    endpoint_parts = endpoint.strip("/").split("/") if endpoint.strip("/") else []
    if len(route_parts) != len(endpoint_parts):
        return False
    for route_part, endpoint_part in zip(route_parts, endpoint_parts):
        if _is_route_param(route_part) or route_part == "*":
            continue
        if route_part == endpoint_part:
            return True
        if _endpoint_param_can_match_static_route_part(endpoint_part, route_part):
            return True
    return False


def _param_route_matches(routes: list[ApiRouteFact], endpoint: str) -> list[ApiRouteFact]:
    matches = [route for route in routes if _route_matches(route.path, endpoint) and _param_match_has_signal(route.path, endpoint)]
    return sorted(matches, key=lambda route: _route_match_specificity(route.path), reverse=True)


def _rails_anchored_text_param_route_matches(routes: list[ApiRouteFact], endpoint: str) -> list[ApiRouteFact]:
    matches = [
        route
        for route in routes
        if route.framework == "rails"
        and _route_has_static_overlap(route.path, endpoint)
        and _route_matches_with_anchored_text_id(route.path, endpoint)
    ]
    return sorted(matches, key=lambda route: _route_match_specificity(route.path), reverse=True)


def _rails_resource_text_id_param_route_matches(routes: list[ApiRouteFact], endpoint: str) -> list[ApiRouteFact]:
    matches = [
        route
        for route in routes
        if route.framework == "rails"
        and route.kind == "rails-resource-member-route"
        and _route_has_static_overlap(route.path, endpoint)
        and _route_matches_with_resource_text_id(route.path, endpoint)
    ]
    return sorted(matches, key=lambda route: _route_match_specificity(route.path), reverse=True)


def _route_matches_with_anchored_text_id(route_path: str, endpoint: str) -> bool:
    route = _normalize_path(route_path)
    endpoint = _normalize_path(endpoint)
    route_parts = route.strip("/").split("/") if route.strip("/") else []
    endpoint_parts = endpoint.strip("/").split("/") if endpoint.strip("/") else []
    if len(route_parts) != len(endpoint_parts):
        return False

    saw_text_id_param = False
    for index, (route_part, endpoint_part) in enumerate(zip(route_parts, endpoint_parts)):
        if _is_route_param(route_part):
            if _is_endpoint_param_value(endpoint_part, route_part):
                continue
            if (
                _route_param_name_looks_like_id(route_part)
                and re.fullmatch(r"[A-Za-z0-9._~-]+", endpoint_part)
                and _has_static_anchor_before(route_parts, endpoint_parts, index)
                and _has_static_anchor_after(route_parts, endpoint_parts, index)
            ):
                saw_text_id_param = True
                continue
            return False
        if route_part == "*":
            return True
        if _endpoint_param_can_match_static_route_part(endpoint_part, route_part):
            continue
        if route_part != endpoint_part:
            return False
    return saw_text_id_param and bool(route_parts)


def _route_matches_with_resource_text_id(route_path: str, endpoint: str) -> bool:
    route = _normalize_path(route_path)
    endpoint = _normalize_path(endpoint)
    route_parts = route.strip("/").split("/") if route.strip("/") else []
    endpoint_parts = endpoint.strip("/").split("/") if endpoint.strip("/") else []
    if len(route_parts) != len(endpoint_parts):
        return False

    saw_text_id_param = False
    for route_part, endpoint_part in zip(route_parts, endpoint_parts):
        if _is_route_param(route_part):
            if _is_endpoint_param_value(endpoint_part, route_part):
                continue
            if _route_param_name_looks_like_id(route_part) and re.fullmatch(r"[A-Za-z0-9._~-]+", endpoint_part):
                saw_text_id_param = True
                continue
            return False
        if route_part == "*":
            return True
        if _endpoint_param_can_match_static_route_part(endpoint_part, route_part):
            continue
        if route_part != endpoint_part:
            return False
    return saw_text_id_param and bool(route_parts)


def _has_static_anchor_before(route_parts: list[str], endpoint_parts: list[str], index: int) -> bool:
    return any(
        _route_static_part_matches_endpoint(route_part, endpoint_part)
        for route_part, endpoint_part in zip(route_parts[:index], endpoint_parts[:index])
    )


def _has_static_anchor_after(route_parts: list[str], endpoint_parts: list[str], index: int) -> bool:
    return any(
        _route_static_part_matches_endpoint(route_part, endpoint_part)
        for route_part, endpoint_part in zip(route_parts[index + 1 :], endpoint_parts[index + 1 :])
    )


def _route_static_part_matches_endpoint(route_part: str, endpoint_part: str) -> bool:
    if _is_route_param(route_part) or route_part == "*":
        return False
    return route_part == endpoint_part or _endpoint_param_can_match_static_route_part(endpoint_part, route_part)


def _param_match_has_signal(route_path: str, endpoint: str) -> bool:
    if _route_has_static_overlap(route_path, endpoint):
        return True

    route = _normalize_path(route_path)
    normalized_endpoint = _normalize_path(endpoint)
    route_parts = route.strip("/").split("/") if route.strip("/") else []
    endpoint_parts = normalized_endpoint.strip("/").split("/") if normalized_endpoint.strip("/") else []
    if not route_parts or len(route_parts) != len(endpoint_parts):
        return False

    if len(route_parts) == 1 and _is_route_param(route_parts[0]) and _route_param_name_looks_like_id(route_parts[0]):
        return _endpoint_part_is_id_like(endpoint_parts[0]) or _is_route_param(endpoint_parts[0])

    return all(_is_route_param(part) for part in endpoint_parts)


def _route_match_specificity(path: str) -> tuple[int, int, int]:
    return max(
        (_route_variant_match_specificity(variant) for variant in _route_path_variants(path)),
        default=(0, 0, 0),
    )


def _route_variant_match_specificity(path: str) -> tuple[int, int, int]:
    route = _normalize_path(path)
    parts = route.strip("/").split("/") if route.strip("/") else []
    static_count = sum(1 for part in parts if not _is_route_param(part) and part != "*")
    param_count = sum(1 for part in parts if _is_route_param(part))
    wildcard_count = sum(1 for part in parts if part == "*")
    return static_count, -wildcard_count, -param_count


def _route_path_variants(path: str) -> list[str]:
    normalized = _normalize_path(path)
    if "(" not in normalized:
        return [normalized]
    variants = [normalized]
    for _ in range(4):
        expanded: list[str] = []
        changed = False
        for variant in variants:
            match = re.search(r"\((?P<segment>/[^()]*)\)", variant)
            if not match:
                expanded.append(variant)
                continue
            changed = True
            expanded.append(f"{variant[:match.start()]}{variant[match.end():]}")
            expanded.append(f"{variant[:match.start()]}{match.group('segment')}{variant[match.end():]}")
        variants = list(dict.fromkeys(_normalize_path(variant) for variant in expanded))
        if not changed:
            break
    return variants


def _is_route_param(part: str) -> bool:
    return bool(
        re.fullmatch(r":[A-Za-z_][\w-]*", part)
        or re.fullmatch(r"\{[^/{}]+\}", part)
        or re.fullmatch(r"<[^/<>]+>", part)
        or re.fullmatch(r"\[[^/\[\]]+\]", part)
        or re.fullmatch(r"\*[A-Za-z_][\w-]*", part)
        or re.fullmatch(r"\(\*[A-Za-z_][\w-]*\)", part)
    )


def _is_endpoint_param_value(part: str, route_part: str | None = None) -> bool:
    if _is_route_param(part):
        return True
    if _endpoint_part_is_id_like(part):
        return True
    if route_part and _route_param_name_looks_like_id(route_part):
        return False
    if re.fullmatch(r"[A-Za-z0-9._~-]+", part):
        return True
    return False


def _endpoint_part_is_id_like(part: str) -> bool:
    return bool(
        re.fullmatch(r"\d+", part)
        or re.fullmatch(r"[0-9a-fA-F]{8,}(?:-[0-9a-fA-F]{4,})*", part)
    )


def _route_param_name_looks_like_id(part: str) -> bool:
    name = part.strip(":{}<>[]*()").lower()
    return name == "id" or name.endswith("_id") or name.endswith("-id") or name.endswith("id")


def _endpoint_param_can_match_static_route_part(endpoint_part: str, route_part: str) -> bool:
    if not _is_route_param(endpoint_part):
        return False
    name = endpoint_part.strip(":{}<>[]").lower()
    return "version" in name and re.fullmatch(r"v\d+", route_part) is not None


def _route_regex(path: str) -> re.Pattern[str]:
    normalized = _normalize_path(path)
    parts = normalized.strip("/").split("/") if normalized.strip("/") else []
    pattern_parts: list[str] = []
    for part in parts:
        if (
            re.fullmatch(r":[A-Za-z_][\w-]*", part)
            or re.fullmatch(r"\{[^/{}]+\}", part)
            or re.fullmatch(r"<[^/<>]+>", part)
            or re.fullmatch(r"\[[^/\[\]]+\]", part)
            or re.fullmatch(r"\*[A-Za-z_][\w-]*", part)
            or re.fullmatch(r"\(\*[A-Za-z_][\w-]*\)", part)
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
