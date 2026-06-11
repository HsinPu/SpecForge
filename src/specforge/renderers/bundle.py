from __future__ import annotations

import json
from pathlib import Path

from specforge.models import Gap, ProjectFacts, TraceClaim, to_jsonable
from specforge.renderers.backend import (
    render_api_contracts,
    render_api_links,
    render_api_routes,
    render_backend,
    render_data_layer,
    render_data_models,
    render_java_web,
    render_jsp_pages,
    render_servlets,
    render_spring,
)
from specforge.renderers.frontend import (
    render_api_calls,
    render_assets,
    render_components,
    render_forms,
    render_frontend,
    render_frontend_map,
    render_frontend_routes,
    render_pages,
    render_state,
    render_styles,
)
from specforge.renderers.implementation import render_implementation_guide, render_llm_handoff
from specforge.renderers.overview import (
    render_architecture,
    render_dependencies,
    render_frameworks,
    render_imports,
    render_inventory,
    render_modules,
    render_overview,
    render_summary,
    render_symbols,
)
from specforge.renderers.supporting import (
    render_commands,
    render_entrypoints,
    render_evidence,
    render_gaps,
    render_runtime_config,
    render_test_map,
    render_tests,
)

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

def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(to_jsonable(value), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
