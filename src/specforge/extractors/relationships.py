from __future__ import annotations

import re

from specforge.extractors.relationship_insights import (
    build_contract_gaps,
    build_module_boundaries,
    build_refactor_findings,
)
from specforge.models import (
    ApiCallFact,
    ApiContractFact,
    ApiLinkFact,
    ApiRouteFact,
    AssetFact,
    ComponentFact,
    ContractGapFact,
    DataLayerFact,
    DataModelFact,
    Evidence,
    FeatureMapFact,
    FileFact,
    FormFact,
    FrontendRouteFact,
    ModuleBoundaryFact,
    PageFact,
    RefactorFindingFact,
    RepositoryFact,
    RuntimeConfigFact,
    ServiceFact,
    StateUsageFact,
    StyleFact,
    TestMapFact,
)


def build_relationship_facts(
    files: list[FileFact],
    frontend_routes: list[FrontendRouteFact],
    pages: list[PageFact],
    components: list[ComponentFact],
    forms: list[FormFact],
    api_calls: list[ApiCallFact],
    api_routes: list[ApiRouteFact],
    api_contracts: list[ApiContractFact],
    api_links: list[ApiLinkFact],
    data_models: list[DataModelFact],
    repositories: list[RepositoryFact],
    services: list[ServiceFact],
    data_layers: list[DataLayerFact],
    runtime_configs: list[RuntimeConfigFact],
    test_maps: list[TestMapFact],
    styles: list[StyleFact],
    assets: list[AssetFact],
    state_usages: list[StateUsageFact],
    test_files: list[FileFact],
) -> tuple[
    list[FeatureMapFact],
    list[ModuleBoundaryFact],
    list[RefactorFindingFact],
    list[ContractGapFact],
]:
    contract_gaps = build_contract_gaps(api_contracts, api_links, api_routes)
    feature_maps = _build_feature_maps(
        frontend_routes,
        pages,
        components,
        forms,
        api_calls,
        api_routes,
        api_contracts,
        api_links,
        data_models,
        repositories,
        services,
        test_maps,
    )
    module_boundaries = build_module_boundaries(
        files,
        pages,
        components,
        forms,
        api_routes,
        data_models,
        repositories,
        services,
        data_layers,
        runtime_configs,
        test_maps,
        styles,
        assets,
        state_usages,
        test_files,
    )
    refactor_findings = build_refactor_findings(
        files,
        api_links,
        api_routes,
        api_contracts,
        test_maps,
        contract_gaps,
    )
    return feature_maps, module_boundaries, refactor_findings, contract_gaps


def _build_feature_maps(
    frontend_routes: list[FrontendRouteFact],
    pages: list[PageFact],
    components: list[ComponentFact],
    forms: list[FormFact],
    api_calls: list[ApiCallFact],
    api_routes: list[ApiRouteFact],
    api_contracts: list[ApiContractFact],
    api_links: list[ApiLinkFact],
    data_models: list[DataModelFact],
    repositories: list[RepositoryFact],
    services: list[ServiceFact],
    test_maps: list[TestMapFact],
) -> list[FeatureMapFact]:
    features: list[FeatureMapFact] = []
    seen: set[str] = set()

    for link in api_links:
        key = f"link:{link.source}:{link.method}:{link.endpoint}:{link.matched_route}"
        if key in seen:
            continue
        seen.add(key)
        route = _matching_route(link, api_routes)
        contract = _matching_contract(link, api_contracts)
        calls = [
            call
            for call in api_calls
            if call.endpoint == link.endpoint and call.path == link.source
        ]
        source_tokens = _tokens(link.endpoint)
        source_tokens.update(_tokens(link.matched_route or ""))
        related_services = _related_names(services, source_tokens)
        related_repositories = _related_names(repositories, source_tokens)
        related_models = _related_names(data_models, source_tokens)
        related_components = [
            component.name
            for component in components
            if component.path == link.source or _tokens(component.name) & source_tokens
        ]
        related_pages = [
            page.route
            for page in pages
            if page.path == link.source or _tokens(page.route) & source_tokens
        ]
        related_routes = [
            route_fact.route
            for route_fact in frontend_routes
            if route_fact.path == link.source or _tokens(route_fact.route) & source_tokens
        ]
        related_forms = [
            f"{form.method or 'GET'} {form.action or 'unknown'}"
            for form in forms
            if form.source == link.source
            or form.action in {link.endpoint, link.matched_route}
            or _tokens(form.action or "") & source_tokens
        ]
        related_tests = _related_tests(test_maps, source_tokens, related_components, related_services)
        backend_routes = [_route_label(route)] if route else []
        contracts = [_contract_label(contract)] if contract else []
        evidence = _dedupe_evidence(
            [
                *link.evidence,
                *[call.evidence for call in calls],
                *([route.evidence] if route else []),
                *([contract.evidence] if contract else []),
            ]
        )
        features.append(
            FeatureMapFact(
                name=_feature_name(link.endpoint, link.matched_route),
                summary=(
                    f"{link.method or 'ANY'} {link.endpoint} links frontend source "
                    f"`{link.source}` to `{link.matched_route or 'unmatched backend route'}`."
                ),
                frontend_sources=_dedupe([link.source]),
                frontend_routes=_dedupe(related_routes),
                pages=_dedupe(related_pages),
                components=_dedupe(related_components),
                forms=_dedupe(related_forms),
                api_calls=_dedupe([_call_label(call) for call in calls] or [f"{link.method or 'ANY'} {link.endpoint}"]),
                backend_routes=_dedupe(backend_routes),
                contracts=_dedupe(contracts),
                services=_dedupe(related_services),
                repositories=_dedupe(related_repositories),
                data_models=_dedupe(related_models),
                tests=_dedupe(related_tests),
                confidence=link.confidence,
                evidence=evidence,
            )
        )

    linked_routes = {
        (link.matched_method, link.matched_route)
        for link in api_links
        if link.matched_route
    }
    for route in api_routes:
        if (route.method, route.path) in linked_routes or ("ANY", route.path) in linked_routes:
            continue
        key = f"route:{route.method}:{route.path}"
        if key in seen:
            continue
        seen.add(key)
        tokens = _tokens(route.path)
        features.append(
            FeatureMapFact(
                name=_feature_name(route.path, None),
                summary=f"{route.method} {route.path} is a backend route with no matched frontend call.",
                frontend_sources=[],
                frontend_routes=[],
                pages=[],
                components=[],
                forms=[],
                api_calls=[],
                backend_routes=[_route_label(route)],
                contracts=[
                    _contract_label(contract)
                    for contract in api_contracts
                    if contract.path == route.path and contract.method == route.method
                ],
                services=_dedupe(_related_names(services, tokens)),
                repositories=_dedupe(_related_names(repositories, tokens)),
                data_models=_dedupe(_related_names(data_models, tokens)),
                tests=_dedupe(_related_tests(test_maps, tokens, [], [])),
                confidence="low",
                evidence=[route.evidence],
            )
        )

    return features


def _matching_route(link: ApiLinkFact, routes: list[ApiRouteFact]) -> ApiRouteFact | None:
    for route in routes:
        if route.path == link.matched_route and route.method == link.matched_method:
            return route
    for route in routes:
        if route.path == link.matched_route:
            return route
    return None


def _matching_contract(link: ApiLinkFact, contracts: list[ApiContractFact]) -> ApiContractFact | None:
    for contract in contracts:
        if contract.path == link.matched_route and contract.method == link.matched_method:
            return contract
    for contract in contracts:
        if contract.path == link.endpoint and (not link.method or contract.method == link.method):
            return contract
    return None


def _related_names(items: list, tokens: set[str]) -> list[str]:
    names: list[str] = []
    for item in items:
        name = getattr(item, "name", "")
        path = getattr(item, "path", "")
        entity = getattr(item, "entity", "") or ""
        if _tokens(name) & tokens or _tokens(path) & tokens or _tokens(entity) & tokens:
            names.append(name)
    return names


def _related_tests(
    test_maps: list[TestMapFact],
    tokens: set[str],
    components: list[str],
    services: list[str],
) -> list[str]:
    names = set(components + services)
    tests: list[str] = []
    for test in test_maps:
        target = test.target or ""
        if _tokens(test.test_path) & tokens or _tokens(target) & tokens or target in names:
            tests.append(f"{test.test_path} -> {test.target_kind}:{target or 'unmatched'}")
    return tests


def _feature_name(endpoint: str, matched_route: str | None) -> str:
    tokens = [
        token
        for token in _tokens(endpoint or matched_route or "feature")
        if token not in {"api", "v1", "v2", "id"}
    ]
    if not tokens:
        return "General"
    return " ".join(token.capitalize() for token in sorted(tokens)[:2])


def _tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    return {
        item.lower()
        for item in re.findall(r"[A-Za-z][A-Za-z0-9]*", value)
        if item.lower() not in {"api", "app", "src", "main", "test", "tests"}
    }


def _route_label(route: ApiRouteFact) -> str:
    return f"{route.method} {route.path}"


def _contract_label(contract: ApiContractFact) -> str:
    return f"{contract.method} {contract.path}"


def _call_label(call: ApiCallFact) -> str:
    return f"{call.method or 'ANY'} {call.endpoint}"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _dedupe_evidence(values: list[Evidence]) -> list[Evidence]:
    seen: set[tuple[str, int | None, str]] = set()
    result: list[Evidence] = []
    for evidence in values:
        key = (evidence.file, evidence.line_start, evidence.kind)
        if key in seen:
            continue
        seen.add(key)
        result.append(evidence)
    return result
