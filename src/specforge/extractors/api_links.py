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
        external_target = _non_backend_target(call, before_backend_match=True)
        if external_target:
            link = _non_backend_api_link(call, external_target)
            links.append(link)
            linked_calls.append(replace(call, target_kind=link.target_kind))
            continue

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
                    target_kind="backend-route",
                    evidence=[call.evidence, route.evidence],
                )
            )
            linked_calls.append(replace(call, matched_route=matched_route, target_kind="backend-route"))
        else:
            non_backend_target = _non_backend_target(call, before_backend_match=False)
            if non_backend_target:
                link = _non_backend_api_link(call, non_backend_target)
                links.append(link)
                linked_calls.append(replace(call, target_kind=link.target_kind))
                continue
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
                    target_kind="backend-route",
                    evidence=[call.evidence],
                )
            )
            linked_calls.append(replace(call, target_kind="backend-route"))

    return links, linked_calls


def _non_backend_target(
    call: ApiCallFact,
    *,
    before_backend_match: bool,
) -> tuple[str, str, str | None, str] | None:
    endpoint = call.endpoint.strip().strip("'\"`")
    if not endpoint:
        return None
    if endpoint.startswith(("http://", "https://")):
        host = urlparse(endpoint).netloc or "external"
        return "external-api", "external-url", host, "high"
    if before_backend_match:
        return None
    if endpoint.startswith("dynamic:") or "${" in endpoint:
        return "dynamic-endpoint", "dynamic-endpoint", "dynamic", "medium"
    if endpoint.startswith("rails-helper:"):
        return "framework-helper", "framework-helper", "rails", "medium"
    return None


def _non_backend_api_link(
    call: ApiCallFact,
    target: tuple[str, str, str | None, str],
) -> ApiLinkFact:
    target_kind, match_type, matched_framework, confidence = target
    return ApiLinkFact(
        source=call.path,
        endpoint=call.endpoint,
        method=call.method,
        matched_route=None,
        matched_method=None,
        matched_framework=matched_framework,
        match_type=match_type,
        confidence=confidence,
        target_kind=target_kind,
        evidence=[call.evidence],
    )


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

    rails_helper_matches = _rails_helper_matches(call, routes)
    if rails_helper_matches:
        return _best_method_match(call, rails_helper_matches, "rails-helper")

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

    param_format_suffix_matches = []
    for route in routes:
        route_without_format = _route_without_format_suffix(route.path)
        if _route_has_static_overlap(route_without_format, endpoint_without_format) and _route_matches(
            route_without_format,
            endpoint_without_format,
        ):
            param_format_suffix_matches.append(route)
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

    static_choice_param_matches = _static_choice_param_route_matches(routes, endpoint_without_format)
    if static_choice_param_matches:
        return _best_method_match(call, static_choice_param_matches, "static-choice-param")

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
            elif (
                match_type.startswith("rails-anchored-param")
                or match_type.startswith("rails-resource-text-id-param")
                or match_type == "static-choice-param"
            ):
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


def _rails_helper_matches(call: ApiCallFact, routes: list[ApiRouteFact]) -> list[ApiRouteFact]:
    endpoint = call.endpoint.strip().strip("'\"`")
    match = re.fullmatch(r"rails-helper:(?P<helper>[A-Za-z_]\w*(?:_path|_url))", endpoint)
    if not match:
        return []
    stem = re.sub(r"_(?:path|url)$", "", match.group("helper"))
    handler_matches = [route for route in routes if route.framework == "rails" and _rails_route_handler_helper_matches(route.handler, stem)]
    path_matches = [route for route in routes if route.framework == "rails" and _rails_route_path_helper_matches(route.path, stem)]
    return _dedupe_routes([*handler_matches, *path_matches])


def _rails_route_handler_helper_matches(handler: str | None, stem: str) -> bool:
    if not handler or "#" not in handler:
        return False
    controller, action = handler.split("#", 1)
    controller = controller.strip().replace("/", "_")
    action = action.strip()
    if stem == f"{controller}_{action}":
        return True
    resource_actions = {
        "index",
        "create",
        "show",
        "update",
        "destroy",
        "new",
        "edit",
    }
    return action in resource_actions and stem in {controller, _singularize_rails_helper_stem(controller)}


def _rails_route_path_helper_matches(path: str, stem: str) -> bool:
    normalized = _without_format_suffix(_normalize_path(path))
    parts = [part for part in normalized.strip("/").split("/") if part and not _is_route_param(part) and part != "*"]
    if not parts:
        return False
    full_name = "_".join(_rails_helper_segment(part) for part in parts)
    collection_name = _rails_helper_segment(parts[0])
    return stem in {full_name, collection_name}


def _rails_helper_segment(segment: str) -> str:
    return segment.strip().replace("-", "_")


def _singularize_rails_helper_stem(stem: str) -> str:
    if stem.endswith("ies") and len(stem) > 3:
        return f"{stem[:-3]}y"
    if stem.endswith("s") and len(stem) > 1:
        return stem[:-1]
    return stem


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
    for suffix in (".json", ".csv"):
        if path.endswith(suffix) and len(path) > len(suffix):
            return path[: -len(suffix)]
    return path


def _route_without_format_suffix(path: str) -> str:
    return _without_format_suffix(_normalize_path(path))


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
    route_variants = _route_path_variants(route_path)
    endpoint_variants = _endpoint_path_variants(endpoint) if len(route_variants) > 1 else [_normalize_path(endpoint)]
    return any(
        _route_variant_matches(route_variant, endpoint)
        for route_variant in route_variants
        for endpoint in endpoint_variants
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
    route_variants = _route_path_variants(route_path)
    endpoint_variants = _endpoint_path_variants(endpoint) if len(route_variants) > 1 else [_normalize_path(endpoint)]
    return any(
        _route_variant_has_static_overlap(route_variant, endpoint)
        for route_variant in route_variants
        for endpoint in endpoint_variants
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


def _static_choice_param_route_matches(routes: list[ApiRouteFact], endpoint: str) -> list[ApiRouteFact]:
    grouped: dict[tuple[str, ...], list[tuple[ApiRouteFact, tuple[str, ...]]]] = {}
    for route in routes:
        for route_variant in _route_path_variants(_route_without_format_suffix(route.path)):
            result = _static_choice_param_signature(route_variant, endpoint)
            if not result:
                continue
            signature, alternatives = result
            grouped.setdefault(signature, []).append((route, alternatives))

    matches: list[ApiRouteFact] = []
    for candidates in grouped.values():
        alternative_values = {alternatives for _, alternatives in candidates}
        if len(alternative_values) < 2:
            continue
        matches.extend(route for route, _ in candidates)
    return sorted(_dedupe_routes(matches), key=lambda route: _route_match_specificity(route.path), reverse=True)


def _static_choice_param_signature(route_path: str, endpoint: str) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    route = _normalize_path(route_path)
    normalized_endpoint = _normalize_path(endpoint)
    route_parts = route.strip("/").split("/") if route.strip("/") else []
    endpoint_parts = normalized_endpoint.strip("/").split("/") if normalized_endpoint.strip("/") else []
    if not route_parts or len(route_parts) != len(endpoint_parts):
        return None

    signature: list[str] = []
    alternatives: list[str] = []
    has_static_anchor = False
    saw_choice = False
    for route_part, endpoint_part in zip(route_parts, endpoint_parts):
        if route_part == endpoint_part:
            if not _is_route_param(route_part):
                has_static_anchor = True
            signature.append(route_part)
            continue
        if _is_route_param(route_part):
            if not _is_endpoint_param_value(endpoint_part, route_part):
                return None
            signature.append(_route_param_signature_part(route_part))
            continue
        if _endpoint_param_can_match_static_route_part(endpoint_part, route_part):
            signature.append(route_part)
            continue
        if _is_route_param(endpoint_part) and not _route_param_name_looks_like_id(endpoint_part) and _static_choice_route_part_is_safe(route_part):
            signature.append(":static-choice")
            alternatives.append(route_part)
            saw_choice = True
            continue
        return None

    if not saw_choice or not has_static_anchor:
        return None
    return tuple(signature), tuple(alternatives)


def _route_param_signature_part(part: str) -> str:
    if _route_param_name_looks_like_id(part):
        return ":id"
    return ":param"


def _static_choice_route_part_is_safe(part: str) -> bool:
    return not _is_route_param(part) and part != "*" and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", part) is not None


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
            if match:
                changed = True
                expanded.append(f"{variant[:match.start()]}{variant[match.end():]}")
                expanded.append(f"{variant[:match.start()]}{match.group('segment')}{variant[match.end():]}")
                continue
            match = re.search(r"/\((?P<segment>[^()/][^()]*)\)", variant)
            if match:
                changed = True
                expanded.append(f"{variant[:match.start()]}{variant[match.end():]}")
                expanded.append(f"{variant[:match.start()]}/{match.group('segment')}{variant[match.end():]}")
                continue
            expanded.append(variant)
        variants = list(dict.fromkeys(_normalize_path(variant) for variant in expanded))
        if not changed:
            break
    return variants


def _endpoint_path_variants(path: str) -> list[str]:
    normalized = _normalize_path(path)
    parts = normalized.strip("/").split("/") if normalized.strip("/") else []
    variants: list[list[str]] = [[]]
    for part in parts:
        params = _adjacent_endpoint_params(part)
        choices = [params[:index] for index in range(1, len(params) + 1)] if len(params) > 1 else [[part]]
        variants = [prefix + choice for prefix in variants for choice in choices]
    if not parts:
        return [normalized]
    return list(dict.fromkeys(_normalize_path("/".join(parts_variant)) for parts_variant in variants))


def _adjacent_endpoint_params(part: str) -> list[str]:
    params = re.findall(r":[A-Za-z_][\w-]*", part)
    return params if params and "".join(params) == part else []


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
