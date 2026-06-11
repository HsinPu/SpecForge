from __future__ import annotations

import json
from pathlib import Path

from specforge.models import Gap, ProjectFacts, TraceClaim, to_jsonable


def write_fact_bundle(
    facts: ProjectFacts,
    claims: list[TraceClaim],
    gaps: list[Gap],
    out_dir: str | Path,
) -> None:
    output_path = Path(out_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    _write_json(output_path / "facts.json", facts)
    _write_json(output_path / "traceability.json", claims)
    _write_json(output_path / "gaps.json", gaps)
    (output_path / "summary.md").write_text(render_summary(facts), encoding="utf-8")
    (output_path / "gaps.md").write_text(render_gaps(gaps), encoding="utf-8")


def write_spec_bundle(
    facts: ProjectFacts,
    claims: list[TraceClaim],
    gaps: list[Gap],
    out_dir: str | Path,
) -> None:
    output_path = Path(out_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    _write_markdown_documents(output_path, _spec_documents(facts, claims, gaps))
    _write_json(output_path / "facts.json", facts)
    _write_json(output_path / "traceability.json", claims)
    _write_json(output_path / "gaps.json", gaps)


def _write_markdown_documents(output_path: Path, documents: list[tuple[str, str]]) -> None:
    for filename, content in documents:
        (output_path / filename).write_text(content, encoding="utf-8")


def _spec_documents(
    facts: ProjectFacts,
    claims: list[TraceClaim],
    gaps: list[Gap],
) -> list[tuple[str, str]]:
    return [
        ("overview.md", render_overview(facts, gaps)),
        ("architecture.md", render_architecture(facts)),
        ("inventory.md", render_inventory(facts)),
        ("modules.md", render_modules(facts)),
        ("symbols.md", render_symbols(facts)),
        ("imports.md", render_imports(facts)),
        ("frameworks.md", render_frameworks(facts)),
        ("backend.md", render_backend(facts)),
        ("api-routes.md", render_api_routes(facts)),
        ("java-web.md", render_java_web(facts)),
        ("spring.md", render_spring(facts)),
        ("servlets.md", render_servlets(facts)),
        ("jsp-pages.md", render_jsp_pages(facts)),
        ("data-models.md", render_data_models(facts)),
        ("data-layer.md", render_data_layer(facts)),
        ("api-contracts.md", render_api_contracts(facts)),
        ("api-links.md", render_api_links(facts)),
        ("frontend.md", render_frontend(facts)),
        ("components.md", render_components(facts)),
        ("frontend-routes.md", render_frontend_routes(facts)),
        ("api-calls.md", render_api_calls(facts)),
        ("pages.md", render_pages(facts)),
        ("forms.md", render_forms(facts)),
        ("assets.md", render_assets(facts)),
        ("styles.md", render_styles(facts)),
        ("state.md", render_state(facts)),
        ("frontend-map.md", render_frontend_map(facts)),
        ("dependencies.md", render_dependencies(facts)),
        ("entrypoints.md", render_entrypoints(facts)),
        ("commands.md", render_commands(facts)),
        ("tests.md", render_tests(facts)),
        ("runtime-config.md", render_runtime_config(facts)),
        ("test-map.md", render_test_map(facts)),
        ("gaps-and-questions.md", render_gaps(gaps)),
        ("implementation-guide.md", render_implementation_guide(facts, gaps)),
        ("llm-handoff.md", render_llm_handoff(facts, gaps)),
        ("evidence.md", render_evidence(claims)),
    ]


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


def render_backend(facts: ProjectFacts) -> str:
    if not facts.backend_surfaces:
        return "# Backend\n\nNo backend surface was detected by the current extractors.\n"
    sections = ["# Backend\n"]
    for surface in facts.backend_surfaces:
        java_services = len(facts.services) if surface.framework in {"java-web", "servlet", "spring"} else 0
        java_models = len(facts.data_models) if surface.framework in {"java-web", "servlet", "spring"} else 0
        sections.append(
            f"## {surface.framework}\n\n"
            f"- Routes: {surface.route_count}\n"
            f"- Handlers: {surface.handler_count}\n"
            f"- Service symbols: {surface.service_count + java_services}\n"
            f"- Model symbols: {surface.model_count + java_models}\n"
            f"- Data-layer facts: {surface.data_layer_count}\n"
            f"- Runtime config facts: {surface.runtime_config_count}\n"
            f"- Test map entries: {surface.test_map_count}\n"
        )
    return "\n".join(sections)


def render_api_routes(facts: ProjectFacts) -> str:
    if not facts.api_routes:
        return "# API Routes\n\nNo backend API routes were detected by the current extractors.\n"
    rows = [
        "| Method | Path | Handler | Params | Body | Response | Framework | Kind | Source |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for route in facts.api_routes:
        rows.append(
            f"| {route.method} | `{route.path}` | `{route.handler or ''}` | "
            f"{_param_summary(route.parameters)} | `{route.request_body or ''}` | "
            f"`{route.response_type or ''}` | "
            f"{route.framework} | {route.kind} | "
            f"{_source_link(route.evidence.file, route.evidence.line_start or 1)} |"
        )
    return "# API Routes\n\n" + "\n".join(rows) + "\n"


def render_java_web(facts: ProjectFacts) -> str:
    if not facts.java_web_surfaces:
        return "# Java Web\n\nNo Java Web surface was detected by the current extractors.\n"
    sections = ["# Java Web\n"]
    for surface in facts.java_web_surfaces:
        sections.append(
            "## Surface Counts\n\n"
            f"- Spring controllers: {surface.spring_controller_count}\n"
            f"- Servlet mappings: {surface.servlet_count}\n"
            f"- JSP pages: {surface.jsp_page_count}\n"
            f"- Data models: {surface.data_model_count}\n"
            f"- Repositories: {surface.repository_count}\n"
            f"- Services: {surface.service_count}\n"
        )
    sections.append("## Reconstruction Notes\n")
    sections.append(
        "- Treat JSP files as legacy page contracts.\n"
        "- Treat Servlet mappings and Spring mappings as backend route contracts.\n"
        "- Treat DTO/entity/repository/service facts as structural evidence, not complete behavior.\n"
    )
    return "\n".join(sections)


def render_spring(facts: ProjectFacts) -> str:
    routes = [route for route in facts.api_routes if route.framework == "spring"]
    if not routes and not facts.repositories and not facts.services and not facts.data_models:
        return "# Spring\n\nNo Spring-specific surface was detected by the current extractors.\n"
    sections = ["# Spring\n"]
    if routes:
        rows = [
            "| Method | Path | Handler | Class Prefix | Params | Body | Response | Source |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for route in routes:
            rows.append(
                f"| {route.method} | `{route.path}` | `{route.handler or ''}` | "
                f"`{route.class_prefix or ''}` | {_param_summary(route.parameters)} | "
                f"`{route.request_body or ''}` | `{route.response_type or ''}` | "
                f"{_source_link(route.evidence.file, route.evidence.line_start or 1)} |"
            )
        sections.append("## Routes\n\n" + "\n".join(rows) + "\n")
    if facts.services:
        sections.append("## Services\n\n" + _service_rows(facts) + "\n")
    if facts.repositories:
        sections.append("## Repositories\n\n" + _repository_rows(facts) + "\n")
    if facts.data_models:
        sections.append("## Data Models\n\n" + _data_model_rows(facts) + "\n")
    return "\n".join(sections)


def render_servlets(facts: ProjectFacts) -> str:
    if not facts.servlets:
        return "# Servlets\n\nNo Servlet mappings were detected by the current extractors.\n"
    rows = [
        "| Servlet | Class | URL Patterns | Source | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for servlet in facts.servlets:
        rows.append(
            f"| `{servlet.name}` | `{servlet.class_name or ''}` | "
            f"{', '.join(f'`{item}`' for item in servlet.url_patterns)} | "
            f"{servlet.source} | {_source_link(servlet.evidence.file, servlet.evidence.line_start or 1)} |"
        )
    return "# Servlets\n\n" + "\n".join(rows) + "\n"


def render_jsp_pages(facts: ProjectFacts) -> str:
    if not facts.jsp_pages:
        return "# JSP Pages\n\nNo JSP pages were detected by the current extractors.\n"
    rows = [
        "| Route | Path | Form Actions | Links | Includes | JSTL | EL | Source |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for page in facts.jsp_pages:
        rows.append(
            f"| `{page.route}` | `{page.path}` | {_code_list(page.form_actions)} | "
            f"{_code_list(page.links)} | {_code_list(page.includes)} | "
            f"{page.uses_jstl} | {page.uses_el} | "
            f"{_source_link(page.evidence.file, page.evidence.line_start or 1)} |"
        )
    return "# JSP Pages\n\n" + "\n".join(rows) + "\n"


def render_data_models(facts: ProjectFacts) -> str:
    if not facts.data_models and not facts.repositories and not facts.services:
        return "# Data Models\n\nNo data model, repository, or service facts were detected.\n"
    sections = ["# Data Models\n"]
    if facts.data_models:
        sections.append("## Models\n\n" + _data_model_rows(facts) + "\n")
    if facts.repositories:
        sections.append("## Repositories\n\n" + _repository_rows(facts) + "\n")
    if facts.services:
        sections.append("## Services\n\n" + _service_rows(facts) + "\n")
    return "\n".join(sections)


def render_data_layer(facts: ProjectFacts) -> str:
    if not facts.data_layers:
        return "# Data Layer\n\nNo SQL, ORM, migration, mapper, repository, or data-layer facts were detected.\n"
    rows = [
        "| Path | Kind | Name | Details | Source |",
        "| --- | --- | --- | --- | --- |",
    ]
    for fact in facts.data_layers:
        rows.append(
            f"| `{fact.path}` | {fact.kind} | `{fact.name}` | "
            f"{_code_list(fact.details) or '`unknown`'} | "
            f"{_source_link(fact.evidence.file, fact.evidence.line_start or 1)} |"
        )
    return "# Data Layer\n\n" + "\n".join(rows) + "\n"


def render_api_contracts(facts: ProjectFacts) -> str:
    if not facts.api_contracts:
        return "# API Contracts\n\nNo API contract skeletons were detected.\n"
    rows = [
        "| Method | Path | Handler | Params | Body | Response | Request Hints | Response Hints | Status | Error Hints | Framework | Source |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for contract in facts.api_contracts:
        rows.append(
            f"| {contract.method} | `{contract.path}` | `{contract.handler or ''}` | "
            f"{_param_summary(contract.parameters)} | `{contract.request_body or ''}` | "
            f"`{contract.response_type or ''}` | "
            f"{_code_list(contract.request_hints) or '`unknown`'} | "
            f"{_code_list(contract.response_hints) or '`unknown`'} | "
            f"{_code_list(contract.status_codes) or '`unknown`'} | "
            f"{_code_list(contract.error_hints) or '`unknown`'} | "
            f"{contract.framework} | "
            f"{_source_link(contract.evidence.file, contract.evidence.line_start or 1)} |"
        )
    return "# API Contracts\n\n" + "\n".join(rows) + "\n"


def render_api_links(facts: ProjectFacts) -> str:
    if not facts.api_links:
        return "# API Links\n\nNo frontend-to-backend API links were generated.\n"
    rows = [
        "| Source | Method | Endpoint | Matched Route | Framework | Match | Confidence | Evidence |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for link in facts.api_links:
        evidence = link.evidence[0] if link.evidence else None
        source = _source_link(evidence.file, evidence.line_start or 1) if evidence else ""
        matched = (
            f"`{link.matched_method or ''} {link.matched_route}`"
            if link.matched_route
            else "`unmatched`"
        )
        rows.append(
            f"| `{link.source}` | {link.method or ''} | `{link.endpoint}` | "
            f"{matched} | {link.matched_framework or ''} | "
            f"{link.match_type} | {link.confidence} | {source} |"
        )
    return "# API Links\n\n" + "\n".join(rows) + "\n"


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
        "| Method | Endpoint | Client | Trigger | Context | Matched Route | Source |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for api_call in facts.api_calls:
        rows.append(
            f"| {api_call.method or ''} | `{api_call.endpoint}` | {api_call.client} | "
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


def render_entrypoints(facts: ProjectFacts) -> str:
    if not facts.entrypoints:
        return "# Entrypoints\n\nNo entrypoints were detected from supported manifests or conventions.\n"
    rows = [
        "| Command | Target | Kind | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    for entrypoint in facts.entrypoints:
        rows.append(
            "| "
            f"{entrypoint.command or ''} | `{entrypoint.path}` | {entrypoint.kind} | "
            f"`{entrypoint.evidence.file}` |"
        )
    return "# Entrypoints\n\n" + "\n".join(rows) + "\n"


def render_commands(facts: ProjectFacts) -> str:
    if not facts.commands:
        return "# Commands\n\nNo CLI commands were detected by the current extractors.\n"
    rows = [
        "| Command | Description | Arguments | Options | Source |",
        "| --- | --- | --- | --- | --- |",
    ]
    for command in facts.commands:
        arguments = ", ".join(f"`{item}`" for item in command.arguments) or ""
        options = ", ".join(f"`{item}`" for item in command.options) or ""
        description = command.description or ""
        source = _source_link(command.path, command.evidence.line_start or 1)
        rows.append(
            f"| `{command.name}` | {description} | {arguments} | {options} | {source} |"
        )
    return "# Commands\n\n" + "\n".join(rows) + "\n"


def render_tests(facts: ProjectFacts) -> str:
    if not facts.test_files:
        return "# Tests\n\nNo test files were detected with the current scanner rules.\n"
    rows = [
        "| Path | Language | Size |",
        "| --- | --- | ---: |",
    ]
    for test_file in facts.test_files:
        rows.append(f"| `{test_file.path}` | {test_file.language} | {test_file.size_bytes} |")
    return "# Tests\n\n" + "\n".join(rows) + "\n"


def render_runtime_config(facts: ProjectFacts) -> str:
    if not facts.runtime_configs:
        return "# Runtime Config\n\nNo runtime config facts were detected.\n"
    rows = [
        "| Path | Kind | Name | Values | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for config in facts.runtime_configs:
        rows.append(
            f"| `{config.path}` | {config.kind} | `{config.name}` | "
            f"{_code_list(config.values) or '`unknown`'} | "
            f"{_source_link(config.evidence.file, config.evidence.line_start or 1)} |"
        )
    return "# Runtime Config\n\n" + "\n".join(rows) + "\n"


def render_test_map(facts: ProjectFacts) -> str:
    if not facts.test_maps:
        return "# Test Map\n\nNo test map entries were generated.\n"
    rows = [
        "| Test | Target Kind | Target | Confidence | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in facts.test_maps:
        rows.append(
            f"| `{item.test_path}` | {item.target_kind} | "
            f"`{item.target or 'unmatched'}` | {item.confidence} | "
            f"{_source_link(item.evidence.file, item.evidence.line_start or 1)} |"
        )
    return "# Test Map\n\n" + "\n".join(rows) + "\n"


def render_implementation_guide(facts: ProjectFacts, gaps: list[Gap]) -> str:
    entrypoints = "\n".join(
        f"- `{item.command or item.path}` -> `{item.path}` ({item.kind})"
        for item in facts.entrypoints
    ) or "- no entrypoints detected"
    commands = "\n".join(
        f"- `{item.name}` arguments=[{', '.join(item.arguments)}] options=[{', '.join(item.options)}]"
        for item in facts.commands
    ) or "- no commands detected"
    modules = "\n".join(
        f"- `{path}`"
        for path in _symbols_by_path(facts)
    ) or "- no extracted modules"
    backend = "\n".join(
        f"- {route.method} `{route.path}` -> `{route.handler or ''}` "
        f"({route.framework}) params=[{_param_summary(route.parameters)}] "
        f"body=`{route.request_body or ''}` response=`{route.response_type or ''}`"
        for route in facts.api_routes
    ) or "- no backend routes detected"
    api_contracts = "\n".join(
        f"- {contract.method} `{contract.path}` -> `{contract.handler or ''}` "
        f"params=[{_param_summary(contract.parameters)}] "
        f"body=`{contract.request_body or ''}` response=`{contract.response_type or ''}` "
        f"request_hints=[{', '.join(contract.request_hints) or 'unknown'}] "
        f"response_hints=[{', '.join(contract.response_hints) or 'unknown'}] "
        f"status=[{', '.join(contract.status_codes) or 'unknown'}]"
        for contract in facts.api_contracts
    ) or "- no API contract skeletons detected"
    api_links = "\n".join(
        f"- `{link.source}` {link.method or ''} `{link.endpoint}` -> "
        f"`{link.matched_method or ''} {link.matched_route or 'unmatched'}` "
        f"({link.match_type}, {link.confidence})"
        for link in facts.api_links
    ) or "- no API links generated"
    java_web = "\n".join(
        f"- Servlet `{servlet.name}` -> {', '.join(servlet.url_patterns)}"
        for servlet in facts.servlets
    ) or "- no Servlet mappings detected"
    jsp_pages = "\n".join(
        f"- `{page.route}` from `{page.path}` forms=[{', '.join(page.form_actions)}]"
        for page in facts.jsp_pages
    ) or "- no JSP pages detected"
    data_models = "\n".join(
        f"- `{model.name}` ({model.kind}) fields=[{', '.join(model.fields)}]"
        for model in facts.data_models
    ) or "- no data models detected"
    data_layer = "\n".join(
        f"- `{item.path}` {item.kind} `{item.name}` details=[{', '.join(item.details) or 'unknown'}]"
        for item in facts.data_layers
    ) or "- no data-layer facts detected"
    runtime_config = "\n".join(
        f"- `{item.path}` {item.kind} values=[{', '.join(item.values) or 'unknown'}]"
        for item in facts.runtime_configs
    ) or "- no runtime config facts detected"
    frontend = "\n".join(
        f"- `{component.name}` ({component.framework}) props=[{', '.join(component.props)}]"
        for component in facts.components
    ) or "- no frontend components detected"
    pages = "\n".join(
        f"- `{page.route}` -> `{page.path}` title=`{page.title or ''}` engine=`{page.template_engine or ''}`"
        for page in facts.pages
    ) or "- no static/template pages detected"
    forms = "\n".join(
        f"- `{form.source}` {form.method or ''} `{form.action or ''}` fields=[{', '.join(form.fields)}]"
        for form in facts.forms
    ) or "- no forms detected"
    state = "\n".join(
        f"- `{item.source}` {item.library}:{item.name} ({item.usage})"
        for item in facts.state_usages
    ) or "- no frontend state usages detected"
    styles = "\n".join(
        f"- `{style.path}` selectors={len(style.selectors)} variables=[{', '.join(style.css_variables)}]"
        for style in facts.styles
    ) or "- no style files detected"
    assets = "\n".join(
        f"- `{asset.asset_path}` ({asset.asset_kind}) from `{asset.source}`"
        for asset in facts.assets[:50]
    ) or "- no asset references detected"
    tests = "\n".join(f"- `{item.path}`" for item in facts.test_files) or "- no tests detected"
    test_map = "\n".join(
        f"- `{item.test_path}` -> {item.target_kind} `{item.target or 'unmatched'}` ({item.confidence})"
        for item in facts.test_maps
    ) or "- no test map entries generated"
    return f"""# Implementation Guide

## Intent

This document is the bridge between the observed codebase and a future implementation. It is designed for a human engineer or an LLM agent that needs to rebuild the project while preserving observable behavior.

## Preserve First

- Preserve command-line or runtime entrypoints.
- Preserve public symbols and module responsibilities where they reflect user-facing behavior.
- Preserve dependency-driven behavior only when it is supported by evidence.
- Treat gaps as questions, not facts.

## Entrypoint Contract

{entrypoints}

## Command Contract

{commands}

## Backend Contract

{backend}

## API Contract Skeleton

{api_contracts}

## API Link Contract

{api_links}

## Java Web Contract

{java_web}

## JSP Page Contract

{jsp_pages}

## Data Model Contract

{data_models}

## Data Layer Contract

{data_layer}

## Runtime Config Contract

{runtime_config}

## Frontend Contract

{frontend}

## Page Contract

{pages}

## Form Contract

{forms}

## State Contract

{state}

## Style Contract

{styles}

## Asset Contract

{assets}

## Module Contract

{modules}

## Test Contract

{tests}

## Test Map Contract

{test_map}

## Reimplementation Workflow

1. Read `overview.md` and `architecture.md`.
2. Recreate API links from `api-links.md`; treat unmatched calls/routes as gaps.
3. Recreate backend route contracts from `backend.md`, `api-routes.md`, and `api-contracts.md`.
4. Recreate Java Web contracts from `java-web.md`, `spring.md`, `servlets.md`, `jsp-pages.md`, and `data-models.md`.
5. Recreate frontend pages and routes from `pages.md`, `frontend-routes.md`, and `frontend-map.md`.
6. Recreate forms and API integrations from `forms.md`, `api-calls.md`, and `api-links.md`.
7. Recreate data and persistence skeletons from `data-models.md` and `data-layer.md`.
8. Recreate runtime setup from `runtime-config.md`, `entrypoints.md`, and `commands.md`.
9. Recreate components and state surfaces from `components.md` and `state.md`.
10. Recreate styles and static assets from `styles.md` and `assets.md`.
11. Recreate modules from `modules.md` and `symbols.md`.
12. Use `imports.md`, `frameworks.md`, and `dependencies.md` to choose equivalent libraries.
13. Port or recreate tests listed in `tests.md`, using `test-map.md` to prioritize targets.
14. Resolve every item in `gaps-and-questions.md` before declaring parity.

## Known Limits

- Business rules are not inferred unless directly observable.
- Internal call flow is not yet extracted.
- Data model side effects, persistence behavior, and auth/security still require deeper framework extractors.
- Servlet/JSP findings describe route/page skeletons, not complete request lifecycle behavior.
- Frontend page/style/state findings describe static structure, not complete runtime UI behavior.
- API links are heuristic and include confidence levels.
- Unknown request/response/status/error hints must remain unknown until confirmed by evidence.
- Runtime config does not include secret values.
- Open gaps: {len(gaps)}
"""


def render_llm_handoff(facts: ProjectFacts, gaps: list[Gap]) -> str:
    return f"""# LLM Handoff

You are implementing a project from a SpecForge evidence-backed spec bundle.

## Objective

Recreate the project `{facts.name}` from the spec bundle, preserving observable behavior and public interfaces before changing architecture.

## Source Of Truth Order

1. `facts.json` and `traceability.json` for observed facts.
2. `api-links.md` for frontend-to-backend wiring and unmatched API gaps.
3. `frameworks.md`, `backend.md`, `api-routes.md`, and `api-contracts.md` for backend contracts.
4. `java-web.md`, `spring.md`, `servlets.md`, `jsp-pages.md`, `data-models.md`, and `data-layer.md` for Java Web, legacy page, and persistence contracts.
5. `frontend.md`, `pages.md`, `forms.md`, `components.md`, `frontend-routes.md`, `api-calls.md`, `state.md`, `styles.md`, `assets.md`, and `frontend-map.md` for frontend product surfaces.
6. `runtime-config.md`, `entrypoints.md`, `commands.md`, `modules.md`, `symbols.md`, `tests.md`, and `test-map.md` for implementation targets.
7. `implementation-guide.md` for rebuild workflow.
8. `gaps-and-questions.md` for unresolved items.

## Rules

- Do not invent business rules as facts.
- Do not invent DTO fields, database side effects, authentication, or authorization rules.
- Do not invent frontend user flows, CSS cascade behavior, or state schemas.
- Treat unmatched API calls, unmatched backend routes, unmatched tests, and unknown contract fields as gaps.
- Only treat facts with file/line evidence as confirmed.
- Mark assumptions explicitly.
- When replacing libraries or language features, preserve behavior rather than file structure.
- Keep generated code covered by tests that correspond to `tests.md`.
- If a spec claim conflicts with evidence, trust the evidence and report the conflict.
- First summarize backend routes, frontend routes/screens, pages, forms, Servlet/JSP pages, API links, unmatched API calls, unmatched backend routes, unknown contracts, state usage, styles, assets, data models, data-layer facts, runtime config, test map, unmatched tests, and gaps before implementing.

## Current Coverage

- Files scanned: {len(facts.files)}
- Symbols extracted: {len(facts.symbols)}
- Imports extracted: {len(facts.imports)}
- Frameworks detected: {len(facts.frameworks)}
- Backend routes detected: {len(facts.api_routes)}
- API contract skeletons detected: {len(facts.api_contracts)}
- API links detected: {len(facts.api_links)}
- Java Web surfaces detected: {len(facts.java_web_surfaces)}
- Servlet mappings detected: {len(facts.servlets)}
- JSP pages detected: {len(facts.jsp_pages)}
- Data models detected: {len(facts.data_models)}
- Repositories detected: {len(facts.repositories)}
- Services detected: {len(facts.services)}
- Data-layer facts detected: {len(facts.data_layers)}
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
- Entrypoints detected: {len(facts.entrypoints)}
- Commands detected: {len(facts.commands)}
- Tests detected: {len(facts.test_files)}
- Test map entries detected: {len(facts.test_maps)}
- Gaps detected: {len(gaps)}

## Starting Prompt

Implement `{facts.name}` from this SpecForge bundle. First summarize the backend routes, frontend routes/screens, pages/forms/components, API calls, API links, unmatched API calls, unmatched backend routes, API contracts with unknown request/response/status/error fields, Java Web Servlet/JSP surface, state usage, styles, assets, data models, data layer, runtime config, public entrypoints, commands, modules, symbols, test map, unmatched tests, and unresolved gaps. Then propose an implementation plan that preserves observed behavior before writing code.
"""


def render_gaps(gaps: list[Gap]) -> str:
    if not gaps:
        return "# Gaps and Questions\n\nNo deterministic gaps were detected by the current scanner.\n"
    sections = ["# Gaps and Questions\n"]
    for gap in gaps:
        evidence = "\n".join(f"- {_evidence_label(item)} ({item.kind})" for item in gap.evidence)
        sections.append(
            f"## {gap.gap_id}: {gap.title}\n\n"
            f"Severity: `{gap.severity}`\n\n"
            f"{gap.detail}\n\n"
            f"Evidence:\n{evidence or '- none'}\n"
        )
    return "\n".join(sections)


def render_evidence(claims: list[TraceClaim]) -> str:
    if not claims:
        return "# Evidence\n\nNo traceability claims were generated.\n"
    sections = ["# Evidence\n"]
    for claim in claims:
        evidence = "\n".join(
            f"- {_evidence_label(item)} ({item.kind})"
            + (f": {item.note}" if item.note else "")
            for item in claim.evidence
        )
        sections.append(
            f"## {claim.claim_id}\n\n"
            f"- Type: `{claim.claim_type}`\n"
            f"- Status: `{claim.status}`\n"
            f"- Confidence: `{claim.confidence}`\n"
            f"- Claim: {claim.claim}\n\n"
            f"Evidence:\n{evidence or '- none'}\n"
        )
    return "\n".join(sections)


def _dominant_language(facts: ProjectFacts) -> str:
    if not facts.languages:
        return "none detected"
    language, count = max(facts.languages.items(), key=lambda item: item[1])
    return f"{language} ({count} file(s))"


def _symbols_by_path(facts: ProjectFacts) -> dict[str, list]:
    grouped: dict[str, list] = {}
    for symbol in facts.symbols:
        grouped.setdefault(symbol.path, []).append(symbol)
    return dict(sorted(grouped.items()))


def _symbol_bullets(symbols: list) -> str:
    lines: list[str] = []
    for symbol in symbols:
        suffix = f"`{symbol.signature}`" if symbol.signature else symbol.kind
        doc = f" - {symbol.docstring}" if symbol.docstring else ""
        lines.append(f"- `{symbol.qualname}` ({symbol.kind}) {suffix}{doc}")
    return "\n".join(lines)


def _param_summary(parameters: list) -> str:
    if not parameters:
        return ""
    return ", ".join(
        f"`{item.source}:{item.name}{':' + item.type if item.type else ''}`"
        for item in parameters
    )


def _code_list(values: list[str]) -> str:
    return ", ".join(f"`{item}`" for item in values)


def _data_model_rows(facts: ProjectFacts) -> str:
    rows = [
        "| Model | Kind | Fields | Annotations | Source |",
        "| --- | --- | --- | --- | --- |",
    ]
    for model in facts.data_models:
        rows.append(
            f"| `{model.name}` | {model.kind} | {_code_list(model.fields)} | "
            f"{_code_list(model.annotations)} | "
            f"{_source_link(model.evidence.file, model.evidence.line_start or 1)} |"
        )
    return "\n".join(rows)


def _repository_rows(facts: ProjectFacts) -> str:
    rows = [
        "| Repository | Entity | Base Interface | Source |",
        "| --- | --- | --- | --- |",
    ]
    for repository in facts.repositories:
        rows.append(
            f"| `{repository.name}` | `{repository.entity or ''}` | "
            f"`{repository.base_interface or ''}` | "
            f"{_source_link(repository.evidence.file, repository.evidence.line_start or 1)} |"
        )
    return "\n".join(rows)


def _service_rows(facts: ProjectFacts) -> str:
    rows = [
        "| Service | Methods | Source |",
        "| --- | --- | --- |",
    ]
    for service in facts.services:
        rows.append(
            f"| `{service.name}` | {_code_list(service.methods)} | "
            f"{_source_link(service.evidence.file, service.evidence.line_start or 1)} |"
        )
    return "\n".join(rows)


def _evidence_label(evidence: object) -> str:
    line = getattr(evidence, "line_start", None)
    file = getattr(evidence, "file", "")
    return f"`{file}:{line}`" if line else f"`{file}`"


def _source_link(path: str, line: int) -> str:
    return f"`{path}:{line}`"


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(to_jsonable(value), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
