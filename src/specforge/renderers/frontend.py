from __future__ import annotations

from specforge.models import ProjectFacts
from specforge.renderers.shared import _code_list, _source_link

def render_frontend(facts: ProjectFacts) -> str:
    if not facts.frontend_surfaces:
        return "# Frontend\n\nNo frontend surface was detected by the current extractors.\n"
    sections = ["# Frontend\n"]
    for surface in facts.frontend_surfaces:
        sections.append(
            f"## {surface.framework}\n\n"
            f"- Routes: {surface.route_count}\n"
            f"- Components: {surface.component_count}\n"
            f"- API calls: {surface.api_call_count}\n"
            f"- Pages: {surface.page_count}\n"
            f"- Forms: {surface.form_count}\n"
            f"- Styles: {surface.style_count}\n"
            f"- Assets: {surface.asset_count}\n"
            f"- State usages: {surface.state_count}\n"
        )
    return "\n".join(sections)

def render_components(facts: ProjectFacts) -> str:
    if not facts.components:
        return "# Components\n\nNo frontend components were detected by the current extractors.\n"
    rows = [
        "| Component | Framework | Props | Hooks | Source |",
        "| --- | --- | --- | --- | --- |",
    ]
    for component in facts.components:
        rows.append(
            f"| `{component.name}` | {component.framework} | "
            f"{', '.join(component.props)} | {', '.join(component.hooks)} | "
            f"{_source_link(component.path, component.evidence.line_start or 1)} |"
        )
    return "# Components\n\n" + "\n".join(rows) + "\n"

def render_frontend_routes(facts: ProjectFacts) -> str:
    if not facts.frontend_routes:
        return "# Frontend Routes\n\nNo frontend routes were detected by the current extractors.\n"
    rows = [
        "| Route | Source | Framework | Kind |",
        "| --- | --- | --- | --- |",
    ]
    for route in facts.frontend_routes:
        rows.append(
            f"| `{route.route}` | {_source_link(route.path, route.evidence.line_start or 1)} | "
            f"{route.framework} | {route.kind} |"
        )
    return "# Frontend Routes\n\n" + "\n".join(rows) + "\n"

def render_api_calls(facts: ProjectFacts) -> str:
    if not facts.api_calls:
        return "# API Calls\n\nNo frontend API calls were detected by the current extractors.\n"
    rows = [
        "| Method | Endpoint | Target | Client | Trigger | Context | Matched Route | Source |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for api_call in facts.api_calls:
        rows.append(
            f"| {api_call.method or ''} | `{api_call.endpoint}` | {api_call.target_kind} | {api_call.client} | "
            f"{api_call.trigger or ''} | {api_call.context or ''} | "
            f"`{api_call.matched_route or 'unmatched'}` | "
            f"{_source_link(api_call.path, api_call.evidence.line_start or 1)} |"
        )
    return "# API Calls\n\n" + "\n".join(rows) + "\n"

def render_pages(facts: ProjectFacts) -> str:
    if not facts.pages:
        return "# Pages\n\nNo static or template pages were detected.\n"
    rows = [
        "| Route | Page | Title | Kind | Template Engine | Source |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for page in facts.pages:
        rows.append(
            f"| `{page.route}` | `{page.path}` | {page.title or ''} | "
            f"{page.kind} | {page.template_engine or ''} | "
            f"{_source_link(page.evidence.file, page.evidence.line_start or 1)} |"
        )
    return "# Pages\n\n" + "\n".join(rows) + "\n"

def render_forms(facts: ProjectFacts) -> str:
    if not facts.forms:
        return "# Forms\n\nNo forms were detected in static or template pages.\n"
    rows = [
        "| Source | Method | Action | Fields | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for form in facts.forms:
        rows.append(
            f"| `{form.source}` | {form.method or ''} | `{form.action or ''}` | "
            f"{_code_list(form.fields)} | "
            f"{_source_link(form.evidence.file, form.evidence.line_start or 1)} |"
        )
    return "# Forms\n\n" + "\n".join(rows) + "\n"

def render_assets(facts: ProjectFacts) -> str:
    if not facts.assets:
        return "# Assets\n\nNo frontend asset references were detected.\n"
    rows = [
        "| Asset | Kind | Usage | Source | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for asset in facts.assets:
        rows.append(
            f"| `{asset.asset_path}` | {asset.asset_kind} | {asset.usage_kind} | "
            f"`{asset.source}` | {_source_link(asset.evidence.file, asset.evidence.line_start or 1)} |"
        )
    return "# Assets\n\n" + "\n".join(rows) + "\n"

def render_styles(facts: ProjectFacts) -> str:
    if not facts.styles:
        return "# Styles\n\nNo CSS, Sass, or Less style files were detected.\n"
    rows = [
        "| Style File | Selectors | Classes | IDs | Variables | Imports | Asset URLs | Source |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for style in facts.styles:
        rows.append(
            f"| `{style.path}` | {_code_list(style.selectors[:12])} | "
            f"{_code_list(style.classes[:12])} | {_code_list(style.ids[:12])} | "
            f"{_code_list(style.css_variables[:12])} | {_code_list(style.imports)} | "
            f"{_code_list(style.asset_urls)} | "
            f"{_source_link(style.evidence.file, style.evidence.line_start or 1)} |"
        )
    return "# Styles\n\n" + "\n".join(rows) + "\n"

def render_state(facts: ProjectFacts) -> str:
    if not facts.state_usages:
        return "# State\n\nNo frontend state or store usages were detected.\n"
    rows = [
        "| Source | Library | Usage | Name | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for state in facts.state_usages:
        rows.append(
            f"| `{state.source}` | {state.library} | {state.usage} | `{state.name}` | "
            f"{_source_link(state.evidence.file, state.evidence.line_start or 1)} |"
        )
    return "# State\n\n" + "\n".join(rows) + "\n"

def render_frontend_map(facts: ProjectFacts) -> str:
    if not facts.frontend_maps:
        return "# Frontend Map\n\nNo frontend map entries were generated.\n"
    rows = [
        "| Route | Page | Components | API Calls | State | Styles | Assets | Evidence |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in facts.frontend_maps:
        evidence = item.evidence[0] if item.evidence else None
        source = _source_link(evidence.file, evidence.line_start or 1) if evidence else ""
        rows.append(
            f"| `{item.route}` | `{item.page or ''}` | {_code_list(item.components)} | "
            f"{_code_list(item.api_calls)} | {_code_list(item.state)} | "
            f"{_code_list(item.styles)} | {_code_list(item.assets)} | {source} |"
        )
    return "# Frontend Map\n\n" + "\n".join(rows) + "\n"
