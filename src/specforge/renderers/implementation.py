from __future__ import annotations

from specforge.models import Gap, ProjectFacts
from specforge.renderers.shared import _param_summary, _symbols_by_path

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
    feature_map = "\n".join(
        f"- {feature.name}: commands=[{', '.join(feature.commands) or 'none'}] "
        f"implementation=[{_join_limited(feature.implementation_sources, 8) or 'unknown'}] "
        f"reasons=[{_join_limited(feature.implementation_reasons, 8) or 'unknown'}] "
        f"calls=[{', '.join(feature.api_calls) or 'none'}] "
        f"routes=[{', '.join(feature.backend_routes) or 'none'}] "
        f"tests=[{_join_limited(feature.tests, 12) or 'unknown'}]"
        for feature in facts.feature_maps
    ) or "- no feature map entries generated"
    module_boundaries = "\n".join(
        f"- {boundary.name} ({boundary.kind}) paths={len(boundary.paths)} "
        f"depends_on=[{', '.join(boundary.depends_on) or 'none'}]"
        for boundary in facts.module_boundaries
    ) or "- no module boundaries generated"
    contract_gaps = "\n".join(
        f"- `{gap.contract}` {gap.gap_type}: {gap.detail}"
        for gap in facts.contract_gaps
    ) or "- no contract gaps generated"
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

## Feature Map Contract

{feature_map}

## Module Boundary Contract

{module_boundaries}

## Contract Gap Contract

{contract_gaps}

## Reimplementation Workflow

1. Read `overview.md` and `architecture.md`.
2. Read `feature-map.md` and `rebuild-spec.md` to choose implementation slices.
3. Read `contract-gaps.md`; keep unknown schemas and behavior unknown until confirmed.
4. Recreate API links from `api-links.md`; treat unmatched calls/routes as gaps.
5. Recreate backend route contracts from `backend.md`, `api-routes.md`, and `api-contracts.md`.
6. Recreate Java Web contracts from `java-web.md`, `spring.md`, `servlets.md`, `jsp-pages.md`, and `data-models.md`.
7. Recreate frontend pages and routes from `pages.md`, `frontend-routes.md`, and `frontend-map.md`.
8. Recreate forms and API integrations from `forms.md`, `api-calls.md`, and `api-links.md`.
9. Recreate data and persistence skeletons from `data-models.md` and `data-layer.md`.
10. Recreate runtime setup from `runtime-config.md`, `entrypoints.md`, and `commands.md`.
11. Recreate components and state surfaces from `components.md` and `state.md`.
12. Recreate styles and static assets from `styles.md` and `assets.md`.
13. Recreate modules from `modules.md`, `symbols.md`, and `module-boundaries.md`.
14. Use `imports.md`, `frameworks.md`, and `dependencies.md` to choose equivalent libraries.
15. Port or recreate tests listed in `tests.md`, using `test-map.md` to prioritize targets.
16. Use `refactor-plan.md` for cleanup sequencing after behavior is covered.
17. Resolve every item in `gaps-and-questions.md` before declaring parity.

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

## Project Shape Hint

{_project_shape_hint(facts)}

## Source Of Truth Order

1. `facts.json` and `traceability.json` for observed facts.
2. `api-links.md` for frontend-to-backend wiring and unmatched API gaps.
3. `frameworks.md`, `backend.md`, `api-routes.md`, and `api-contracts.md` for backend contracts.
4. `java-web.md`, `spring.md`, `servlets.md`, `jsp-pages.md`, `data-models.md`, and `data-layer.md` for Java Web, legacy page, and persistence contracts.
5. `frontend.md`, `pages.md`, `forms.md`, `components.md`, `frontend-routes.md`, `api-calls.md`, `state.md`, `styles.md`, `assets.md`, and `frontend-map.md` for frontend product surfaces.
6. `feature-map.md`, `rebuild-spec.md`, `module-boundaries.md`, `contract-gaps.md`, and `refactor-plan.md` for rebuild and refactor sequencing.
7. `runtime-config.md`, `entrypoints.md`, `commands.md`, `modules.md`, `symbols.md`, `tests.md`, and `test-map.md` for implementation targets.
8. `spec-diff.md` for changes since the previous update when available.
9. `implementation-guide.md` for rebuild workflow.
10. `gaps-and-questions.md` for unresolved items.

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
- Feature map entries detected: {len(facts.feature_maps)}
- Module boundaries detected: {len(facts.module_boundaries)}
- Refactor findings detected: {len(facts.refactor_findings)}
- Contract gaps detected: {len(facts.contract_gaps)}
- Gaps detected: {len(gaps)}

## Starting Prompt

Implement `{facts.name}` from this SpecForge bundle. First summarize feature-map entries, rebuild targets, module boundaries, refactor findings, contract gaps, backend routes, frontend routes/screens, pages/forms/components, API calls, API links, unmatched API calls, unmatched backend routes, API contracts with unknown request/response/status/error fields, Java Web Servlet/JSP surface, state usage, styles, assets, data models, data layer, runtime config, public entrypoints, commands, modules, symbols, test map, unmatched tests, spec diff, and unresolved gaps. Then propose an implementation plan that preserves observed behavior before writing code.
"""


def _project_shape_hint(facts: ProjectFacts) -> str:
    has_cli = bool(facts.commands or facts.entrypoints)
    has_backend = bool(facts.api_routes or facts.api_contracts)
    has_frontend = bool(facts.frontend_routes or facts.pages or facts.components)
    if has_cli and not has_backend and not has_frontend:
        return (
            "- This scan looks CLI/library-oriented: prioritize `commands.md`, "
            "`entrypoints.md`, `modules.md`, `symbols.md`, `tests.md`, and `test-map.md`.\n"
            "- Treat `feature-map.md` command entries as rebuild slices even when API links are empty."
        )
    if has_backend or has_frontend:
        return (
            "- This scan has application surfaces: prioritize `api-links.md`, `feature-map.md`, "
            "`backend.md`, frontend/page documents, data/config, then tests."
        )
    return (
        "- This scan has no strong application surface yet: prioritize inventory, entrypoints, "
        "modules, symbols, runtime config, tests, and unresolved gaps."
    )


def _join_limited(values: list[str], limit: int) -> str:
    visible = values[:limit]
    suffix = f", ... {len(values) - limit} more" if len(values) > limit else ""
    return ", ".join(visible) + suffix if visible else ""
