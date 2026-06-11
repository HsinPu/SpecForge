from __future__ import annotations

import re
from pathlib import Path

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
}
STYLE_LANGUAGES = {"css", "scss", "sass", "less"}
TITLE_RE = re.compile(r"<title[^>]*>(?P<title>.*?)</title>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<(?P<tag>form|a|script|link|img|source)\b(?P<attrs>[^>]*)>", re.IGNORECASE | re.DOTALL)
ATTR_RE = re.compile(r"(?P<name>[:@\w.-]+)(?:\s*=\s*(?P<quote>['\"])(?P<value>.*?)(?P=quote))?", re.DOTALL)
INPUT_RE = re.compile(r"<(?:input|select|textarea)\b(?P<attrs>[^>]*)>", re.IGNORECASE | re.DOTALL)
FETCH_RE = re.compile(r"\bfetch\(\s*['\"`](?P<endpoint>[^'\"`]+)['\"`](?P<args>[^)]*)\)", re.DOTALL)
AXIOS_RE = re.compile(
    r"\baxios\.(?P<method>get|post|put|delete|patch)\(\s*['\"`](?P<endpoint>[^'\"`]+)['\"`]",
    re.IGNORECASE,
)
CLIENT_CALL_RE = re.compile(
    r"\b(?P<client>api|client|http|request|service)\.(?P<method>get|post|put|delete|patch)"
    r"\(\s*['\"`](?P<endpoint>/[^'\"`]+)['\"`]",
    re.IGNORECASE,
)
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

    for file_fact in files:
        if file_fact.role == "test":
            continue
        if file_fact.language in PAGE_LANGUAGES:
            source = _read(root, file_fact)
            page = _extract_page(file_fact, source)
            pages.append(page)
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
            api_calls.extend(_extract_api_calls(file_fact, source, "inline-script"))
        elif file_fact.language in STYLE_LANGUAGES:
            source = _read(root, file_fact)
            style = _extract_style(file_fact, source)
            styles.append(style)
            assets.extend(_style_assets(style))

    return pages, forms, assets, styles, routes, api_calls


def build_frontend_maps(
    pages: list[PageFact],
    components: list[object],
    api_calls: list[ApiCallFact],
    state_usages: list[object],
    styles: list[StyleFact],
    assets: list[AssetFact],
) -> list[FrontendMapFact]:
    maps: list[FrontendMapFact] = []
    global_styles = [style.path for style in styles[:10]]
    for page in pages:
        page_assets = [asset.asset_path for asset in assets if asset.source == page.path]
        page_calls = [call.endpoint for call in api_calls if call.path == page.path]
        maps.append(
            FrontendMapFact(
                route=page.route,
                page=page.path,
                components=[item.name for item in components if item.path == page.path],
                api_calls=_dedupe(page_calls),
                state=[],
                styles=_dedupe(global_styles + [asset for asset in page_assets if _asset_kind(asset) == "style"]),
                assets=_dedupe(page_assets),
                evidence=[page.evidence],
            )
        )
    for component in components:
        if any(item.page == component.path for item in maps):
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


def _extract_page(file_fact: FileFact, source: str) -> PageFact:
    engine = _template_engine(file_fact, source)
    title_match = TITLE_RE.search(source)
    title = " ".join(title_match.group("title").split()) if title_match else None
    return PageFact(
        path=file_fact.path,
        route=_page_route(file_fact.path),
        title=title,
        kind="template-page" if engine else "static-page",
        template_engine=engine,
        evidence=Evidence(file=file_fact.path, kind="page", line_start=1, line_end=1),
    )


def _extract_forms(file_fact: FileFact, source: str) -> list[FormFact]:
    forms: list[FormFact] = []
    for match in TAG_RE.finditer(source):
        if match.group("tag").lower() != "form":
            continue
        attrs = _attrs(match.group("attrs"))
        action = attrs.get("action") or attrs.get("th:action") or attrs.get("@action")
        method = attrs.get("method", "GET").upper() if "method" in attrs else None
        form_end = source.find("</form>", match.end())
        body = source[match.end() : form_end if form_end >= 0 else match.end() + 1200]
        fields = _form_fields(body)
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


def _extract_page_assets(file_fact: FileFact, source: str) -> list[AssetFact]:
    assets: list[AssetFact] = []
    for match in TAG_RE.finditer(source):
        tag = match.group("tag").lower()
        attrs = _attrs(match.group("attrs"))
        candidates: list[tuple[str, str, str]] = []
        if tag == "script" and attrs.get("src"):
            candidates.append((attrs["src"], "script", "script-src"))
        elif tag == "link" and attrs.get("href"):
            rel = attrs.get("rel", "").lower()
            kind = "style" if "stylesheet" in rel else "link"
            candidates.append((attrs["href"], kind, "link-href"))
        elif tag in {"img", "source"} and attrs.get("src"):
            candidates.append((attrs["src"], "image", f"{tag}-src"))
        for asset_path, asset_kind, usage_kind in candidates:
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


def _extract_api_calls(file_fact: FileFact, source: str, context: str) -> list[ApiCallFact]:
    calls: list[ApiCallFact] = []
    for match in FETCH_RE.finditer(source):
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=match.group("endpoint"),
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
        calls.append(
            ApiCallFact(
                path=file_fact.path,
                endpoint=match.group("endpoint"),
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
    return calls


def _attrs(source: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for match in ATTR_RE.finditer(source):
        name = match.group("name").lower()
        value = match.group("value") or ""
        attrs[name] = " ".join(value.split())
    return attrs


def _form_fields(source: str) -> list[str]:
    fields: list[str] = []
    for match in INPUT_RE.finditer(source):
        attrs = _attrs(match.group("attrs"))
        name = attrs.get("name") or attrs.get("id")
        if name:
            fields.append(name)
    return _dedupe(fields)


def _template_engine(file_fact: FileFact, source: str) -> str | None:
    suffix = Path(file_fact.path).suffix.lower()
    if file_fact.language == "jsp":
        return "jsp"
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
    if "th:" in source or "xmlns:th=" in source:
        return "thymeleaf"
    return None


def _page_route(path: str) -> str:
    normalized = path.replace("\\", "/")
    prefixes = (
        "public/",
        "static/",
        "src/main/resources/static/",
        "src/main/resources/templates/",
        "src/main/webapp/",
        "webapp/",
        "templates/",
        "views/",
    )
    for prefix in prefixes:
        if normalized.startswith(prefix):
            normalized = normalized.removeprefix(prefix)
            break
    stem = normalized.rsplit(".", 1)[0]
    if stem in {"index", "home"}:
        return "/"
    if stem.endswith("/index"):
        return "/" + stem.removesuffix("/index").strip("/")
    return "/" + stem.strip("/")


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


def _read(root: Path, file_fact: FileFact) -> str:
    return (root / file_fact.path).read_text(encoding="utf-8")


def _line_for_offset(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _dedupe(values: object) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(str(value))
    return result
