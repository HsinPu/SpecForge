from __future__ import annotations

from specforge.models import Evidence, ProjectFacts, TraceClaim


def build_trace_claims(facts: ProjectFacts) -> list[TraceClaim]:
    claims: list[TraceClaim] = []
    claims.append(
        TraceClaim(
            claim_id="PROJECT-001",
            claim=f"Project root is named {facts.name}",
            claim_type="project",
            confidence=1.0,
            evidence=[Evidence(file=".", kind="directory", note=facts.root)],
        )
    )

    for index, (language, count) in enumerate(facts.languages.items(), start=1):
        claims.append(
            TraceClaim(
                claim_id=f"LANG-{index:03d}",
                claim=f"Project contains {count} {language} file(s)",
                claim_type="language",
                confidence=1.0,
                evidence=[
                    file_fact.evidence
                    for file_fact in facts.files
                    if file_fact.language == language
                ][:10],
            )
        )

    for index, dependency in enumerate(facts.dependencies, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"DEP-{index:03d}",
                claim=f"Dependency {dependency.name} is declared for {dependency.scope}",
                claim_type="dependency",
                confidence=1.0,
                evidence=[dependency.evidence],
            )
        )

    for index, entrypoint in enumerate(facts.entrypoints, start=1):
        command = f" command {entrypoint.command}" if entrypoint.command else ""
        claims.append(
            TraceClaim(
                claim_id=f"ENTRY-{index:03d}",
                claim=f"Entrypoint{command} resolves to {entrypoint.path}",
                claim_type="entrypoint",
                confidence=0.95,
                evidence=[entrypoint.evidence],
            )
        )

    for index, command in enumerate(facts.commands, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"CMD-{index:03d}",
                claim=f"CLI command {command.name} is declared in {command.path}",
                claim_type="command",
                confidence=0.9,
                evidence=[command.evidence],
            )
        )

    for index, framework in enumerate(facts.frameworks, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"FW-{index:03d}",
                claim=f"{framework.category} framework {framework.name} was detected from {framework.source}",
                claim_type="framework",
                confidence=framework.confidence,
                evidence=[framework.evidence],
            )
        )

    for index, route in enumerate(facts.api_routes, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"API-{index:03d}",
                claim=f"{route.method} {route.path} is handled by {route.handler or 'unknown handler'}",
                claim_type="api-route",
                confidence=0.85,
                evidence=[route.evidence],
            )
        )

    for index, component in enumerate(facts.components, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"CMP-{index:03d}",
                claim=f"Frontend component {component.name} is defined in {component.path}",
                claim_type="component",
                confidence=0.85,
                evidence=[component.evidence],
            )
        )

    for index, route in enumerate(facts.frontend_routes, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"FR-{index:03d}",
                claim=f"Frontend route {route.route} is associated with {route.path}",
                claim_type="frontend-route",
                confidence=0.85,
                evidence=[route.evidence],
            )
        )

    for index, api_call in enumerate(facts.api_calls, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"CALL-{index:03d}",
                claim=(
                    f"{api_call.client} call to {api_call.endpoint} appears in {api_call.path}"
                    + (f" ({api_call.context})" if api_call.context else "")
                ),
                claim_type="api-call",
                confidence=0.8,
                evidence=[api_call.evidence],
            )
        )

    for index, api_link in enumerate(facts.api_links, start=1):
        target = (
            f"{api_link.matched_method or ''} {api_link.matched_route}"
            if api_link.matched_route
            else "unmatched backend route"
        )
        claims.append(
            TraceClaim(
                claim_id=f"LINK-{index:03d}",
                claim=(
                    f"API call {api_link.method or 'ANY'} {api_link.endpoint} links to "
                    f"{target} with {api_link.confidence} confidence"
                ),
                claim_type="api-link",
                confidence=0.85 if api_link.confidence == "high" else 0.65 if api_link.confidence == "medium" else 0.4,
                evidence=api_link.evidence,
                status="observed" if api_link.matched_route else "gap",
            )
        )

    for index, page in enumerate(facts.pages, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"PAGE-{index:03d}",
                claim=f"Frontend page {page.path} is associated with route {page.route}",
                claim_type="page",
                confidence=0.85,
                evidence=[page.evidence],
            )
        )

    for index, form in enumerate(facts.forms, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"FORM-{index:03d}",
                claim=f"Form in {form.source} submits to {form.action or 'unknown action'}",
                claim_type="form",
                confidence=0.85,
                evidence=[form.evidence],
            )
        )

    for index, asset in enumerate(facts.assets, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"ASSET-{index:03d}",
                claim=f"{asset.asset_kind} asset {asset.asset_path} is referenced by {asset.source}",
                claim_type="asset",
                confidence=0.8,
                evidence=[asset.evidence],
            )
        )

    for index, style in enumerate(facts.styles, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"STYLE-{index:03d}",
                claim=f"Style file {style.path} defines {len(style.selectors)} selector(s)",
                claim_type="style",
                confidence=0.8,
                evidence=[style.evidence],
            )
        )

    for index, state_usage in enumerate(facts.state_usages, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"STATE-{index:03d}",
                claim=f"{state_usage.library} {state_usage.usage} usage {state_usage.name} appears in {state_usage.source}",
                claim_type="state-usage",
                confidence=0.8,
                evidence=[state_usage.evidence],
            )
        )

    for index, frontend_map in enumerate(facts.frontend_maps, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"FMAP-{index:03d}",
                claim=f"Frontend map entry exists for route {frontend_map.route or frontend_map.page or 'component surface'}",
                claim_type="frontend-map",
                confidence=0.75,
                evidence=frontend_map.evidence,
            )
        )

    for index, surface in enumerate(facts.java_web_surfaces, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"JAVA-WEB-{index:03d}",
                claim=(
                    "Java Web surface includes "
                    f"{surface.servlet_count} servlet(s), {surface.jsp_page_count} JSP page(s), "
                    f"{surface.data_model_count} data model(s), "
                    f"{surface.repository_count} repository/repositories, and "
                    f"{surface.service_count} service(s)"
                ),
                claim_type="java-web-surface",
                confidence=0.85,
                evidence=surface.evidence,
            )
        )

    for index, servlet in enumerate(facts.servlets, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"SERVLET-{index:03d}",
                claim=f"Servlet {servlet.name} maps {', '.join(servlet.url_patterns)}",
                claim_type="servlet",
                confidence=0.9,
                evidence=[servlet.evidence],
            )
        )

    for index, page in enumerate(facts.jsp_pages, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"JSP-{index:03d}",
                claim=f"JSP page {page.path} is exposed as {page.route}",
                claim_type="jsp-page",
                confidence=0.85,
                evidence=[page.evidence],
            )
        )

    for index, model in enumerate(facts.data_models, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"DATA-{index:03d}",
                claim=f"{model.kind} model {model.name} is declared in {model.path}",
                claim_type="data-model",
                confidence=0.85,
                evidence=[model.evidence],
            )
        )

    for index, repository in enumerate(facts.repositories, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"REPO-{index:03d}",
                claim=f"Repository {repository.name} is declared in {repository.path}",
                claim_type="repository",
                confidence=0.85,
                evidence=[repository.evidence],
            )
        )

    for index, service in enumerate(facts.services, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"SERVICE-{index:03d}",
                claim=f"Service {service.name} is declared in {service.path}",
                claim_type="service",
                confidence=0.85,
                evidence=[service.evidence],
            )
        )

    for index, contract in enumerate(facts.api_contracts, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"CONTRACT-{index:03d}",
                claim=f"API contract skeleton exists for {contract.method} {contract.path}",
                claim_type="api-contract",
                confidence=0.8,
                evidence=[contract.evidence],
            )
        )

    for index, detail in enumerate(facts.contract_details, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"CONTRACT-DETAIL-{index:03d}",
                claim=(
                    f"Contract hints for {detail.method} {detail.path}: "
                    f"request={len(detail.request_hints)}, response={len(detail.response_hints)}, "
                    f"status={len(detail.status_codes)}, error={len(detail.error_hints)}"
                ),
                claim_type="contract-detail",
                confidence=0.75,
                evidence=[detail.evidence],
            )
        )

    for index, data_layer in enumerate(facts.data_layers, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"DATA-LAYER-{index:03d}",
                claim=f"Data-layer fact {data_layer.kind} {data_layer.name} appears in {data_layer.path}",
                claim_type="data-layer",
                confidence=0.8,
                evidence=[data_layer.evidence],
            )
        )

    for index, runtime_config in enumerate(facts.runtime_configs, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"RUNTIME-{index:03d}",
                claim=f"Runtime config {runtime_config.kind} appears in {runtime_config.path}",
                claim_type="runtime-config",
                confidence=0.8,
                evidence=[runtime_config.evidence],
            )
        )

    for index, test_map in enumerate(facts.test_maps, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"TEST-MAP-{index:03d}",
                claim=(
                    f"Test {test_map.test_path} maps to "
                    f"{test_map.target_kind} {test_map.target or 'unmatched'}"
                ),
                claim_type="test-map",
                confidence=0.75 if test_map.confidence == "high" else 0.55 if test_map.confidence == "medium" else 0.35,
                evidence=[test_map.evidence],
                status="observed" if test_map.target_kind != "unmatched" else "gap",
            )
        )

    for index, symbol in enumerate(facts.symbols, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"SYM-{index:03d}",
                claim=f"{symbol.kind} {symbol.qualname} is defined in {symbol.path}",
                claim_type="symbol",
                confidence=1.0,
                evidence=[symbol.evidence],
            )
        )

    for index, import_fact in enumerate(facts.imports, start=1):
        target = import_fact.module or ", ".join(import_fact.names)
        claims.append(
            TraceClaim(
                claim_id=f"IMP-{index:03d}",
                claim=f"{import_fact.path} imports {target}",
                claim_type="import",
                confidence=1.0,
                evidence=[import_fact.evidence],
            )
        )

    for index, issue in enumerate(facts.extraction_issues, start=1):
        claims.append(
            TraceClaim(
                claim_id=f"ISSUE-{index:03d}",
                claim=f"{issue.extractor} could not fully parse {issue.path}: {issue.message}",
                claim_type="extraction-issue",
                confidence=1.0,
                evidence=[issue.evidence],
                status="gap",
            )
        )

    return claims
