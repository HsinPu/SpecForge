from __future__ import annotations

import re

from specforge.models import (
    ApiContractFact,
    ApiLinkFact,
    ApiRouteFact,
    AssetFact,
    CommandFact,
    ComponentFact,
    ContractGapFact,
    DataLayerFact,
    DataModelFact,
    EntrypointFact,
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
    entrypoints: list[EntrypointFact],
    commands: list[CommandFact],
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
    file_paths = {fact.path for fact in files}
    cli_paths = _dedupe(
        [
            *[command.path for command in commands],
            *[
                path
                for command in commands
                for path in _command_related_source_paths(command, files)
            ],
            *[
                path
                for entrypoint in entrypoints
                if (path := _entrypoint_file_path(entrypoint, file_paths)) is not None
            ],
        ]
    )
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
    known = set(cli_paths + frontend_paths + backend_paths + data_paths + runtime_paths + test_paths)
    shared_paths = [
        fact.path
        for fact in files
        if fact.path not in known and _is_shared_source_candidate(fact)
    ]

    return [
        _boundary(
            "CLI Surface",
            "cli",
            cli_paths,
            [
                f"{len(entrypoints)} entrypoint(s)",
                f"{len(commands)} command(s)",
            ],
            ["runtime-config", "shared"],
            files,
        ),
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
        if not _is_large_file_refactor_candidate(file_fact):
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


def _entrypoint_file_path(entrypoint: EntrypointFact, file_paths: set[str]) -> str | None:
    candidates = [
        entrypoint.path.replace("\\", "/"),
        entrypoint.path.removeprefix("./").replace("\\", "/"),
    ]
    if ":" in entrypoint.path:
        module = entrypoint.path.split(":", 1)[0].replace(".", "/")
        candidates.extend([f"{module}.py", f"src/{module}.py"])
    for candidate in candidates:
        if candidate in file_paths:
            return candidate
    return None


def _is_large_file_refactor_candidate(file_fact: FileFact) -> bool:
    implementation_roles = {
        "api",
        "data-layer",
        "data-model",
        "entrypoint",
        "frontend-page",
        "repository",
        "service",
        "source",
        "test",
        "webapp",
    }
    non_implementation_languages = {
        "dockerfile",
        "font",
        "gitignore",
        "image",
        "json",
        "lockfile",
        "markdown",
        "svg",
        "toml",
        "yaml",
        "yml",
    }
    path = file_fact.path.lower()
    if file_fact.role not in implementation_roles:
        return False
    if file_fact.language in non_implementation_languages:
        return False
    if path.endswith(("package-lock.json", "pnpm-lock.yaml", "yarn.lock")):
        return False
    return True


def _is_shared_source_candidate(file_fact: FileFact) -> bool:
    if file_fact.role not in {"source", "entrypoint"}:
        return False
    non_source_languages = {
        "config",
        "dockerfile",
        "font",
        "gitignore",
        "gradle",
        "image",
        "json",
        "license",
        "lockfile",
        "markdown",
        "nix",
        "properties",
        "svg",
        "toml",
        "xml",
        "yaml",
    }
    path = file_fact.path.lower()
    name = path.rsplit("/", 1)[-1]
    if file_fact.language in non_source_languages:
        return False
    if path.startswith(("docs/", "openspec/", ".github/", ".changeset/")):
        return False
    if "config" in name or name in {"build.js", "build.ts"}:
        return False
    return True


def _command_related_source_paths(command: CommandFact, files: list[FileFact]) -> list[str]:
    command_tokens = _tokens(command.name)
    if not command_tokens:
        return []
    paths: list[str] = []
    for file_fact in files:
        if file_fact.path == command.path or not _is_shared_source_candidate(file_fact):
            continue
        if _is_command_source_path(file_fact.path, command.name, command_tokens):
            paths.append(file_fact.path)
    return _dedupe(paths)


def _is_command_source_path(path: str, command_name: str, command_tokens: set[str]) -> bool:
    stem = path.replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()
    if stem.startswith("__") and stem.endswith("__"):
        return False
    if stem == command_name.lower():
        return True
    return _tokens(stem) == command_tokens


def _tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    return {
        item.lower()
        for item in re.findall(r"[A-Za-z][A-Za-z0-9]*", value)
        if item.lower() not in {"api", "app", "src", "main", "test", "tests"}
    }


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
