from __future__ import annotations

from specforge.models import Gap, ProjectFacts
from specforge.renderers.shared import (
    _dominant_language,
    _source_link,
    _symbol_bullets,
    _symbols_by_path,
)

def render_summary(facts: ProjectFacts) -> str:
    languages = "\n".join(f"- {name}: {count}" for name, count in facts.languages.items()) or "- none"
    dependencies = "\n".join(
        f"- {dependency.name} ({dependency.scope}, {dependency.source})"
        for dependency in facts.dependencies[:50]
    ) or "- none detected"
    entrypoints = "\n".join(
        f"- {entrypoint.command or entrypoint.path}: {entrypoint.kind}"
        for entrypoint in facts.entrypoints
    ) or "- none detected"
    return f"""# SpecForge Scan Summary

Project: `{facts.name}`

## Languages

{languages}

## Entrypoints

{entrypoints}

## Dependencies

{dependencies}

## Inventory

- Files scanned: {len(facts.files)}
- Config files: {len(facts.config_files)}
- Test files: {len(facts.test_files)}
- Backend routes: {len(facts.api_routes)}
- API links: {len(facts.api_links)}
- Java Web surfaces: {len(facts.java_web_surfaces)}
- Servlet mappings: {len(facts.servlets)}
- JSP pages: {len(facts.jsp_pages)}
- Data models: {len(facts.data_models)}
- Data layer facts: {len(facts.data_layers)}
- Runtime config facts: {len(facts.runtime_configs)}
- Test map entries: {len(facts.test_maps)}
- Frontend pages: {len(facts.pages)}
- Forms: {len(facts.forms)}
- Styles: {len(facts.styles)}
- Assets: {len(facts.assets)}
- State usages: {len(facts.state_usages)}
"""

def render_overview(facts: ProjectFacts, gaps: list[Gap]) -> str:
    dominant_language = _dominant_language(facts)
    return f"""# {facts.name} Spec

## Purpose

This spec bundle was generated from deterministic codebase scanning. It is an evidence-backed starting point for understanding the project, not a complete product requirements document.

## Observed Profile

- Project root: `{facts.root}`
- Files scanned: {len(facts.files)}
- Dominant language: {dominant_language}
- Dependencies detected: {len(facts.dependencies)}
- Frameworks detected: {len(facts.frameworks)}
- Entrypoints detected: {len(facts.entrypoints)}
- Commands detected: {len(facts.commands)}
- Backend routes detected: {len(facts.api_routes)}
- API contracts detected: {len(facts.api_contracts)}
- API links detected: {len(facts.api_links)}
- Java Web surfaces detected: {len(facts.java_web_surfaces)}
- Servlet mappings detected: {len(facts.servlets)}
- JSP pages detected: {len(facts.jsp_pages)}
- Data models detected: {len(facts.data_models)}
- Repositories detected: {len(facts.repositories)}
- Services detected: {len(facts.services)}
- Data layer facts detected: {len(facts.data_layers)}
- Runtime config facts detected: {len(facts.runtime_configs)}
- Frontend routes detected: {len(facts.frontend_routes)}
- Frontend pages detected: {len(facts.pages)}
- Forms detected: {len(facts.forms)}
- Components detected: {len(facts.components)}
- Frontend API calls detected: {len(facts.api_calls)}
- Styles detected: {len(facts.styles)}
- Assets detected: {len(facts.assets)}
- State usages detected: {len(facts.state_usages)}
- Frontend map entries detected: {len(facts.frontend_maps)}
- Imports detected: {len(facts.imports)}
- Symbols detected: {len(facts.symbols)}
- Test files detected: {len(facts.test_files)}
- Test map entries detected: {len(facts.test_maps)}
- Open gaps: {len(gaps)}

## Reading Order

1. `overview.md`
2. `architecture.md`
3. `modules.md`
4. `symbols.md`
5. `imports.md`
6. `frameworks.md`
7. `backend.md`
8. `api-routes.md`
9. `api-contracts.md`
10. `api-links.md`
11. `java-web.md`
12. `spring.md`
13. `servlets.md`
14. `jsp-pages.md`
15. `data-models.md`
16. `data-layer.md`
17. `frontend.md`
18. `components.md`
19. `frontend-routes.md`
20. `api-calls.md`
21. `pages.md`
22. `forms.md`
23. `assets.md`
24. `styles.md`
25. `state.md`
26. `frontend-map.md`
27. `runtime-config.md`
28. `dependencies.md`
29. `entrypoints.md`
30. `commands.md`
31. `tests.md`
32. `test-map.md`
33. `implementation-guide.md`
34. `llm-handoff.md`
35. `gaps-and-questions.md`
36. `evidence.md`

## Evidence Policy

Claims in this bundle come from observed files and manifests unless explicitly listed as gaps. Future LLM-assisted summaries should keep inferred claims separate from observed claims.
"""

def render_architecture(facts: ProjectFacts) -> str:
    role_counts: dict[str, int] = {}
    for file_fact in facts.files:
        role_counts[file_fact.role] = role_counts.get(file_fact.role, 0) + 1
    roles = "\n".join(f"- {role}: {count}" for role, count in sorted(role_counts.items()))
    config_files = "\n".join(f"- `{item.path}`" for item in facts.config_files) or "- none detected"
    modules = "\n".join(
        f"- `{path}`: {len(symbols)} symbol(s)"
        for path, symbols in _symbols_by_path(facts).items()
    ) or "- no AST-backed modules detected"
    backend = "\n".join(
        f"- {surface.framework}: {surface.route_count} route(s), "
        f"{surface.service_count} service symbol(s), {surface.model_count} model symbol(s), "
        f"{surface.data_layer_count} data-layer fact(s), "
        f"{surface.runtime_config_count} runtime config fact(s), "
        f"{surface.test_map_count} test map entry/entries"
        for surface in facts.backend_surfaces
    ) or "- no backend surface detected"
    api_links = "\n".join(
        f"- {link.method or 'ANY'} `{link.endpoint}` -> "
        f"{link.matched_method or ''} `{link.matched_route or 'unmatched'}` "
        f"({link.match_type}, {link.confidence})"
        for link in facts.api_links[:30]
    ) or "- no API links generated"
    data_layer = "\n".join(
        f"- `{item.path}`: {item.kind} `{item.name}` details={len(item.details)}"
        for item in facts.data_layers[:30]
    ) or "- no data-layer facts detected"
    runtime_config = "\n".join(
        f"- `{item.path}`: {item.kind} values={len(item.values)}"
        for item in facts.runtime_configs[:30]
    ) or "- no runtime config facts detected"
    test_map = "\n".join(
        f"- `{item.test_path}` -> {item.target_kind} `{item.target or 'unmatched'}` ({item.confidence})"
        for item in facts.test_maps[:30]
    ) or "- no test map entries generated"
    java_web = "\n".join(
        "- Java Web: "
        f"{surface.spring_controller_count} Spring controller(s), "
        f"{surface.servlet_count} servlet mapping(s), "
        f"{surface.jsp_page_count} JSP page(s), "
        f"{surface.data_model_count} data model(s), "
        f"{surface.repository_count} repository/repositories, "
        f"{surface.service_count} service(s)"
        for surface in facts.java_web_surfaces
    ) or "- no Java Web surface detected"
    frontend = "\n".join(
        f"- {surface.framework}: {surface.route_count} route(s), "
        f"{surface.component_count} component(s), {surface.api_call_count} API call(s), "
        f"{surface.page_count} page(s), {surface.form_count} form(s), "
        f"{surface.style_count} style file(s), {surface.asset_count} asset reference(s), "
        f"{surface.state_count} state usage(s)"
        for surface in facts.frontend_surfaces
    ) or "- no frontend surface detected"
    static_frontend = "\n".join(
        [
            f"- Pages: {len(facts.pages)}",
            f"- Forms: {len(facts.forms)}",
            f"- Styles: {len(facts.styles)}",
            f"- Assets: {len(facts.assets)}",
            f"- State usages: {len(facts.state_usages)}",
            f"- Frontend map entries: {len(facts.frontend_maps)}",
        ]
    )
    return f"""# Architecture

## Current View

SpecForge describes architecture from repository structure, manifests, language extractors, and conservative backend/frontend surface detection. It does not yet infer full runtime data flow or business workflows.

## Backend Surface

{backend}

## Java Web Surface

{java_web}

## Frontend Surface

{frontend}

## Frontend Static And Template Surface

{static_frontend}

## Connected Full-Stack Map

- Pages/components/forms: {len(facts.pages) + len(facts.components) + len(facts.forms)}
- Frontend API calls: {len(facts.api_calls)}
- Backend routes: {len(facts.api_routes)}
- API contracts: {len(facts.api_contracts)}
- API links: {len(facts.api_links)}
- Data-layer facts: {len(facts.data_layers)}
- Runtime config facts: {len(facts.runtime_configs)}
- Test map entries: {len(facts.test_maps)}

### API Links

{api_links}

### Data Layer

{data_layer}

### Runtime Config

{runtime_config}

### Test Map

{test_map}

## File Roles

{roles or "- none detected"}

## Extracted Modules

{modules}

## Configuration Surface

{config_files}

## Next Extractors

The next useful extractors are route, entity, and call graph scanners for each supported language.
"""

def render_inventory(facts: ProjectFacts) -> str:
    rows = [
        "| Path | Language | Role | Size |",
        "| --- | --- | --- | ---: |",
    ]
    for file_fact in facts.files:
        rows.append(
            f"| `{file_fact.path}` | {file_fact.language} | {file_fact.role} | {file_fact.size_bytes} |"
        )
    return "# Inventory\n\n" + "\n".join(rows) + "\n"

def render_dependencies(facts: ProjectFacts) -> str:
    if not facts.dependencies:
        return "# Dependencies\n\nNo dependencies were detected from supported manifests.\n"
    rows = [
        "| Name | Scope | Source |",
        "| --- | --- | --- |",
    ]
    for dependency in facts.dependencies:
        rows.append(f"| `{dependency.name}` | {dependency.scope} | `{dependency.source}` |")
    return "# Dependencies\n\n" + "\n".join(rows) + "\n"

def render_modules(facts: ProjectFacts) -> str:
    grouped = _symbols_by_path(facts)
    if not grouped:
        return "# Modules\n\nNo language-backed modules were extracted.\n"

    sections = ["# Modules\n"]
    for path, symbols in grouped.items():
        imports = [item for item in facts.imports if item.path == path]
        top_level = [item for item in symbols if item.parent is None]
        sections.append(
            f"## `{path}`\n\n"
            f"- Symbols: {len(symbols)}\n"
            f"- Top-level symbols: {len(top_level)}\n"
            f"- Imports: {len(imports)}\n\n"
            "### Extracted Surface\n\n"
            f"{_symbol_bullets(top_level) or '- no top-level symbols detected'}\n"
        )
    return "\n".join(sections)

def render_symbols(facts: ProjectFacts) -> str:
    if not facts.symbols:
        return "# Symbols\n\nNo symbols were extracted.\n"
    rows = [
        "| Symbol | Kind | Signature | Source |",
        "| --- | --- | --- | --- |",
    ]
    for symbol in facts.symbols:
        source = _source_link(symbol.path, symbol.line_start)
        rows.append(
            f"| `{symbol.qualname}` | {symbol.kind} | `{symbol.signature}` | {source} |"
        )
    return "# Symbols\n\n" + "\n".join(rows) + "\n"

def render_imports(facts: ProjectFacts) -> str:
    if not facts.imports:
        return "# Imports\n\nNo imports were extracted.\n"
    rows = [
        "| Source | Import | Kind |",
        "| --- | --- | --- |",
    ]
    for import_fact in facts.imports:
        target = import_fact.module or ", ".join(import_fact.names)
        if import_fact.module and import_fact.names:
            target = f"{'.' * import_fact.level}{import_fact.module}: {', '.join(import_fact.names)}"
        elif import_fact.level:
            target = f"{'.' * import_fact.level}{target}"
        rows.append(f"| `{import_fact.path}` | `{target}` | {import_fact.kind} |")
    return "# Imports\n\n" + "\n".join(rows) + "\n"

def render_frameworks(facts: ProjectFacts) -> str:
    if not facts.frameworks:
        return "# Frameworks\n\nNo frameworks were detected by the current extractors.\n"
    rows = [
        "| Framework | Category | Source | Confidence | Evidence |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for framework in facts.frameworks:
        rows.append(
            f"| {framework.name} | {framework.category} | {framework.source} | "
            f"{framework.confidence:.2f} | `{framework.evidence.file}` |"
        )
    return "# Frameworks\n\n" + "\n".join(rows) + "\n"
