from __future__ import annotations

from specforge.models import ProjectFacts
from specforge.renderers.shared import (
    _code_list,
    _data_model_rows,
    _evidence_label,
    _param_summary,
    _repository_rows,
    _service_rows,
    _source_link,
)

def render_backend(facts: ProjectFacts) -> str:
    if not facts.backend_surfaces:
        return "# Backend\n\nNo backend surface was detected by the current extractors.\n"
    sections = ["# Backend\n"]
    for surface in facts.backend_surfaces:
        service_facts = len(facts.services) if surface.framework in {"java-web", "servlet", "spring", "redwood"} else 0
        java_models = len(facts.data_models) if surface.framework in {"java-web", "servlet", "spring"} else 0
        sections.append(
            f"## {surface.framework}\n\n"
            f"- Routes: {surface.route_count}\n"
            f"- Handlers: {surface.handler_count}\n"
            f"- Service symbols: {surface.service_count + service_facts}\n"
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
            f"{_evidence_label(route.evidence)} |"
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
                f"{_evidence_label(route.evidence)} |"
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
            f"{_evidence_label(contract.evidence)} |"
        )
    return "# API Contracts\n\n" + "\n".join(rows) + "\n"

def render_api_links(facts: ProjectFacts) -> str:
    if not facts.api_links:
        return "# API Links\n\nNo frontend-to-backend API links were generated.\n"
    rows = [
        "| Source | Method | Endpoint | Target | Matched Route | Framework | Match | Confidence | Evidence |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for link in facts.api_links:
        evidence = link.evidence[0] if link.evidence else None
        source = _source_link(evidence.file, evidence.line_start or 1) if evidence else ""
        matched = (
            f"`{link.matched_method or ''} {link.matched_route}`"
            if link.matched_route
            else f"`{link.target_kind}`"
        )
        rows.append(
            f"| `{link.source}` | {link.method or ''} | `{link.endpoint}` | "
            f"{link.target_kind} | {matched} | {link.matched_framework or ''} | "
            f"{link.match_type} | {link.confidence} | {source} |"
        )
    return "# API Links\n\n" + "\n".join(rows) + "\n"
