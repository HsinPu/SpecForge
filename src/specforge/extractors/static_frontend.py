from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from specforge.models import (
    ApiCallFact,
    AssetFact,
    Evidence,
    FileFact,
    FormFact,
    FrontendMapFact,
    FrontendRouteFact,
    PageFact,
    StyleFact,
)


PAGE_LANGUAGES = {
    "html",
    "jsp",
    "freemarker",
    "handlebars",
    "mustache",
    "ejs",
    "pug",
    "twig",
    "haml",
    "eex",
    "heex",
    "leex",
    "liquid",
    "erb",
    "ruby-template",
    "razor",
    "astro",
    "blade",
    "twirl",
}
STYLE_LANGUAGES = {"css", "scss", "sass", "less"}
COMPONENT_MARKUP_LANGUAGES = {"svelte"}
TITLE_RE = re.compile(r"<title[^>]*>(?P<title>.*?)</title>", re.IGNORECASE | re.DOTALL)
FRONTMATTER_TITLE_RE = re.compile(r"^---\s*\n(?P<body>[\s\S]*?)\n---", re.MULTILINE)
FRONTMATTER_TITLE_LINE_RE = re.compile(r"(?m)^\s*title\s*:\s*(?P<title>.+?)\s*$")
STREAMLIT_PAGE_CONFIG_RE = re.compile(
    r"\bst\.set_page_config\s*\((?P<body>[\s\S]{0,1000}?)\)",
    re.IGNORECASE,
)
STREAMLIT_PAGE_TITLE_RE = re.compile(
    r"\bpage_title\s*=\s*(?P<quote>['\"])(?P<title>.*?)(?P=quote)",
    re.DOTALL,
)
STREAMLIT_TITLE_RE = re.compile(
    r"\bst\.(?:title|header)\s*\(\s*(?P<quote>['\"])(?P<title>.*?)(?P=quote)",
    re.DOTALL,
)
GRADIO_APP_CALL_RE = re.compile(
    r"\b(?:gr|gradio)\."
    r"(?P<kind>Blocks|Interface|ChatInterface|TabbedInterface|load)\s*"
    r"\((?P<body>(?:[^()'\"\[\]]+|'[^']*'|\"[^\"]*\"|\[[\s\S]{0,500}?\]){0,1800})\)",
    re.IGNORECASE,
)
GRADIO_TITLE_RE = re.compile(
    r"\btitle\s*=\s*(?P<quote>['\"])(?P<title>.*?)(?P=quote)",
    re.DOTALL,
)
GRADIO_MARKDOWN_TITLE_RE = re.compile(
    r"\bgr\.Markdown\s*\(\s*(?P<quote>['\"])\s*#{1,2}\s*(?P<title>[^'\"\r\n]+)(?P=quote)",
    re.DOTALL,
)
DASH_APP_CALL_RE = re.compile(
    r"\b(?:dash\.)?Dash\s*"
    r"\((?P<body>(?:[^()'\"\[\]]+|'[^']*'|\"[^\"]*\"|\[[\s\S]{0,500}?\]){0,1800})\)",
    re.IGNORECASE,
)
DASH_TITLE_RE = re.compile(
    r"\btitle\s*=\s*(?P<quote>['\"])(?P<title>.*?)(?P=quote)",
    re.DOTALL,
)
DASH_HEADING_RE = re.compile(
    r"\bhtml\.H[12]\s*\(\s*(?P<quote>['\"])(?P<title>.*?)(?P=quote)",
    re.DOTALL,
)
PANEL_TITLE_RE = re.compile(
    r"\btitle\s*=\s*(?P<quote>['\"])(?P<title>.*?)(?P=quote)",
    re.DOTALL,
)
PANEL_MARKDOWN_TITLE_RE = re.compile(
    r"\bpn\.(?:pane\.)?Markdown\s*\(\s*(?P<quote>['\"])\s*#{1,2}\s*(?P<title>[^'\"\r\n]+)(?P=quote)",
    re.DOTALL,
)
TAG_RE = re.compile(r"<\.?(?P<tag>form|a|script|link|img|source)\b(?P<attrs>[^>]*)>", re.IGNORECASE | re.DOTALL)
FORM_TAG_RE = re.compile(r"<\.?form\b(?P<attrs>(?:=>|->|[^>])*?)>", re.IGNORECASE | re.DOTALL)
JSX_FORM_TAG_RE = re.compile(r"<(?P<tag>Form|fetcher\.Form)\b(?P<attrs>(?:=>|->|[^>])*?)>", re.IGNORECASE | re.DOTALL)
RAILS_FORM_HELPER_RE = re.compile(
    r"<%=\s*(?P<helper>simple_form_for|(?:labelled_)?form_for|form_with|form_tag)\s*(?P<args>[\s\S]{0,900}?)\s+do(?:\s*\|[^|]*\|)?\s*%>",
    re.IGNORECASE,
)
HAML_RAILS_FORM_HELPER_RE = re.compile(
    r"(?m)^\s*=\s*(?P<helper>simple_form_for|(?:labelled_)?form_for|form_with|form_tag)\s*"
    r"(?P<args>[\s\S]{0,900}?)\s+do(?:\s*\|(?P<builder>[^|]+)\|)?",
    re.IGNORECASE,
)
RAILS_FIELD_RE = re.compile(
    r"\b(?:[A-Za-z_]\w*\.)?"
    r"(?P<helper>input|text_field|password_field|email_field|hidden_field|file_field|text_area|select|collection_select|check_box|radio_button)"
    r"\s+:?(?P<quote>['\"])?(?P<name>[A-Za-z_][\w.\[\]-]*)(?P=quote)?",
    re.IGNORECASE,
)
RAILS_TAG_FIELD_RE = re.compile(
    r"\b(?P<helper>text_field_tag|password_field_tag|email_field_tag|hidden_field_tag|file_field_tag|text_area_tag|select_tag|check_box_tag|radio_button_tag)"
    r"\s*(?:\(?\s*)?:?(?P<quote>['\"])?(?P<name>[A-Za-z_][\w\[\]#{}.-]*)(?P=quote)?",
    re.IGNORECASE,
)
ATTR_RE = re.compile(
    r"(?P<name>[:@\w.-]+)(?:\s*=\s*(?:(?P<quote>['\"])(?P<value>.*?)(?P=quote)|\{(?P<brace_value>.*?)\}))?",
    re.DOTALL,
)
INPUT_RE = re.compile(r"<(?:input|select|textarea)\b(?P<attrs>[^>]*)>", re.IGNORECASE | re.DOTALL)
HEEX_INPUT_RE = re.compile(
    r"<\.input\b(?P<attrs>(?:=>|->|[^>])*?)(?:/?>)",
    re.IGNORECASE | re.DOTALL,
)
RAZOR_FIELD_TAG_RE = re.compile(
    r"<(?:nop-editor|nop-select|nop-textarea|nop-override-store-checkbox|nop-bb-code-editor)"
    r"\b(?P<attrs>[^>]*)>",
    re.IGNORECASE | re.DOTALL,
)
RAZOR_HTML_HELPER_FIELD_RE = re.compile(
    r"@\s*Html\.(?:EditorFor|TextBoxFor|HiddenFor|CheckBoxFor|DropDownListFor|TextAreaFor)"
    r"\s*\(\s*(?:[A-Za-z_]\w*)\s*=>\s*(?:[A-Za-z_]\w*)\."
    r"(?P<name>[A-Za-z_]\w*(?:\[[^\]]+\])?(?:\.[A-Za-z_]\w*)*)",
    re.IGNORECASE,
)
FETCH_RE = re.compile(r"(?<!\.)\bfetch\(\s*['\"`](?P<endpoint>[^'\"`]+)['\"`](?P<args>[^)]*)\)", re.DOTALL)
AXIOS_RE = re.compile(
    r"\baxios\.(?P<method>get|post|put|delete|patch)\(\s*['\"`](?P<endpoint>[^'\"`]+)['\"`]",
    re.IGNORECASE,
)
BLADE_ROUTE_FETCH_RE = re.compile(
    r"(?<!\.)\bfetch\(\s*"
    r"(?P<quote>['\"])\s*"
    r"\{\{\s*route\(\s*(?P<name_quote>['\"])(?P<name>[^'\"]+)(?P=name_quote)[^}]*\}\}\s*"
    r"(?P=quote)(?P<args>[^)]*)\)",
    re.IGNORECASE | re.DOTALL,
)
BLADE_ROUTE_AXIOS_RE = re.compile(
    r"\baxios\.(?P<method>get|post|put|delete|patch)\(\s*"
    r"(?P<quote>['\"])\s*"
    r"\{\{\s*route\(\s*(?P<name_quote>['\"])(?P<name>[^'\"]+)(?P=name_quote)[^}]*\}\}\s*"
    r"(?P=quote)",
    re.IGNORECASE | re.DOTALL,
)
CLIENT_CALL_RE = re.compile(
    r"\b(?P<client>api|client|http|request|service)\.(?P<method>get|post|put|delete|patch)"
    r"\(\s*['\"`](?P<endpoint>/[^'\"`]+)['\"`]",
    re.IGNORECASE,
)
EVENTSOURCE_RE = re.compile(r"\bnew\s+EventSource\(\s*['\"`](?P<endpoint>[^'\"`]+)['\"`]", re.IGNORECASE)
WEBSOCKET_CLIENT_RE = re.compile(r"\bnew\s+WebSocket\(\s*['\"`](?P<endpoint>[^'\"`]+)['\"`]", re.IGNORECASE)
WEBSOCKET_SEND_RE = re.compile(r"\b[A-Za-z_$][\w$]*\.send\(", re.IGNORECASE)
CSS_IMPORT_RE = re.compile(r"@import\s+(?:url\()?['\"]?(?P<value>[^'\"\);]+)", re.IGNORECASE)
CSS_URL_RE = re.compile(r"url\(\s*['\"]?(?P<value>[^'\"\)]+)['\"]?\s*\)", re.IGNORECASE)
CSS_VAR_RE = re.compile(r"(?P<var>--[A-Za-z0-9_-]+)\s*:")
CSS_CLASS_RE = re.compile(r"\.(?P<class>[A-Za-z_-][\w-]*)")
CSS_ID_RE = re.compile(r"#(?P<id>[A-Za-z_-][\w-]*)")
CSS_SELECTOR_RE = re.compile(r"(?P<selector>[^{}@]+)\{")


def extract_static_frontend_facts(
    root: Path,
    files: list[FileFact],
) -> tuple[
    list[PageFact],
    list[FormFact],
    list[AssetFact],
    list[StyleFact],
    list[FrontendRouteFact],
    list[ApiCallFact],
]:
    pages: list[PageFact] = []
    forms: list[FormFact] = []
    assets: list[AssetFact] = []
    styles: list[StyleFact] = []
    routes: list[FrontendRouteFact] = []
    api_calls: list[ApiCallFact] = []
    streamlit_main_paths = _streamlit_main_paths(root, files)
    gradio_main_paths = _gradio_main_paths(root, files)
    dash_main_paths = _dash_main_paths(root, files)
    panel_main_paths = _panel_main_paths(root, files)

    for file_fact in files:
        if _is_astro_content_page_path(file_fact.path):
            source = _read(root, file_fact)
            page = _extract_astro_content_page(file_fact, source)
            pages.append(page)
            routes.append(
                FrontendRouteFact(
                    route=page.route,
                    path=file_fact.path,
                    framework="astro",
                    kind="astro-content-page-route",
                    evidence=page.evidence,
                )
            )
            continue
        if file_fact.role in {"test", "sample", "generated", "documentation"}:
            continue
        if file_fact.role == "asset" and _is_frontend_static_asset_file(file_fact.path):
            assets.append(_extract_standalone_asset(file_fact))
            continue
        if file_fact.language == "python":
            source = _read(root, file_fact)
            if _looks_like_streamlit_source(source):
                page = _extract_streamlit_page(file_fact, source, file_fact.path in streamlit_main_paths)
                pages.append(page)
                routes.append(
                    FrontendRouteFact(
                        route=page.route,
                        path=file_fact.path,
                        framework="streamlit",
                        kind="streamlit-page-route",
                        evidence=page.evidence,
                    )
                )
            elif _looks_like_gradio_source(source):
                page = _extract_gradio_page(file_fact, source, file_fact.path in gradio_main_paths)
                pages.append(page)
                routes.append(
                    FrontendRouteFact(
                        route=page.route,
                        path=file_fact.path,
                        framework="gradio",
                        kind="gradio-app-route",
                        evidence=page.evidence,
                    )
                )
            elif _looks_like_dash_source(source):
                page = _extract_dash_page(file_fact, source, file_fact.path in dash_main_paths)
                pages.append(page)
                routes.append(
                    FrontendRouteFact(
                        route=page.route,
                        path=file_fact.path,
                        framework="dash",
                        kind="dash-app-route",
                        evidence=page.evidence,
                    )
                )
            elif _looks_like_panel_app_source(source):
                page = _extract_panel_page(file_fact, source, file_fact.path in panel_main_paths)
                pages.append(page)
                routes.append(
                    FrontendRouteFact(
                        route=page.route,
                        path=file_fact.path,
                        framework="panel",
                        kind="panel-app-route",
                        evidence=page.evidence,
                    )
                )
            continue
        if file_fact.language in PAGE_LANGUAGES:
            source = _read(root, file_fact)
            if not _is_non_routable_template(file_fact.path, source):
                page = _extract_page(file_fact, source)
                pages.append(page)
                if file_fact.language != "astro" and not file_fact.path.replace("\\", "/").lower().endswith(".razor"):
                    routes.append(
                        FrontendRouteFact(
                            route=page.route,
                            path=file_fact.path,
                            framework=page.template_engine or "static-site",
                            kind="template-page-route" if page.template_engine else "static-page-route",
                            evidence=page.evidence,
                        )
                    )
            forms.extend(_extract_forms(file_fact, source))
            assets.extend(_extract_page_assets(file_fact, source))
            if file_fact.language != "astro":
                api_calls.extend(_extract_api_calls(file_fact, source, "inline-script"))
        elif file_fact.language == "php":
            source = _read(root, file_fact)
            if _looks_like_php_template_source(source):
                forms.extend(_extract_php_forms(file_fact, source))
                assets.extend(_extract_page_assets(file_fact, source))
        elif file_fact.language in STYLE_LANGUAGES:
            source = _read(root, file_fact)
            style = _extract_style(file_fact, source)
            styles.append(style)
            assets.extend(_style_assets(style))
        elif _is_jsx_markup_file(file_fact):
            source = _read(root, file_fact)
            forms.extend(_extract_jsx_forms(file_fact, source))
        elif file_fact.language in COMPONENT_MARKUP_LANGUAGES:
            source = _read(root, file_fact)
            if _is_sveltekit_page_component(file_fact.path):
                pages.append(_extract_sveltekit_page(file_fact, source))
            forms.extend(_extract_forms(file_fact, source))
            assets.extend(_extract_page_assets(file_fact, source))

    return pages, forms, assets, styles, routes, api_calls


def build_frontend_maps(
    pages: list[PageFact],
    frontend_routes: list[FrontendRouteFact],
    components: list[object],
    api_calls: list[ApiCallFact],
    state_usages: list[object],
    styles: list[StyleFact],
    assets: list[AssetFact],
) -> list[FrontendMapFact]:
    maps: list[FrontendMapFact] = []
    global_styles = [style.path for style in styles[:10]]
    routes_by_route = _frontend_routes_by_route(frontend_routes)
    for page in pages:
        page_assets = [asset.asset_path for asset in assets if asset.source == page.path]
        route_sources = _compatible_route_sources(page, routes_by_route.get(page.route, []))
        route_dir = _route_group_dir(page.path)
        related_sources = _dedupe([page.path, *[item.path for item in route_sources]])
        allow_group_fallback = _allow_route_group_fallback(page.path)
        page_components = [
            item.name
            for item in components
            if item.path in related_sources or (allow_group_fallback and _belongs_to_route_group(route_dir, item.path))
        ]
        page_calls = [
            call.endpoint
            for call in api_calls
            if call.path in related_sources or (allow_group_fallback and _belongs_to_route_group(route_dir, call.path))
        ]
        page_state = [
            f"{state.library}:{state.name}"
            for state in state_usages
            if state.source in related_sources or (allow_group_fallback and _belongs_to_route_group(route_dir, state.source))
        ]
        maps.append(
            FrontendMapFact(
                route=page.route,
                page=page.path,
                components=_dedupe(page_components),
                api_calls=_dedupe(page_calls),
                state=_dedupe(page_state),
                styles=_dedupe(global_styles + [asset for asset in page_assets if _asset_kind(asset) == "style"]),
                assets=_dedupe(page_assets),
                evidence=_dedupe_evidence([page.evidence, *[item.evidence for item in route_sources]]),
            )
        )
    for route, route_sources in routes_by_route.items():
        if any(item.route == route for item in maps):
            continue
        primary = _primary_route_source(route_sources)
        if primary is None:
            continue
        route_dir = _route_group_dir(primary.path)
        related_sources = [item.path for item in route_sources]
        allow_group_fallback = _allow_route_group_fallback(primary.path)
        route_components = [
            item.name
            for item in components
            if item.path in related_sources or (allow_group_fallback and _belongs_to_route_group(route_dir, item.path))
        ]
        route_calls = [
            call.endpoint
            for call in api_calls
            if call.path in related_sources or (allow_group_fallback and _belongs_to_route_group(route_dir, call.path))
        ]
        route_state = [
            f"{state.library}:{state.name}"
            for state in state_usages
            if state.source in related_sources or (allow_group_fallback and _belongs_to_route_group(route_dir, state.source))
        ]
        if not route_components and not route_calls and not route_state:
            continue
        maps.append(
            FrontendMapFact(
                route=route,
                page=primary.path,
                components=_dedupe(route_components),
                api_calls=_dedupe(route_calls),
                state=_dedupe(route_state),
                styles=[],
                assets=[],
                evidence=_dedupe_evidence([item.evidence for item in route_sources]),
            )
        )
    for component in components:
        if any(item.page == component.path or component.name in item.components for item in maps):
            continue
        component_calls = [call.endpoint for call in api_calls if call.path == component.path]
        component_state = [
            f"{state.library}:{state.name}"
            for state in state_usages
            if state.source == component.path
        ]
        if component_calls or component_state:
            maps.append(
                FrontendMapFact(
                    route="",
                    page=None,
                    components=[component.name],
                    api_calls=_dedupe(component_calls),
                    state=_dedupe(component_state),
                    styles=[],
                    assets=[],
                    evidence=[component.evidence],
                )
            )
    return maps


def _frontend_routes_by_route(routes: list[FrontendRouteFact]) -> dict[str, list[FrontendRouteFact]]:
    grouped: dict[str, list[FrontendRouteFact]] = {}
    for route in routes:
        if route.framework == "static-site":
            continue
        grouped.setdefault(route.route, []).append(route)
    return grouped


def _primary_route_source(routes: list[FrontendRouteFact]) -> FrontendRouteFact | None:
    if not routes:
        return None
    return next((route for route in routes if route.path.replace("\\", "/").endswith("+page.svelte")), routes[0])


def _compatible_route_sources(page: PageFact, routes: list[FrontendRouteFact]) -> list[FrontendRouteFact]:
    if page.kind == "static-page" and page.template_engine is None:
        return [
            route
            for route in routes
            if route.path == page.path or route.framework == "static-site"
        ]
    return routes


def _route_group_dir(path: str) -> str:
    normalized = path.replace("\\", "/")
    return normalized.rsplit("/", 1)[0] if "/" in normalized else ""


def _allow_route_group_fallback(path: str) -> bool:
    name = Path(path.replace("\\", "/")).name.lower()
    if name in {"router.js", "router.ts"}:
        return False
    if name.endswith(".py"):
        return False
    return not name.endswith((".routes.ts", ".routes.js", ".routing.ts", ".routing.js"))


def _belongs_to_route_group(route_dir: str, path: str) -> bool:
    if not route_dir:
        return False
    normalized = path.replace("\\", "/")
    prefix = f"{route_dir.rstrip('/')}/"
    if not normalized.startswith(prefix):
        return False
    remainder = normalized[len(prefix) :]
    return bool(remainder) and "/" not in remainder


def _dedupe_evidence(items: list[Evidence]) -> list[Evidence]:
    seen: set[tuple[str, int | None, str]] = set()
    result: list[Evidence] = []
    for item in items:
        key = (item.file, item.line_start, item.kind)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _extract_page(file_fact: FileFact, source: str) -> PageFact:
    engine = _template_engine(file_fact, source)
    title_match = TITLE_RE.search(source)
    title = " ".join(title_match.group("title").split()) if title_match else None
    return PageFact(
        path=file_fact.path,
        route=_page_route(file_fact.path, source),
        title=title,
        kind="template-page" if engine else "static-page",
        template_engine=engine,
        evidence=Evidence(file=file_fact.path, kind="page", line_start=1, line_end=1),
    )


def _extract_astro_content_page(file_fact: FileFact, source: str) -> PageFact:
    return PageFact(
        path=file_fact.path,
        route=_astro_content_page_route(file_fact.path) or _page_route(file_fact.path, source),
        title=_frontmatter_title(source),
        kind="content-page",
        template_engine="astro-content",
        evidence=Evidence(file=file_fact.path, kind="page", line_start=1, line_end=1),
    )


def _extract_sveltekit_page(file_fact: FileFact, source: str) -> PageFact:
    title_match = TITLE_RE.search(source)
    title = " ".join(title_match.group("title").split()) if title_match else None
    return PageFact(
        path=file_fact.path,
        route=_sveltekit_route_for_component(file_fact.path) or "/",
        title=title,
        kind="sveltekit-page",
        template_engine="svelte",
        evidence=Evidence(file=file_fact.path, kind="page", line_start=1, line_end=1),
    )


def _is_sveltekit_page_component(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return normalized.endswith("/+page.svelte") or normalized == "+page.svelte"


def _extract_streamlit_page(file_fact: FileFact, source: str, is_main: bool) -> PageFact:
    title, title_line = _streamlit_title(source)
    evidence_line = title_line or _streamlit_signal_line(source)
    return PageFact(
        path=file_fact.path,
        route=_streamlit_route(file_fact.path, is_main),
        title=title,
        kind="streamlit-page",
        template_engine="streamlit",
        evidence=Evidence(
            file=file_fact.path,
            kind="page",
            line_start=evidence_line,
            line_end=evidence_line,
        ),
    )


def _streamlit_main_paths(root: Path, files: list[FileFact]) -> set[str]:
    candidates: list[tuple[tuple[int, str], str]] = []
    for file_fact in files:
        if file_fact.language != "python" or file_fact.role in {"test", "sample", "generated", "documentation"}:
            continue
        source = _read(root, file_fact)
        if not _looks_like_streamlit_source(source):
            continue
        candidates.append((_streamlit_main_score(file_fact.path), file_fact.path))
    if not candidates:
        return set()
    return {sorted(candidates, key=lambda item: item[0])[0][1]}


def _streamlit_main_score(path: str) -> tuple[int, str]:
    normalized = path.replace("\\", "/")
    lower = normalized.lower()
    name = Path(lower).name
    page_penalty = 20 if "/pages/" in f"/{lower}" or lower.startswith("pages/") else 0
    cleaned_name = re.sub(r"^\d+[_\-\s]+", "", name)
    priority = {
        "streamlit_app.py": 0,
        "app.py": 1,
        "home.py": 2,
        "homepage.py": 2,
        "main.py": 3,
    }.get(cleaned_name, 8)
    return (page_penalty + priority + lower.count("/"), lower)


def _looks_like_streamlit_source(source: str) -> bool:
    return bool(
        re.search(r"^\s*(?:import\s+streamlit\b|from\s+streamlit\s+import\b)", source, re.MULTILINE)
        or re.search(r"\bstreamlit\.", source)
        or re.search(
            r"\bst\."
            r"(?:set_page_config|title|header|write|markdown|sidebar|session_state|"
            r"text_input|button|chat_input)\b",
            source,
        )
    )


def _streamlit_title(source: str) -> tuple[str | None, int | None]:
    config_match = STREAMLIT_PAGE_CONFIG_RE.search(source)
    if config_match:
        title_match = STREAMLIT_PAGE_TITLE_RE.search(config_match.group("body"))
        if title_match:
            line = _line_for_offset(source, config_match.start() + title_match.start())
            return _clean_streamlit_title(title_match.group("title")), line
    title_match = STREAMLIT_TITLE_RE.search(source)
    if title_match:
        line = _line_for_offset(source, title_match.start())
        return _clean_streamlit_title(title_match.group("title")), line
    return None, None


def _clean_streamlit_title(title: str) -> str:
    return " ".join(title.split()).strip()


def _streamlit_signal_line(source: str) -> int:
    match = re.search(
        r"^\s*(?:import\s+streamlit\b|from\s+streamlit\s+import\b)|"
        r"\bst\.(?:set_page_config|title|header|write)\b|\bstreamlit\.",
        source,
        re.MULTILINE,
    )
    return _line_for_offset(source, match.start()) if match else 1


def _streamlit_route(path: str, is_main: bool) -> str:
    if is_main:
        return "/"
    normalized = path.replace("\\", "/")
    lower = normalized.lower()
    if lower.startswith("pages/"):
        route_part = normalized[len("pages/") :]
    elif "/pages/" in lower:
        index = lower.index("/pages/") + len("/pages/")
        route_part = normalized[index:]
    else:
        route_part = Path(normalized).name
    stem = re.sub(r"\.py$", "", route_part, flags=re.IGNORECASE)
    slug_parts = [_streamlit_slug_part(part) for part in stem.split("/")]
    slug = "/".join(part for part in slug_parts if part)
    return _ensure_route(slug or "page")


def _streamlit_slug_part(value: str) -> str:
    value = re.sub(r"^\d+[_\-\s]+", "", value)
    return re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()


def _extract_gradio_page(file_fact: FileFact, source: str, is_main: bool) -> PageFact:
    title, title_line = _gradio_title(source)
    evidence_line = title_line or _gradio_signal_line(source)
    return PageFact(
        path=file_fact.path,
        route="/" if is_main else _gradio_route(file_fact.path),
        title=title,
        kind="gradio-app",
        template_engine="gradio",
        evidence=Evidence(
            file=file_fact.path,
            kind="page",
            line_start=evidence_line,
            line_end=evidence_line,
        ),
    )


def _gradio_main_paths(root: Path, files: list[FileFact]) -> set[str]:
    candidates: list[tuple[tuple[int, str], str]] = []
    for file_fact in files:
        if file_fact.language != "python" or file_fact.role in {"test", "sample", "generated", "documentation"}:
            continue
        source = _read(root, file_fact)
        if not _looks_like_gradio_source(source):
            continue
        candidates.append((_gradio_main_score(file_fact.path), file_fact.path))
    if not candidates:
        return set()
    return {sorted(candidates, key=lambda item: item[0])[0][1]}


def _gradio_main_score(path: str) -> tuple[int, str]:
    normalized = path.replace("\\", "/")
    lower = normalized.lower()
    name = Path(lower).name
    priority = {
        "app.py": 0,
        "gradio_app.py": 1,
        "demo.py": 2,
        "main.py": 3,
        "run.py": 4,
    }.get(name, 8)
    return (priority + lower.count("/"), lower)


def _looks_like_gradio_source(source: str) -> bool:
    return bool(
        re.search(r"\bgr\.(?:Interface|Blocks|ChatInterface|TabbedInterface|load)\b", source)
        or re.search(
            r"\bgradio\.(?:Interface|Blocks|ChatInterface|TabbedInterface|load)\b",
            source,
        )
    )


def _gradio_title(source: str) -> tuple[str | None, int | None]:
    for app_match in GRADIO_APP_CALL_RE.finditer(source):
        title_match = GRADIO_TITLE_RE.search(app_match.group("body"))
        if title_match:
            line = _line_for_offset(source, app_match.start("body") + title_match.start())
            return _clean_gradio_title(title_match.group("title")), line
    markdown_match = GRADIO_MARKDOWN_TITLE_RE.search(source)
    if markdown_match:
        line = _line_for_offset(source, markdown_match.start())
        return _clean_gradio_title(markdown_match.group("title")), line
    return None, None


def _clean_gradio_title(title: str) -> str:
    return " ".join(title.split()).strip()


def _gradio_signal_line(source: str) -> int:
    match = re.search(
        r"^\s*(?:import\s+gradio\b|from\s+gradio\s+import\b)|"
        r"\bgr\.(?:Interface|Blocks|ChatInterface|TabbedInterface|load)\b|\bgradio\.",
        source,
        re.MULTILINE,
    )
    return _line_for_offset(source, match.start()) if match else 1


def _gradio_route(path: str) -> str:
    stem = Path(path.replace("\\", "/")).stem
    slug = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()
    return _ensure_route(slug or "app")


def _extract_dash_page(file_fact: FileFact, source: str, is_main: bool) -> PageFact:
    title, title_line = _dash_title(source)
    evidence_line = title_line or _dash_signal_line(source)
    return PageFact(
        path=file_fact.path,
        route="/" if is_main else _dash_route(file_fact.path),
        title=title,
        kind="dash-app",
        template_engine="dash",
        evidence=Evidence(
            file=file_fact.path,
            kind="page",
            line_start=evidence_line,
            line_end=evidence_line,
        ),
    )


def _dash_main_paths(root: Path, files: list[FileFact]) -> set[str]:
    candidates: list[tuple[tuple[int, str], str]] = []
    for file_fact in files:
        if file_fact.language != "python" or file_fact.role in {"test", "sample", "generated", "documentation"}:
            continue
        source = _read(root, file_fact)
        if not _looks_like_dash_source(source):
            continue
        candidates.append((_dash_main_score(file_fact.path), file_fact.path))
    if not candidates:
        return set()
    return {sorted(candidates, key=lambda item: item[0])[0][1]}


def _dash_main_score(path: str) -> tuple[int, str]:
    normalized = path.replace("\\", "/")
    lower = normalized.lower()
    name = Path(lower).name
    priority = {
        "app.py": 0,
        "dash_app.py": 1,
        "dashboard.py": 2,
        "main.py": 3,
        "usage.py": 4,
        "run.py": 5,
    }.get(name, 8)
    return (priority + lower.count("/"), lower)


def _looks_like_dash_source(source: str) -> bool:
    return bool(
        re.search(r"\b(?:dash\.)?Dash\s*\(", source)
        or re.search(r"\bapp\.layout\s*=", source)
        or re.search(r"@\s*app\.callback\s*\(", source)
    )


def _dash_title(source: str) -> tuple[str | None, int | None]:
    app_match = DASH_APP_CALL_RE.search(source)
    if app_match:
        title_match = DASH_TITLE_RE.search(app_match.group("body"))
        if title_match:
            line = _line_for_offset(source, app_match.start("body") + title_match.start())
            return _clean_dash_title(title_match.group("title")), line
    heading_match = DASH_HEADING_RE.search(source)
    if heading_match:
        line = _line_for_offset(source, heading_match.start())
        return _clean_dash_title(heading_match.group("title")), line
    return None, None


def _clean_dash_title(title: str) -> str:
    return " ".join(title.split()).strip()


def _dash_signal_line(source: str) -> int:
    match = re.search(
        r"\b(?:dash\.)?Dash\s*\(|\bapp\.layout\s*=|@\s*app\.callback\s*\(",
        source,
        re.MULTILINE,
    )
    return _line_for_offset(source, match.start()) if match else 1


def _dash_route(path: str) -> str:
    stem = Path(path.replace("\\", "/")).stem
    slug = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()
    return _ensure_route(slug or "dash")


def _extract_panel_page(file_fact: FileFact, source: str, is_main: bool) -> PageFact:
    title, title_line = _panel_title(source)
    evidence_line = title_line or _panel_signal_line(source)
    return PageFact(
        path=file_fact.path,
        route="/" if is_main else _panel_route(file_fact.path),
        title=title,
        kind="panel-app",
        template_engine="panel",
        evidence=Evidence(
            file=file_fact.path,
            kind="page",
            line_start=evidence_line,
            line_end=evidence_line,
        ),
    )


def _panel_main_paths(root: Path, files: list[FileFact]) -> set[str]:
    candidates: list[tuple[tuple[int, str], str]] = []
    for file_fact in files:
        if file_fact.language != "python" or file_fact.role in {"test", "sample", "generated", "documentation"}:
            continue
        source = _read(root, file_fact)
        if not _looks_like_panel_app_source(source):
            continue
        candidates.append((_panel_main_score(file_fact.path), file_fact.path))
    if not candidates:
        return set()
    return {sorted(candidates, key=lambda item: item[0])[0][1]}


def _panel_main_score(path: str) -> tuple[int, str]:
    normalized = path.replace("\\", "/")
    lower = normalized.lower()
    name = Path(lower).name
    priority = {
        "app.py": 0,
        "panel_app.py": 1,
        "dashboard.py": 2,
        "main.py": 3,
    }.get(name, 8)
    return (priority + lower.count("/"), lower)


def _looks_like_panel_app_source(source: str) -> bool:
    return bool(
        re.search(r"\.servable\s*\(", source)
        or re.search(r"\bpn\.serve\s*\(|\bpanel\.serve\s*\(", source)
    ) and bool(
        re.search(r"^\s*(?:import\s+panel\b|from\s+panel\s+import\b)", source, re.MULTILINE)
        or re.search(r"\bpn\.", source)
    )


def _panel_title(source: str) -> tuple[str | None, int | None]:
    title_match = PANEL_TITLE_RE.search(source)
    if title_match:
        line = _line_for_offset(source, title_match.start())
        return _clean_panel_title(title_match.group("title")), line
    markdown_match = PANEL_MARKDOWN_TITLE_RE.search(source)
    if markdown_match:
        line = _line_for_offset(source, markdown_match.start())
        return _clean_panel_title(markdown_match.group("title")), line
    return None, None


def _clean_panel_title(title: str) -> str:
    return " ".join(title.split()).strip()


def _panel_signal_line(source: str) -> int:
    match = re.search(
        r"\.servable\s*\(|\bpn\.serve\s*\(|\bpanel\.serve\s*\(|"
        r"^\s*(?:import\s+panel\b|from\s+panel\s+import\b)",
        source,
        re.MULTILINE,
    )
    return _line_for_offset(source, match.start()) if match else 1


def _panel_route(path: str) -> str:
    stem = Path(path.replace("\\", "/")).stem
    slug = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()
    return _ensure_route(slug or "panel")


def _extract_forms(file_fact: FileFact, source: str) -> list[FormFact]:
    forms: list[FormFact] = []
    for match in FORM_TAG_RE.finditer(source):
        raw_attrs = match.group("attrs")
        attrs = _attrs(raw_attrs)
        action = _blade_action_from_attrs(raw_attrs) or attrs.get("action") or attrs.get("th:action") or attrs.get("@action") or _template_form_action(attrs)
        action = _normalize_template_action(action)
        if not action and attrs.get("phx-submit"):
            action = f"phx-submit:{attrs['phx-submit']}"
        method = attrs.get("method", "GET").upper() if "method" in attrs else ("LIVE_EVENT" if attrs.get("phx-submit") else None)
        if file_fact.language == "svelte":
            action = _sveltekit_form_action(file_fact.path, action, method)
        form_end = _form_body_end(source, match.end())
        body = source[match.end() : form_end if form_end >= 0 else match.end() + 1200]
        fields = _form_fields(body)
        if not action and not method and not fields:
            continue
        line = _line_for_offset(source, match.start())
        forms.append(
            FormFact(
                source=file_fact.path,
                method=method,
                action=action,
                fields=fields,
                evidence=Evidence(file=file_fact.path, kind="form", line_start=line, line_end=line),
            )
        )
    if file_fact.language in {"erb", "ruby-template"} or file_fact.path.lower().endswith((".erb", ".rsb", ".builder", ".ruby")):
        forms.extend(_extract_rails_helper_forms(file_fact, source))
    if file_fact.language == "haml" or file_fact.path.lower().endswith(".haml"):
        forms.extend(_extract_haml_rails_helper_forms(file_fact, source))
    return forms


def _form_body_end(source: str, start: int) -> int:
    ends = [index for marker in ("</form>", "</.form>") if (index := source.find(marker, start)) >= 0]
    return min(ends) if ends else -1


def _extract_php_forms(file_fact: FileFact, source: str) -> list[FormFact]:
    forms: list[FormFact] = []
    for match in re.finditer(r"<form\b", source, re.IGNORECASE):
        if _offset_is_php_comment(source, match.start()):
            continue
        tag_end = _html_tag_end(source, match.start())
        if tag_end is None:
            continue
        attrs = _attrs(source[match.end() : tag_end])
        action = _normalize_template_action(attrs.get("action") or _template_form_action(attrs))
        method = attrs.get("method", "GET").upper() if "method" in attrs else None
        form_end = source.find("</form>", tag_end)
        body = source[tag_end + 1 : form_end if form_end >= 0 else tag_end + 1800]
        line = _line_for_offset(source, match.start())
        forms.append(
            FormFact(
                source=file_fact.path,
                method=method,
                action=action,
                fields=_php_form_fields(body),
                evidence=Evidence(file=file_fact.path, kind="form", line_start=line, line_end=line),
            )
        )
    return forms


def _php_form_fields(source: str) -> list[str]:
    fields: list[str] = []
    for match in re.finditer(r"<(?:input|select|textarea)\b", source, re.IGNORECASE):
        if _offset_is_php_comment(source, match.start()):
            continue
        tag_end = _html_tag_end(source, match.start())
        if tag_end is None:
            continue
        attrs = _attrs(source[match.end() : tag_end])
        name = _clean_form_field_name(attrs.get("name") or attrs.get("id"))
        if name:
            fields.append(name)
    return _dedupe(fields)


def _html_tag_end(source: str, offset: int) -> int | None:
    quote: str | None = None
    escape = False
    for index in range(offset, len(source)):
        char = source[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char == ">":
            return index
    return None


def _looks_like_php_template_source(source: str) -> bool:
    return re.search(r"<(?:form|a|script|link|img|input|select|textarea)\b", source, re.IGNORECASE) is not None


def _offset_is_php_comment(source: str, offset: int) -> bool:
    block_start = source.rfind("/*", 0, offset)
    block_end = source.rfind("*/", 0, offset)
    if block_start > block_end:
        return True
    line_start = source.rfind("\n", 0, offset) + 1
    prefix = source[line_start:offset].strip()
    return prefix.startswith("//") or prefix.startswith("#")


def _extract_jsx_forms(file_fact: FileFact, source: str) -> list[FormFact]:
    forms: list[FormFact] = []
    for match in JSX_FORM_TAG_RE.finditer(source):
        raw_attrs = match.group("attrs")
        method = (_jsx_attr_value(raw_attrs, "method") or "GET").strip("'\"`").upper()
        action = _normalize_jsx_action(_jsx_attr_value(raw_attrs, "action")) or _remix_form_default_action(file_fact.path)
        body = _jsx_form_body(source, match)
        line = _line_for_offset(source, match.start())
        forms.append(
            FormFact(
                source=file_fact.path,
                method=method,
                action=action,
                fields=_form_fields(body),
                evidence=Evidence(file=file_fact.path, kind="form", line_start=line, line_end=line),
            )
        )
    return forms


def _jsx_attr_value(attrs: str, name: str) -> str | None:
    quoted = re.search(rf"\b{re.escape(name)}\s*=\s*(?P<quote>['\"])(?P<value>.*?)(?P=quote)", attrs, re.DOTALL)
    if quoted:
        return quoted.group("value")
    braced = re.search(rf"\b{re.escape(name)}\s*=\s*\{{", attrs)
    if not braced:
        return None
    start = braced.end()
    depth = 1
    for index, char in enumerate(attrs[start:], start=start):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return attrs[start:index].strip()
    return attrs[start:].strip()


def _jsx_form_body(source: str, match: re.Match[str]) -> str:
    tag = re.escape(match.group("tag"))
    close_match = re.search(rf"</\s*{tag}\s*>", source[match.end() :], re.IGNORECASE)
    if close_match:
        return source[match.end() : match.end() + close_match.start()]
    return source[match.end() : match.end() + 1800]


def _normalize_jsx_action(action: str | None) -> str | None:
    if not action:
        return None
    cleaned = " ".join(action.strip().split())
    if len(cleaned) >= 2 and cleaned[0] in {"'", '"', "`"} and cleaned[-1] == cleaned[0]:
        cleaned = cleaned[1:-1]
    if "${" in cleaned:
        cleaned = re.sub(r"\$\{(?P<expr>[^}]+)\}", lambda match: f":{_jsx_path_param_name(match.group('expr'))}", cleaned)
    cleaned = _normalize_template_action(cleaned)
    if cleaned.startswith(("/", "http://", "https://")):
        return cleaned
    if cleaned in {"", "null", "undefined"}:
        return None
    return f"dynamic:{cleaned[:80]}"


def _jsx_path_param_name(expression: str) -> str:
    names = re.findall(r"[A-Za-z_$][\w$]*", expression.replace("?.", "."))
    ignored = {"this", "props", "state", "params", "param", "user", "article", "item", "data"}
    for name in reversed(names):
        cleaned = name.strip("$")
        if cleaned and cleaned not in ignored:
            return cleaned
    return "value"


def _remix_form_default_action(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    lower = normalized.lower()
    marker = "app/routes/"
    if marker not in lower or not lower.endswith((".tsx", ".jsx", ".ts", ".js")):
        return None
    route_file = normalized[lower.index(marker) + len(marker) :]
    route_part = route_file.rsplit(".", 1)[0]
    route_part = route_part.removesuffix("/route").removesuffix("/index")
    segments: list[str] = []
    for segment in route_part.split("."):
        if segment in {"index", "_index"}:
            continue
        if segment.startswith("_"):
            continue
        if segment == "$":
            segments.append("*")
        elif segment.startswith("$"):
            segments.append(f":{segment[1:]}")
        else:
            segments.append(segment)
    return "/" + "/".join(part.strip("/") for part in segments if part.strip("/")) if segments else "/"


def _is_jsx_markup_file(file_fact: FileFact) -> bool:
    return file_fact.path.replace("\\", "/").lower().endswith((".tsx", ".jsx"))


def _extract_rails_helper_forms(file_fact: FileFact, source: str) -> list[FormFact]:
    forms: list[FormFact] = []
    for match in RAILS_FORM_HELPER_RE.finditer(source):
        args = match.group("args")
        method = _rails_form_method(args)
        action = _rails_form_action(match.group("helper"), args)
        form_end = source.find("<% end %>", match.end())
        body = source[match.end() : form_end if form_end >= 0 else match.end() + 1800]
        fields = _dedupe([*_rails_form_fields(args), *_rails_form_fields(body)])
        line = _line_for_offset(source, match.start())
        forms.append(
            FormFact(
                source=file_fact.path,
                method=method,
                action=action,
                fields=fields,
                evidence=Evidence(file=file_fact.path, kind="form", line_start=line, line_end=line),
            )
        )
    return forms


def _extract_haml_rails_helper_forms(file_fact: FileFact, source: str) -> list[FormFact]:
    forms: list[FormFact] = []
    matches = list(HAML_RAILS_FORM_HELPER_RE.finditer(source))
    for index, match in enumerate(matches):
        args = match.group("args")
        method = _rails_form_method(args)
        action = _rails_form_action(match.group("helper"), args)
        body_end = matches[index + 1].start() if index + 1 < len(matches) else min(len(source), match.end() + 2400)
        body = source[match.end() : body_end]
        fields = _dedupe([*_rails_form_fields(args), *_rails_form_fields(body)])
        line = _line_for_offset(source, match.start())
        forms.append(
            FormFact(
                source=file_fact.path,
                method=method,
                action=action,
                fields=fields,
                evidence=Evidence(file=file_fact.path, kind="form", line_start=line, line_end=line),
            )
        )
    return forms


def _rails_form_method(args: str) -> str:
    match = re.search(r"(?:method:|:method\s*=>)\s*['\"]?:?([A-Za-z_]\w*)['\"]?", args)
    if match:
        return match.group(1).upper()
    return "POST"


def _rails_form_action(helper: str, args: str) -> str | None:
    url_match = re.search(r"(?:url:|:url\s*=>)\s*(?P<value>[^,\n)]+)", args)
    if url_match:
        return _rails_action_value(url_match.group("value"))
    if helper.lower().endswith("form_tag"):
        first = args.split(",", 1)[0].strip()
        return _rails_action_value(first) if first else None
    return None


def _rails_action_value(value: str) -> str | None:
    cleaned = value.strip().strip("{}()").strip()
    if not cleaned:
        return None
    string_match = re.match(r"['\"]([^'\"]+)['\"]", cleaned)
    if string_match:
        return _normalize_template_action(string_match.group(1))
    helper_match = re.match(r"([A-Za-z_]\w*(?:_path|_url))\b", cleaned)
    if helper_match:
        return f"rails-helper:{helper_match.group(1)}"
    action_match = re.search(r"(?:action:|:action\s*=>)\s*['\"]([^'\"]+)['\"]", cleaned)
    if action_match:
        return f"rails-action:{action_match.group(1)}"
    return "rails-dynamic-action" if cleaned not in {"{}", "nil"} else None


def _rails_form_fields(source: str) -> list[str]:
    fields: list[str] = []
    for match in RAILS_FIELD_RE.finditer(source):
        field = _clean_rails_field_name(match.group("name"))
        if field:
            fields.append(field)
    for match in RAILS_TAG_FIELD_RE.finditer(source):
        field = _clean_rails_field_name(match.group("name"))
        if field:
            fields.append(field)
    return _dedupe(fields)


def _clean_rails_field_name(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().strip("'\"")
    return cleaned or None


def _blade_action_from_attrs(attrs: str) -> str | None:
    for pattern in (
        r"\baction\s*=\s*\"(?P<value>{{\s*(?:url|route)\s*\(.*?\)\s*}})\"",
        r"\baction\s*=\s*'(?P<value>{{\s*(?:url|route)\s*\(.*?\)\s*}})'",
    ):
        match = re.search(pattern, attrs, re.DOTALL)
        if match:
            return match.group("value")
    return None


def _sveltekit_form_action(path: str, action: str | None, method: str | None) -> str | None:
    route = _sveltekit_route_for_component(path)
    if route is None:
        return action
    if action and action.startswith("?/"):
        return f"{route}?/{action[2:]}" if route != "/" else f"/?/{action[2:]}"
    if not action and method == "POST":
        return route
    return action


def _sveltekit_route_for_component(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    route_part = None
    if normalized.startswith("src/routes/"):
        route_part = normalized.removeprefix("src/routes/")
    elif "/src/routes/" in normalized:
        route_part = normalized.split("/src/routes/", 1)[1]
    elif "/routes/" in normalized:
        route_part = normalized.split("/routes/", 1)[1]
    if route_part is None:
        return None
    parts = route_part.split("/")[:-1]
    cleaned = []
    for part in parts:
        if part.startswith("(") and part.endswith(")"):
            continue
        if part.startswith("[...") and part.endswith("]"):
            cleaned.append(f":{part[4:-1]}*")
        elif part.startswith("[") and part.endswith("]"):
            cleaned.append(f":{part[1:-1]}")
        else:
            cleaned.append(part)
    route = "/".join(part for part in cleaned if part and part != "index")
    return f"/{route}" if route else "/"


def _extract_page_assets(file_fact: FileFact, source: str) -> list[AssetFact]:
    assets: list[AssetFact] = []
    for match in TAG_RE.finditer(source):
        tag = match.group("tag").lower()
        attrs = _attrs(match.group("attrs"))
        candidates: list[tuple[str, str, str]] = []
        if tag == "script" and attrs.get("src"):
            candidates.append((attrs["src"], "script", "script-src"))
        if tag == "script" and attrs.get("asp-fallback-src"):
            candidates.append((attrs["asp-fallback-src"], "script", "asp-fallback-src"))
        elif tag == "link" and attrs.get("href"):
            rel = attrs.get("rel", "").lower()
            kind = "style" if "stylesheet" in rel else "link"
            candidates.append((attrs["href"], kind, "link-href"))
        if tag == "link" and attrs.get("asp-fallback-href"):
            candidates.append((attrs["asp-fallback-href"], "style", "asp-fallback-href"))
        elif tag in {"img", "source"} and attrs.get("src"):
            candidates.append((attrs["src"], "image", f"{tag}-src"))
        for asset_path, asset_kind, usage_kind in candidates:
            if not _is_static_asset_reference(asset_path):
                continue
            line = _line_for_offset(source, match.start())
            assets.append(
                AssetFact(
                    source=file_fact.path,
                    asset_path=asset_path,
                    asset_kind=asset_kind,
                    usage_kind=usage_kind,
                    evidence=Evidence(file=file_fact.path, kind="asset", line_start=line, line_end=line),
                )
            )
    return assets


def _extract_style(file_fact: FileFact, source: str) -> StyleFact:
    selectors = _dedupe(
        " ".join(match.group("selector").split())
        for match in CSS_SELECTOR_RE.finditer(source)
        if match.group("selector").strip() and not match.group("selector").lstrip().startswith("@")
    )
    return StyleFact(
        path=file_fact.path,
        selectors=selectors[:100],
        classes=_dedupe(match.group("class") for match in CSS_CLASS_RE.finditer(source))[:100],
        ids=_dedupe(match.group("id") for match in CSS_ID_RE.finditer(source))[:100],
        css_variables=_dedupe(match.group("var") for match in CSS_VAR_RE.finditer(source))[:100],
        imports=_dedupe(match.group("value") for match in CSS_IMPORT_RE.finditer(source)),
        asset_urls=_dedupe(match.group("value") for match in CSS_URL_RE.finditer(source)),
        evidence=Evidence(file=file_fact.path, kind="style", line_start=1, line_end=1),
    )


def _style_assets(style: StyleFact) -> list[AssetFact]:
    assets: list[AssetFact] = []
    for imported in style.imports:
        assets.append(
            AssetFact(
                source=style.path,
                asset_path=imported,
                asset_kind="style",
                usage_kind="css-import",
                evidence=style.evidence,
            )
        )
    for asset_url in style.asset_urls:
        assets.append(
            AssetFact(
                source=style.path,
                asset_path=asset_url,
                asset_kind=_asset_kind(asset_url),
                usage_kind="css-url",
                evidence=style.evidence,
            )
        )
    return assets


def _extract_standalone_asset(file_fact: FileFact) -> AssetFact:
    return AssetFact(
        source=file_fact.path,
        asset_path=file_fact.path,
        asset_kind=_asset_kind(file_fact.path),
        usage_kind="static-asset",
        evidence=Evidence(file=file_fact.path, kind="asset", line_start=1, line_end=1),
    )


def _extract_api_calls(file_fact: FileFact, source: str, context: str) -> list[ApiCallFact]:
    calls: list[ApiCallFact] = []
    for match in BLADE_ROUTE_FETCH_RE.finditer(source):
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=f"route:{match.group('name')}",
                method=_fetch_method(match.group("args")),
                client="fetch",
                trigger="runtime",
                context=context,
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    for match in BLADE_ROUTE_AXIOS_RE.finditer(source):
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=f"route:{match.group('name')}",
                method=match.group("method").upper(),
                client="axios",
                trigger="runtime",
                context=context,
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    for match in FETCH_RE.finditer(source):
        endpoint = match.group("endpoint")
        if _is_template_endpoint_fragment(endpoint):
            continue
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=endpoint,
                method=_fetch_method(match.group("args")),
                client="fetch",
                trigger="runtime",
                context=context,
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    for match in AXIOS_RE.finditer(source):
        endpoint = match.group("endpoint")
        if _is_template_endpoint_fragment(endpoint):
            continue
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=endpoint,
                method=match.group("method").upper(),
                client="axios",
                trigger="runtime",
                context=context,
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
                context=context,
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    for match in EVENTSOURCE_RE.finditer(source):
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=_httpish_endpoint(match.group("endpoint")),
                method="STREAM",
                client="EventSource",
                trigger="runtime",
                context=context,
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    websocket_client_seen = False
    for match in WEBSOCKET_CLIENT_RE.finditer(source):
        websocket_client_seen = True
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=_websocket_endpoint(match.group("endpoint")),
                method="WS",
                client="WebSocket",
                trigger="runtime",
                context=context,
                evidence=Evidence(
                    file=file_fact.path,
                    kind="frontend-api-call",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.end()),
                ),
            )
        )
    if websocket_client_seen:
        for match in WEBSOCKET_SEND_RE.finditer(source):
            calls.append(
                ApiCallFact(
                    path=file_fact.path,
                    endpoint="websocket#message",
                    method="EVENT",
                    client="WebSocket",
                    trigger="runtime",
                    context=context,
                    evidence=Evidence(
                        file=file_fact.path,
                        kind="frontend-api-call",
                        line_start=_line_for_offset(source, match.start()),
                        line_end=_line_for_offset(source, match.end()),
                    ),
                )
            )
    return calls


def _is_template_endpoint_fragment(endpoint: str) -> bool:
    value = endpoint.strip()
    return value.startswith(("{{", "{%", "<%")) or " route(" in value or value.startswith("@{")


def _attrs(source: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for match in ATTR_RE.finditer(source):
        name = match.group("name").lower()
        value = match.group("value") or match.group("brace_value") or ""
        attrs[name] = " ".join(value.split())
    return attrs


def _form_fields(source: str) -> list[str]:
    fields: list[str] = []
    for match in INPUT_RE.finditer(source):
        attrs = _attrs(match.group("attrs"))
        if attrs.get("asp-for"):
            name = _clean_razor_form_field_name(attrs.get("asp-for"))
        else:
            name = _clean_form_field_name(
                attrs.get("name")
                or attrs.get("th:field")
                or attrs.get("data-th-field")
                or attrs.get("id")
            )
        if name:
            fields.append(name)
    for match in HEEX_INPUT_RE.finditer(source):
        attrs = _attrs(match.group("attrs"))
        name = _clean_heex_form_field_name(attrs.get("field") or attrs.get("name") or attrs.get("id"))
        if name:
            fields.append(name)
    for match in RAZOR_FIELD_TAG_RE.finditer(source):
        attrs = _attrs(match.group("attrs"))
        name = _clean_razor_form_field_name(attrs.get("asp-for") or attrs.get("asp-input"))
        if name:
            fields.append(name)
    for match in RAZOR_HTML_HELPER_FIELD_RE.finditer(source):
        name = _clean_razor_form_field_name(match.group("name"))
        if name:
            fields.append(name)
    return _dedupe(fields)


def _clean_heex_form_field_name(value: str | None) -> str | None:
    cleaned = _clean_form_field_name(value)
    if not cleaned:
        return None
    match = re.fullmatch(
        r"(?:[A-Za-z_]\w*|@[A-Za-z_]\w*)\s*\[\s*:(?P<name>[A-Za-z_]\w*)\s*\]",
        cleaned,
    )
    if match:
        return match.group("name")
    return cleaned.lstrip(":") or None


def _clean_razor_form_field_name(value: str | None) -> str | None:
    cleaned = _clean_form_field_name(value)
    if not cleaned:
        return None
    cleaned = cleaned.strip()
    if cleaned.startswith("@(") and cleaned.endswith(")"):
        cleaned = cleaned[2:-1].strip()
    cleaned = cleaned.lstrip("@")
    if cleaned.startswith("Model."):
        cleaned = cleaned.removeprefix("Model.")
    cleaned = re.sub(r"\[(?:item|i|index)\]", "[]", cleaned)
    if re.search(r"\s|=>", cleaned):
        return None
    return cleaned or None


def _clean_form_field_name(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] in {"'", '"', "`"} and cleaned[-1] == cleaned[0]:
        cleaned = cleaned[1:-1].strip()
    expression = re.fullmatch(r"[*$]?\{\s*(?P<name>[^}]+?)\s*\}", cleaned)
    if expression:
        cleaned = expression.group("name").strip()
    if "${" in cleaned or "__" in cleaned:
        return None
    return cleaned or None


def _template_engine(file_fact: FileFact, source: str) -> str | None:
    suffix = Path(file_fact.path).suffix.lower()
    if file_fact.language == "jsp":
        return "jsp"
    if file_fact.language == "razor" or suffix in {".cshtml", ".razor"}:
        return "razor"
    if suffix in {".ftl"}:
        return "freemarker"
    if suffix in {".hbs", ".handlebars"}:
        return "handlebars"
    if suffix in {".mustache"}:
        return "mustache"
    if suffix == ".ejs":
        return "ejs"
    if suffix == ".pug":
        return "pug"
    if suffix == ".twig":
        return "twig"
    if suffix == ".haml":
        return "haml"
    if suffix == ".liquid":
        return "liquid"
    if suffix == ".erb":
        return "erb"
    if suffix in {".eex", ".heex", ".leex"}:
        return "heex" if suffix == ".heex" else "eex"
    if suffix == ".astro":
        return "astro"
    if file_fact.language == "twirl" or file_fact.path.replace("\\", "/").lower().endswith(".scala.html"):
        return "twirl"
    if suffix in {".rsb", ".builder", ".ruby"}:
        return "ruby-template"
    if file_fact.path.replace("\\", "/").lower().endswith(".blade.php"):
        return "blade"
    if "xmlns:th=" in source or re.search(r"\bth:[A-Za-z0-9_-]+\s*=", source):
        return "thymeleaf"
    normalized = file_fact.path.replace("\\", "/").lower()
    if "/templates/" in f"/{normalized}" and re.search(r"{%\s*(?:block|extends|include|load|url|static|csrf_token)\b|{{", source):
        return "django-template"
    return None


def _template_form_action(attrs: dict[str, str]) -> str | None:
    if attrs.get("asp-page"):
        if attrs.get("asp-page-handler"):
            return f"{attrs['asp-page']}?handler={attrs['asp-page-handler']}"
        return attrs["asp-page"]
    controller = attrs.get("asp-controller")
    action = attrs.get("asp-action")
    if controller and action:
        area = attrs.get("asp-area")
        parts = [part for part in (area, controller, action) if part]
        return "/" + "/".join(part.strip("/") for part in parts)
    if action:
        return action
    if attrs.get("asp-page-handler"):
        return f"handler:{attrs['asp-page-handler']}"
    return None


def _normalize_template_action(action: str | None) -> str | None:
    if not action:
        return action
    cleaned = " ".join(action.strip().split())
    thymeleaf_match = re.fullmatch(r"@\{\s*(?P<path>[^}]+?)\s*\}", cleaned)
    if thymeleaf_match:
        path = thymeleaf_match.group("path").split("(", 1)[0].strip()
        return path or None
    if "<?php" in cleaned:
        return _php_dynamic_action(cleaned)
    url_match = re.search(r"{{\s*url\s*\(\s*['\"](?P<path>/[^'\"]*)['\"]", cleaned)
    if url_match:
        return _normalize_laravel_dynamic_path(url_match.group("path"))
    if re.search(r"{{\s*url\s*\(", cleaned):
        return "dynamic:blade-url"
    route_match = re.search(r"{{\s*route\s*\(\s*['\"](?P<name>[^'\"]+)['\"]", cleaned)
    if route_match:
        return f"route:{route_match.group('name')}"
    if re.search(r"{{\s*route\s*\(", cleaned):
        return "dynamic:blade-route"
    return action


def _php_dynamic_action(action: str) -> str:
    variable_match = re.search(r"\$[A-Za-z_]\w*", action)
    if variable_match:
        return f"php-dynamic:{variable_match.group(0)}"
    function_match = re.search(r"\b([A-Za-z_]\w*)\s*\(", action)
    if function_match:
        return f"php-dynamic:{function_match.group(1)}"
    return "php-dynamic"


def _normalize_laravel_dynamic_path(path: str) -> str:
    def replacement(match: re.Match[str]) -> str:
        value = match.group("value").strip().lstrip("$")
        value = value.replace("->", ".").replace("[", ".").replace("]", "")
        value = value.replace("'", "").replace('"', "")
        return "{" + value.strip(".") + "}"

    return re.sub(r"\{\s*\$(?P<value>[^}]+)\}", replacement, path)


def _is_non_routable_template(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    name = Path(normalized).name
    if name == "app.html" and "%sveltekit." in source.lower():
        return True
    if name.endswith((".component.html", ".component.htm")):
        return True
    is_razor = normalized.endswith((".cshtml", ".razor"))
    if is_razor and name.startswith("_"):
        return True
    if normalized.endswith(".razor") and re.search(r"^\ufeff?\s*@page\b", source, re.MULTILINE) is None:
        return True
    if is_razor and (
        "/pages/shared/" in f"/{normalized}"
        or "/views/shared/" in f"/{normalized}"
        or "/shared/components/" in f"/{normalized}"
    ):
        return True
    if normalized.endswith(".astro") and not _is_astro_page_path(normalized):
        return True
    if normalized.endswith(".blade.php") and (
        "/layouts/" in f"/{normalized}"
        or "/parts/" in f"/{normalized}"
        or "/partials/" in f"/{normalized}"
        or "/components/" in f"/{normalized}"
    ):
        return True
    if normalized.endswith(".twig") and (
        name.startswith("_")
        or name in {"base.html.twig", "layout.html.twig"}
        or "/components/" in f"/{normalized}"
        or "/form/" in f"/{normalized}"
    ):
        return True
    if normalized.endswith((".eex", ".heex", ".leex")) and (
        "/components/" in f"/{normalized}"
        or "/layouts/" in f"/{normalized}"
        or name.startswith("_")
        or "component" in name
    ):
        return True
    if normalized.endswith((".hbs", ".handlebars")) and (
        "/app/components/" in f"/{normalized}"
        or "/addon/components/" in f"/{normalized}"
        or "/addon/templates/" in f"/{normalized}"
        or name in {"application.hbs", "application-loading.hbs"}
    ):
        return True
    if normalized.endswith((".mustache", ".hbs", ".handlebars", ".ejs")) and not _looks_like_routable_template(normalized, source):
        return True
    return False


def _looks_like_routable_template(path: str, source: str) -> bool:
    if re.search(r"<(?:!doctype|html|head|body|main|section|article|form|a|script|link|img)\b", source, re.IGNORECASE):
        return True
    normalized = path.replace("\\", "/").lower()
    return any(marker in f"/{normalized}" for marker in ("/views/", "/templates/", "/pages/", "/public/", "/static/"))


def _page_route(path: str, source: str = "") -> str:
    normalized = path.replace("\\", "/")
    if normalized.lower().endswith(".razor"):
        page_match = re.search(r"^\ufeff?\s*@page\s+(?P<quote>['\"])(?P<route>[^'\"]+)(?P=quote)", source, re.MULTILINE)
        if page_match:
            return _ensure_route(page_match.group("route"))
    area_match = re.search(r"(?:^|/)areas/([^/]+)/(?:pages|views)/(.*)$", normalized, re.IGNORECASE)
    if area_match:
        normalized = f"{area_match.group(1)}/{area_match.group(2)}"
    lower = normalized.lower()
    if lower in {"src/index.html", "src/index.htm"}:
        return "/"
    if lower.endswith(".astro"):
        route_part = _astro_route_part(lower)
        if route_part is not None:
            cleaned = _clean_astro_route_part(route_part.rsplit(".", 1)[0])
            return "/" if cleaned == "index" else _ensure_route(cleaned.removesuffix("/index"))
    ember_route = _ember_template_route_part(normalized)
    if ember_route is not None:
        return ember_route
    prefixes = (
        "public/",
        "static/",
        "resources/views/",
        "src/main/resources/static/",
        "src/main/resources/templates/",
        "src/main/webapp/",
        "src/web/pages/",
        "src/web/views/",
        "webapp/",
        "templates/",
        "views/",
    )
    for prefix in prefixes:
        if lower.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break
    else:
        embedded_prefixes = (
            "/src/main/resources/templates/",
            "/src/main/webapp/",
            "/src/web/pages/",
            "/src/web/views/",
            "/resources/views/",
            "/webapp/",
            "/templates/",
            "/views/",
        )
        for marker in embedded_prefixes:
            if marker in lower:
                index = lower.index(marker) + len(marker)
                normalized = normalized[index:]
                break
    stem = normalized[: -len(".blade.php")] if normalized.lower().endswith(".blade.php") else normalized.rsplit(".", 1)[0]
    stem_lower = stem.lower()
    if stem_lower in {"index", "home"}:
        return "/"
    if stem_lower.endswith("/index"):
        return "/" + stem[: -len("/index")].strip("/")
    return "/" + stem.strip("/")


def _ember_template_route_part(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    lower = normalized.lower()
    markers = ("/app/templates/", "/addon/templates/")
    route_part = None
    for marker in markers:
        if marker in lower:
            index = lower.index(marker) + len(marker)
            route_part = normalized[index:]
            break
    if route_part is None:
        if lower.startswith("app/templates/"):
            route_part = normalized[len("app/templates/") :]
        elif lower.startswith("addon/templates/"):
            route_part = normalized[len("addon/templates/") :]
    if route_part is None:
        return None
    stem = route_part.rsplit(".", 1)[0]
    if stem in {"application", "application-loading"}:
        return None
    if stem == "index":
        return "/"
    if stem.endswith("/index"):
        stem = stem[: -len("/index")]
    return _ensure_route(stem.replace(".", "/"))


def _is_astro_page_path(path: str) -> bool:
    route_part = _astro_route_part(path)
    return route_part is not None and not any(part.startswith("_") for part in route_part.split("/"))


def _is_astro_content_page_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return normalized.startswith("src/content/docs/") and normalized.endswith((".md", ".mdx"))


def _astro_content_page_route(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    lower = normalized.lower()
    prefix = "src/content/docs/"
    if not lower.startswith(prefix) or not lower.endswith((".md", ".mdx")):
        return None
    route = normalized[len(prefix) :]
    route = re.sub(r"\.(?:md|mdx)$", "", route, flags=re.IGNORECASE)
    if route.lower().endswith("/index"):
        route = route[: -len("/index")]
    if route.lower() == "index":
        route = ""
    return _ensure_route(route)


def _astro_route_part(path: str) -> str | None:
    marker = "/pages/"
    if path.startswith("pages/"):
        return path.removeprefix("pages/")
    if marker in path:
        return path.split(marker, 1)[1]
    return None


def _clean_astro_route_part(route: str) -> str:
    parts: list[str] = []
    for part in route.split("/"):
        if part in {"index", ""}:
            parts.append(part)
        elif part.startswith("[...") and part.endswith("]"):
            parts.append(f":{part[4:-1]}*")
        elif part.startswith("[") and part.endswith("]"):
            parts.append(f":{part[1:-1]}")
        else:
            parts.append(part)
    return "/".join(parts)


def _frontmatter_title(source: str) -> str | None:
    match = FRONTMATTER_TITLE_RE.search(source)
    if not match:
        return None
    title_match = FRONTMATTER_TITLE_LINE_RE.search(match.group("body"))
    if not title_match:
        return None
    raw = title_match.group("title").strip()
    if len(raw) >= 2 and raw[0] in {"'", '"'} and raw[-1] == raw[0]:
        raw = raw[1:-1]
    return " ".join(raw.split()) or None


def _ensure_route(route: str) -> str:
    stripped = route.strip()
    if not stripped:
        return "/"
    return stripped if stripped.startswith("/") else "/" + stripped


def _is_static_asset_reference(path: str) -> bool:
    stripped = path.strip()
    if not stripped:
        return False
    if stripped.startswith(("@", "{{", "${", "<%", "#")):
        return False
    return True


def _is_frontend_static_asset_file(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    if not (
        normalized.startswith(("public/", "static/", "assets/"))
        or "/public/" in f"/{normalized}"
        or "/static/" in f"/{normalized}"
        or "/assets/" in f"/{normalized}"
        or "/src/main/resources/static/" in f"/{normalized}"
    ):
        return False
    return _asset_kind(normalized) in {"image", "font", "style", "script"}


def _asset_kind(path: str) -> str:
    suffix = Path(path.split("?", 1)[0]).suffix.lower()
    if suffix in {".css", ".scss", ".sass", ".less"}:
        return "style"
    if suffix in {".js", ".mjs", ".ts"}:
        return "script"
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico"}:
        return "image"
    if suffix in {".woff", ".woff2", ".ttf", ".otf"}:
        return "font"
    return "asset"


def _fetch_method(args: str) -> str:
    match = re.search(r"method\s*:\s*['\"](?P<method>[A-Z]+)['\"]", args, re.IGNORECASE)
    return match.group("method").upper() if match else "GET"


def _httpish_endpoint(endpoint: str) -> str:
    value = endpoint.strip()
    if value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        return parsed.path or "/"
    return value


def _websocket_endpoint(endpoint: str) -> str:
    value = endpoint.strip()
    if value.startswith(("ws://", "wss://", "http://", "https://")):
        parsed = urlparse(value)
        return parsed.path or "websocket#connection"
    if value.startswith("/"):
        return value
    return "websocket#connection"


def _read(root: Path, file_fact: FileFact) -> str:
    return (root / file_fact.path).read_text(encoding="utf-8", errors="ignore")


def _line_for_offset(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _dedupe(values: object) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(str(value))
    return result
