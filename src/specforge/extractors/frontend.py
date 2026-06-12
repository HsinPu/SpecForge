from __future__ import annotations

import re
from pathlib import Path

from specforge.models import (
    ApiCallFact,
    ComponentFact,
    Evidence,
    FileFact,
    FrameworkFact,
    FrontendRouteFact,
    FrontendSurfaceFact,
    StateUsageFact,
    SymbolFact,
)


FETCH_RE = re.compile(r"\bfetch\(\s*['\"`](?P<endpoint>[^'\"`]+)['\"`](?P<args>[^)]*)\)", re.DOTALL)
AXIOS_RE = re.compile(r"\baxios\.(?P<method>get|post|put|delete|patch)\(\s*['\"`](?P<endpoint>[^'\"`]+)['\"`]", re.IGNORECASE)
CLIENT_CALL_RE = re.compile(
    r"\b(?P<client>api|client|http|request|service)\.(?P<method>get|post|put|delete|patch)"
    r"\(\s*['\"`](?P<endpoint>/[^'\"`]+)['\"`]",
    re.IGNORECASE,
)
HOOK_RE = re.compile(r"\b(use[A-Z]\w*)\s*\(")
ROUTER_PATH_RE = re.compile(r"\bpath\s*[:=]\s*['\"](?P<route>[^'\"\r\n]+)['\"]")
PROPS_INTERFACE_RE = re.compile(r"(?:interface|type)\s+(?P<name>[A-Za-z_$][\w$]*Props)\s*(?:=)?\s*{(?P<body>[^}]+)}", re.DOTALL)
PROP_NAME_RE = re.compile(r"(?P<name>[A-Za-z_$][\w$]*)\??\s*:")
STATE_PATTERNS = [
    ("react", "hook", re.compile(r"\b(useState|useReducer|useContext)\s*\(")),
    ("react-redux", "store", re.compile(r"\b(useSelector|useDispatch)\s*\(")),
    ("redux", "store", re.compile(r"\b(createSlice|configureStore|createStore)\s*\(")),
    ("zustand", "store", re.compile(r"\bcreate\s*\(")),
    ("pinia", "store", re.compile(r"\b(defineStore|createPinia)\s*\(")),
    ("vue", "state", re.compile(r"\b(ref|reactive|computed)\s*\(")),
]


def extract_frontend_facts(
    root: Path,
    files: list[FileFact],
    symbols: list[SymbolFact],
    frameworks: list[FrameworkFact],
) -> tuple[
    list[FrontendRouteFact],
    list[ComponentFact],
    list[ApiCallFact],
    list[StateUsageFact],
    list[FrontendSurfaceFact],
]:
    routes: list[FrontendRouteFact] = []
    components: list[ComponentFact] = []
    api_calls: list[ApiCallFact] = []
    state_usages: list[StateUsageFact] = []
    frontend_frameworks = {item.name for item in frameworks if item.category == "frontend"}

    for file_fact in files:
        if file_fact.role in {"test", "sample"}:
            continue
        normalized = file_fact.path.replace("\\", "/")
        if not _is_frontend_candidate(normalized, frontend_frameworks):
            continue
        if file_fact.language in {"typescript", "javascript"} or normalized.endswith(".vue"):
            source = _read(root, file_fact)
            routes.extend(_extract_frontend_routes(file_fact, source, frontend_frameworks))
            components.extend(_extract_components(file_fact, source, symbols, frameworks))
            api_calls.extend(_extract_api_calls(file_fact, source))
            state_usages.extend(_extract_state_usages(file_fact, source))

    surfaces = build_frontend_surfaces(
        routes,
        components,
        api_calls,
        frameworks,
        state_usages=state_usages,
    )
    return routes, components, api_calls, state_usages, surfaces


def _extract_frontend_routes(
    file_fact: FileFact,
    source: str,
    frontend_frameworks: set[str],
) -> list[FrontendRouteFact]:
    routes: list[FrontendRouteFact] = []
    normalized = file_fact.path.replace("\\", "/")
    next_route = _next_route_for_path(normalized)
    if next_route:
        route, kind = next_route
        routes.append(_route(file_fact, route, "next", kind, 1))
    if normalized.endswith(".vue"):
        routes.append(_route(file_fact, _page_route(Path(normalized).stem), "vue", "vue-component-route", 1))
    if _should_extract_angular_routes(source, frontend_frameworks):
        for match in ROUTER_PATH_RE.finditer(source):
            route_value = match.group("route")
            if not _looks_like_route_value(route_value):
                continue
            routes.append(
                _route(
                    file_fact,
                    _normalize_frontend_route(route_value),
                    "angular",
                    "angular-route",
                    _line_for_offset(source, match.start()),
                )
            )
    elif _should_extract_vue_router_routes(source, frontend_frameworks):
        for match in ROUTER_PATH_RE.finditer(source):
            route_value = match.group("route")
            if not _looks_like_route_value(route_value):
                continue
            routes.append(
                _route(
                    file_fact,
                    _normalize_frontend_route(route_value),
                    "vue",
                    "vue-router-route",
                    _line_for_offset(source, match.start()),
                )
            )
    elif _should_extract_react_router_routes(source, frontend_frameworks):
        for match in ROUTER_PATH_RE.finditer(source):
            route_value = match.group("route")
            if not _looks_like_route_value(route_value):
                continue
            routes.append(
                _route(
                    file_fact,
                    _normalize_frontend_route(route_value),
                    "react",
                    "react-router-route",
                    _line_for_offset(source, match.start()),
                )
            )
    return routes


def _extract_components(
    file_fact: FileFact,
    source: str,
    symbols: list[SymbolFact],
    frameworks: list[FrameworkFact],
) -> list[ComponentFact]:
    normalized = file_fact.path.replace("\\", "/")
    framework = _frontend_framework_for_path(normalized, frameworks)
    props_by_name = _props_by_interface(source)
    hooks = sorted(set(HOOK_RE.findall(source)))
    components: list[ComponentFact] = []

    if normalized.endswith(".vue"):
        components.append(
            ComponentFact(
                name=Path(normalized).stem,
                path=file_fact.path,
                framework="vue",
                props=_vue_props(source),
                hooks=[],
                evidence=Evidence(file=file_fact.path, kind="frontend-component", line_start=1, line_end=1),
            )
        )
        return components

    if not normalized.endswith((".tsx", ".jsx", ".js", ".mjs")):
        return []
    if normalized.endswith((".js", ".mjs")) and not _looks_like_react_component_source(source):
        return []

    for symbol in symbols:
        if symbol.path != file_fact.path or symbol.kind not in {"function", "class"}:
            continue
        if not symbol.name[:1].isupper() or symbol.name.endswith("Props"):
            continue
        components.append(
            ComponentFact(
                name=symbol.name,
                path=file_fact.path,
                framework=framework,
                props=props_by_name.get(f"{symbol.name}Props", []),
                hooks=hooks,
                evidence=symbol.evidence,
            )
        )
    return components


def _extract_api_calls(file_fact: FileFact, source: str) -> list[ApiCallFact]:
    calls: list[ApiCallFact] = []
    for match in FETCH_RE.finditer(source):
        method = _fetch_method(match.group("args"))
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=match.group("endpoint"),
                method=method,
                client="fetch",
                trigger="runtime",
                context="source",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    for match in AXIOS_RE.finditer(source):
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=match.group("endpoint"),
                method=match.group("method").upper(),
                client="axios",
                trigger="runtime",
                context="source",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    for match in CLIENT_CALL_RE.finditer(source):
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=match.group("endpoint"),
                method=match.group("method").upper(),
                client=match.group("client"),
                trigger="runtime",
                context="source",
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    return calls


def _extract_state_usages(file_fact: FileFact, source: str) -> list[StateUsageFact]:
    usages: list[StateUsageFact] = []
    for library, usage, pattern in STATE_PATTERNS:
        if library == "zustand" and "zustand" not in source:
            continue
        for match in pattern.finditer(source):
            line = _line_for_offset(source, match.start())
            name = match.group(1) if match.groups() else match.group(0).strip("(")
            usages.append(
                StateUsageFact(
                    source=file_fact.path,
                    library=library,
                    usage=usage,
                    name=name,
                    evidence=Evidence(file=file_fact.path, kind="state-usage", line_start=line, line_end=line),
                )
            )
    return usages


def build_frontend_surfaces(
    routes: list[FrontendRouteFact],
    components: list[ComponentFact],
    api_calls: list[ApiCallFact],
    frameworks: list[FrameworkFact],
    pages: list[object] | None = None,
    forms: list[object] | None = None,
    styles: list[object] | None = None,
    assets: list[object] | None = None,
    state_usages: list[StateUsageFact] | None = None,
) -> list[FrontendSurfaceFact]:
    pages = pages or []
    forms = forms or []
    styles = styles or []
    assets = assets or []
    state_usages = state_usages or []
    frontend_frameworks = {item.name for item in frameworks if item.category == "frontend"}
    frontend_frameworks.update(route.framework for route in routes)
    frontend_frameworks.update(component.framework for component in components)
    if pages:
        frontend_frameworks.add("static-site")
    surfaces: list[FrontendSurfaceFact] = []
    for framework in sorted(frontend_frameworks):
        framework_routes = [route for route in routes if route.framework == framework]
        framework_components = [component for component in components if component.framework == framework]
        is_static = framework in {"static-site", "html", "thymeleaf", "freemarker", "handlebars", "mustache", "ejs", "pug", "jsp"}
        surfaces.append(
            FrontendSurfaceFact(
                framework=framework,
                route_count=len(framework_routes),
                component_count=len(framework_components),
                api_call_count=len(api_calls),
                page_count=len(pages) if is_static else 0,
                form_count=len(forms) if is_static else 0,
                style_count=len(styles) if is_static or framework in {"sass", "tailwind", "bootstrap"} else 0,
                asset_count=len(assets) if is_static else 0,
                state_count=len(state_usages) if framework not in {"static-site", "html"} else 0,
                evidence=[
                    *[route.evidence for route in framework_routes[:5]],
                    *[component.evidence for component in framework_components[:5]],
                    *[getattr(page, "evidence") for page in pages[:5] if is_static],
                ],
            )
        )
    return surfaces


def _is_frontend_candidate(path: str, frontend_frameworks: set[str]) -> bool:
    if _next_route_for_path(path) or path.endswith(".vue"):
        return True
    if frontend_frameworks and path.endswith((".tsx", ".jsx")):
        return True
    if frontend_frameworks and path.endswith((".ts", ".js", ".mjs")):
        return True
    if frontend_frameworks and ("/components/" in f"/{path}" or path.lower().endswith(("app.tsx", "app.jsx"))):
        return True
    return False


def _props_by_interface(source: str) -> dict[str, list[str]]:
    props: dict[str, list[str]] = {}
    for match in PROPS_INTERFACE_RE.finditer(source):
        props[match.group("name")] = PROP_NAME_RE.findall(match.group("body"))
    return props


def _vue_props(source: str) -> list[str]:
    match = re.search(r"defineProps\s*<\s*{(?P<body>[^}]+)}\s*>", source, re.DOTALL)
    return PROP_NAME_RE.findall(match.group("body")) if match else []


def _fetch_method(args: str) -> str:
    match = re.search(r"method\s*:\s*['\"](?P<method>[A-Z]+)['\"]", args, re.IGNORECASE)
    return match.group("method").upper() if match else "GET"


def _frontend_framework_for_path(path: str, frameworks: list[FrameworkFact]) -> str:
    names = {item.name for item in frameworks if item.category == "frontend"}
    if "next" in names and _next_route_for_path(path):
        return "next"
    if "react" in names:
        return "react"
    if "vite" in names:
        return "vite"
    return "react"


def _page_route(route: str) -> str:
    grouped = _strip_next_route_groups(route)
    cleaned = "" if grouped == "index" else grouped.replace("/index", "")
    cleaned = cleaned.replace("[", ":").replace("]", "")
    return "/" + cleaned.strip("/") if cleaned.strip("/") else "/"


def _next_route_for_path(path: str) -> tuple[str, str] | None:
    for marker in ("/app/", "app/"):
        if _inside_non_route_source_tree(path, marker):
            continue
        route_part = _path_after_marker(path, marker)
        if route_part is None:
            continue
        if "/api/" in f"/{route_part}/":
            return None
        if re.fullmatch(r"page\.(?:tsx|ts|jsx|js)", route_part):
            return "/", "next-app-route"
        match = re.match(r"(?P<route>.*)/page\.(?:tsx|ts|jsx|js)$", route_part)
        if match:
            return _page_route(match.group("route")), "next-app-route"

    for marker in ("/pages/", "pages/"):
        if _inside_non_route_source_tree(path, marker):
            continue
        route_part = _path_after_marker(path, marker)
        if route_part is None:
            continue
        if route_part.startswith("api/") or "/api/" in f"/{route_part}":
            return None
        if not route_part.endswith((".tsx", ".ts", ".jsx", ".js")):
            continue
        if Path(route_part).stem.startswith("_"):
            return None
        return _page_route(route_part.rsplit(".", 1)[0]), "next-pages-route"
    return None


def _path_after_marker(path: str, marker: str) -> str | None:
    if path.startswith(marker):
        return path.removeprefix(marker)
    if not marker.startswith("/"):
        return None
    index = path.find(marker)
    if index == -1:
        return None
    return path[index + len(marker):]


def _inside_non_route_source_tree(path: str, marker: str) -> bool:
    prefix = _path_before_marker(path, marker)
    if prefix is None:
        return False
    normalized = prefix.strip("/")
    return "/src/" in f"/{normalized}/" and normalized != "src" and not normalized.endswith("/src")


def _path_before_marker(path: str, marker: str) -> str | None:
    if path.startswith(marker):
        return ""
    if not marker.startswith("/"):
        return None
    index = path.find(marker)
    if index == -1:
        return None
    return path[:index]


def _strip_next_route_groups(route: str) -> str:
    parts = [part for part in route.split("/") if part and not (part.startswith("(") and part.endswith(")"))]
    return "/".join(parts)


def _looks_like_react_component_source(source: str) -> bool:
    return (
        "React.createElement" in source
        or "extends React.Component" in source
        or bool(re.search(r"\breturn\s*\(?\s*<", source))
        or bool(re.search(r"=>\s*\(?\s*<", source))
    )


def _should_extract_react_router_routes(source: str, frontend_frameworks: set[str]) -> bool:
    return bool(
        {"react-router", "react"} & frontend_frameworks
        and (
            "react-router" in source
            or "<Route" in source
            or "createBrowserRouter" in source
            or "createHashRouter" in source
            or "RouterProvider" in source
        )
    )


def _should_extract_angular_routes(source: str, frontend_frameworks: set[str]) -> bool:
    return bool(
        "angular" in frontend_frameworks
        and (
            "@angular/router" in source
            or "RouterModule.forRoot" in source
            or "RouterModule.forChild" in source
            or re.search(r"\bRoutes\b", source)
        )
    )


def _should_extract_vue_router_routes(source: str, frontend_frameworks: set[str]) -> bool:
    return bool(
        {"vue-router", "vue"} & frontend_frameworks
        and (
            "vue-router" in source
            or "createRouter" in source
            or "createWebHistory" in source
            or "createMemoryHistory" in source
        )
    )


def _looks_like_route_value(route: str) -> bool:
    if not route or route.startswith((".", "http:", "https:", "file:")):
        return False
    if any(char in route for char in ("\n", "\r", "`", "$", "{", "}")):
        return False
    return route in {"", "**"} or route.startswith(("/", ":", "*")) or "/" in route or route.isidentifier()


def _normalize_frontend_route(route: str) -> str:
    stripped = route.strip()
    if not stripped or stripped == "**" or stripped.startswith(("/", ":", "*")):
        return stripped or "/"
    return "/" + stripped


def _route(file_fact: FileFact, route: str, framework: str, kind: str, line: int) -> FrontendRouteFact:
    return FrontendRouteFact(
        route=route,
        path=file_fact.path,
        framework=framework,
        kind=kind,
        evidence=Evidence(file=file_fact.path, kind="frontend-route", line_start=line, line_end=line),
    )


def _read(root: Path, file_fact: FileFact) -> str:
    return (root / file_fact.path).read_text(encoding="utf-8")


def _line_for_offset(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1
