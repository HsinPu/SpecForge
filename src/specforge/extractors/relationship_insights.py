from __future__ import annotations

from specforge.models import (
    ApiContractFact,
    ApiLinkFact,
    ApiRouteFact,
    AssetFact,
    ComponentFact,
    ContractGapFact,
    DataLayerFact,
    DataModelFact,
    Evidence,
    FileFact,
    FormFact,
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


def build_module_boundaries(
    files: list[FileFact],
    pages: list[PageFact],
    components: list[ComponentFact],
    forms: list[FormFact],
    api_routes: list[ApiRouteFact],
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
) -> list[ModuleBoundaryFact]:
    frontend_paths = _dedupe(
        [
            *[page.path for page in pages],
            *[component.path for component in components],
            *[form.source for form in forms],
            *[style.path for style in styles],
            *[asset.source for asset in assets],
            *[state.source for state in state_usages],
        ]
    )
    backend_paths = _dedupe([route.evidence.file for route in api_routes])
    data_paths = _dedupe(
        [
            *[model.path for model in data_models],
            *[repository.path for repository in repositories],
            *[service.path for service in services],
            *[fact.path for fact in data_layers],
        ]
    )
    runtime_paths = _dedupe([fact.path for fact in runtime_configs])
    test_paths = _dedupe([fact.path for fact in test_files] + [test.test_path for test in test_maps])
    known = set(frontend_paths + backend_paths + data_paths + runtime_paths + test_paths)
    shared_paths = [
        fact.path
        for fact in files
        if fact.role in {"source", "entrypoint"} and fact.path not in known
    ]

    return [
        _boundary(
            "Frontend Surface",
            "frontend",
            frontend_paths,
            [
                f"{len(pages)} page(s)",
                f"{len(components)} component(s)",
                f"{len(forms)} form(s)",
                f"{len(styles)} style file(s)",
                f"{len(state_usages)} state usage(s)",
            ],
            ["backend-api", "runtime-config"],
            files,
        ),
        _boundary(
            "Backend API Surface",
            "backend-api",
            backend_paths,
            [f"{len(api_routes)} backend route(s)", "route and handler contracts"],
            ["data-layer", "runtime-config"],
            files,
        ),
        _boundary(
            "Data Layer",
            "data-layer",
            data_paths,
            [
                f"{len(data_models)} data model(s)",
                f"{len(repositories)} repository/repositories",
                f"{len(services)} service(s)",
                f"{len(data_layers)} persistence fact(s)",
            ],
            ["runtime-config"],
            files,
        ),
        _boundary(
            "Runtime Configuration",
            "runtime-config",
            runtime_paths,
            [f"{len(runtime_configs)} config fact(s)", "ports, env keys, services, build commands"],
            [],
            files,
        ),
        _boundary(
            "Tests",
            "tests",
            test_paths,
            [f"{len(test_maps)} mapped test entry/entries", "behavior parity evidence"],
            ["frontend", "backend-api", "data-layer"],
            files,
        ),
        _boundary(
            "Shared Source",
            "shared",
            shared_paths,
            ["source files not classified into a stronger boundary"],
            ["runtime-config"],
            files,
        ),
    ]


def build_refactor_findings(
    files: list[FileFact],
    api_links: list[ApiLinkFact],
    api_routes: list[ApiRouteFact],
    _api_contracts: list[ApiContractFact],
    test_maps: list[TestMapFact],
    contract_gaps: list[ContractGapFact],
) -> list[RefactorFindingFact]:
    findings: list[RefactorFindingFact] = []
    for link in api_links:
        if link.matched_route is None:
            findings.append(
                RefactorFindingFact(
                    title="Unmatched frontend API call",
                    severity="medium",
                    subject=f"{link.method or 'ANY'} {link.endpoint}",
                    detail=f"`{link.source}` calls an endpoint that did not match a scanned backend route.",
                    recommendation="Confirm whether this is an external API, missing backend route, or extractor gap before rebuilding.",
                    evidence=link.evidence,
                )
            )

    matched_routes = {
        (link.matched_method, link.matched_route)
        for link in api_links
        if link.matched_route
    }
    for route in api_routes:
        if (route.method, route.path) in matched_routes or ("ANY", route.path) in matched_routes:
            continue
        findings.append(
            RefactorFindingFact(
                title="Backend route has no detected frontend caller",
                severity="low",
                subject=f"{route.method} {route.path}",
                detail="This route may be server-only, externally consumed, or missed by frontend extraction.",
                recommendation="Keep the route contract, but mark consumer behavior as unknown until confirmed.",
                evidence=[route.evidence],
            )
        )

    unknown_contract_count = len(
        {
            gap.contract
            for gap in contract_gaps
            if gap.gap_type.startswith("unknown-")
        }
    )
    if unknown_contract_count:
        findings.append(
            RefactorFindingFact(
                title="API contracts have unknown fields",
                severity="medium",
                subject="api-contracts",
                detail=f"{unknown_contract_count} API contract(s) have unknown request, response, status, or error hints.",
                recommendation="Do not invent schemas during rebuild; add parser support or manual spec notes.",
                evidence=_dedupe_evidence(
                    [evidence for gap in contract_gaps for evidence in gap.evidence]
                )[:10],
            )
        )

    for test in test_maps:
        if test.target_kind == "unmatched":
            findings.append(
                RefactorFindingFact(
                    title="Test file could not be mapped",
                    severity="low",
                    subject=test.test_path,
                    detail="The test exists but SpecForge could not connect it to an API, component, command, service, repository, or model.",
                    recommendation="Review this test manually and assign it to a rebuild target.",
                    evidence=[test.evidence],
                )
            )

    for file_fact in files:
        if file_fact.size_bytes < 20000:
            continue
        findings.append(
            RefactorFindingFact(
                title="Large file may need a module boundary",
                severity="low",
                subject=file_fact.path,
                detail=f"The file is {file_fact.size_bytes} bytes, which may be too broad for reliable rebuild work.",
                recommendation="Split by observed responsibilities only after tests and feature map coverage are clear.",
                evidence=[file_fact.evidence],
            )
        )

    return findings


def build_contract_gaps(
    api_contracts: list[ApiContractFact],
    api_links: list[ApiLinkFact],
    api_routes: list[ApiRouteFact],
) -> list[ContractGapFact]:
    gaps: list[ContractGapFact] = []
    for contract in api_contracts:
        label = _contract_label(contract)
        if not contract.parameters and not contract.request_body and not contract.request_hints:
            gaps.append(
                ContractGapFact(
                    contract=label,
                    gap_type="unknown-request",
                    detail="No request parameters, request body, or request hints were confirmed.",
                    evidence=[contract.evidence],
                )
            )
        if not contract.response_type and not contract.response_hints:
            gaps.append(
                ContractGapFact(
                    contract=label,
                    gap_type="unknown-response",
                    detail="No response type or response hints were confirmed.",
                    evidence=[contract.evidence],
                )
            )
        if not contract.status_codes:
            gaps.append(
                ContractGapFact(
                    contract=label,
                    gap_type="unknown-status",
                    detail="No status code hints were confirmed.",
                    evidence=[contract.evidence],
                )
            )
        if not contract.error_hints:
            gaps.append(
                ContractGapFact(
                    contract=label,
                    gap_type="unknown-error",
                    detail="No error behavior hints were confirmed.",
                    evidence=[contract.evidence],
                )
            )

    for link in api_links:
        if link.matched_route is None:
            gaps.append(
                ContractGapFact(
                    contract=f"{link.method or 'ANY'} {link.endpoint}",
                    gap_type="unmatched-api-call",
                    detail=f"Frontend source `{link.source}` did not match a scanned backend route.",
                    evidence=link.evidence,
                )
            )

    matched_routes = {
        (link.matched_method, link.matched_route)
        for link in api_links
        if link.matched_route
    }
    for route in api_routes:
        if (route.method, route.path) in matched_routes or ("ANY", route.path) in matched_routes:
            continue
        gaps.append(
            ContractGapFact(
                contract=f"{route.method} {route.path}",
                gap_type="unmatched-backend-route",
                detail="No detected frontend API call matched this backend route.",
                evidence=[route.evidence],
            )
        )

    return gaps


def _boundary(
    name: str,
    kind: str,
    paths: list[str],
    responsibilities: list[str],
    depends_on: list[str],
    files: list[FileFact],
) -> ModuleBoundaryFact:
    file_by_path = {file_fact.path: file_fact for file_fact in files}
    evidence = [
        file_by_path[path].evidence
        for path in paths[:10]
        if path in file_by_path
    ]
    return ModuleBoundaryFact(
        name=name,
        kind=kind,
        paths=_dedupe(paths),
        responsibilities=responsibilities,
        depends_on=depends_on,
        evidence=evidence,
    )


def _contract_label(contract: ApiContractFact) -> str:
    return f"{contract.method} {contract.path}"


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
