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
ROUTER_PATH_RE = re.compile(r"\bpath\s*[:=]\s*['\"](?P<route>[^'\"]+)['\"]")
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
        if file_fact.role == "test":
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
    if normalized.startswith("pages/") and not normalized.startswith("pages/api/"):
        route = normalized.removeprefix("pages/").rsplit(".", 1)[0]
        routes.append(_route(file_fact, _page_route(route), "next", "next-pages-route", 1))
    if normalized.startswith("app/") and "/api/" not in normalized and normalized.endswith("/page.tsx"):
        route = normalized.removeprefix("app/").removesuffix("/page.tsx")
        routes.append(_route(file_fact, _page_route(route), "next", "next-app-route", 1))
    if normalized.endswith(".vue"):
        routes.append(_route(file_fact, _page_route(Path(normalized).stem), "vue", "vue-component-route", 1))
    if {"react", "vite", "next"} & frontend_frameworks:
        for match in ROUTER_PATH_RE.finditer(source):
            routes.append(
                _route(
                    file_fact,
                    match.group("route"),
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

    if not normalized.endswith((".tsx", ".jsx")):
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
    if path.startswith(("pages/", "app/")) or path.endswith(".vue"):
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
    if "next" in names and (path.startswith("pages/") or path.startswith("app/")):
        return "next"
    if "react" in names:
        return "react"
    if "vite" in names:
        return "vite"
    return "react"


def _page_route(route: str) -> str:
    cleaned = route.replace("/index", "").replace("[", ":").replace("]", "")
    return "/" + cleaned.strip("/") if cleaned.strip("/") else "/"


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
