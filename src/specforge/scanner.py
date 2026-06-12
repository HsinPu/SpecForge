from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from specforge.extractors.api_links import build_api_links
from specforge.extractors.backend import extract_backend_facts
from specforge.extractors.contracts import build_api_contracts, extract_contract_details
from specforge.extractors.data_layer import extract_data_layer_facts
from specforge.extractors.frameworks import detect_frameworks
from specforge.extractors.frontend import build_frontend_surfaces, extract_frontend_facts
from specforge.extractors.java_web import extract_java_web_facts
from specforge.extractors.python_ast import extract_python_facts
from specforge.extractors.relationships import build_relationship_facts
from specforge.extractors.runtime_config import extract_runtime_config_facts
from specforge.extractors.static_frontend import build_frontend_maps, extract_static_frontend_facts
from specforge.extractors.test_map import build_test_maps
from specforge.extractors.typescript_text import extract_typescript_facts
from specforge.inventory import (
    collect_dependencies,
    collect_entrypoints,
    file_fact,
    iter_source_files,
)
from specforge.models import (
    ApiCallFact,
    ApiContractFact,
    ApiLinkFact,
    ApiRouteFact,
    AssetFact,
    BackendSurfaceFact,
    CommandFact,
    ComponentFact,
    ContractDetailFact,
    DataLayerFact,
    DataModelFact,
    EntrypointFact,
    ExtractionIssue,
    FileFact,
    FormFact,
    FrameworkFact,
    FrontendMapFact,
    FrontendRouteFact,
    FrontendSurfaceFact,
    ImportFact,
    JavaWebSurfaceFact,
    JspPageFact,
    ContractGapFact,
    PageFact,
    ProjectFacts,
    RepositoryFact,
    RefactorFindingFact,
    RuntimeConfigFact,
    ServiceFact,
    ServletFact,
    StateUsageFact,
    StyleFact,
    SymbolFact,
    TestMapFact,
    FeatureMapFact,
    ModuleBoundaryFact,
)


@dataclass(frozen=True)
class LanguageScan:
    imports: list[ImportFact]
    symbols: list[SymbolFact]
    commands: list[CommandFact]
    issues: list[ExtractionIssue]


@dataclass(frozen=True)
class BackendScan:
    api_routes: list[ApiRouteFact]
    backend_surfaces: list[BackendSurfaceFact]
    java_web_surfaces: list[JavaWebSurfaceFact]
    servlets: list[ServletFact]
    jsp_pages: list[JspPageFact]
    data_models: list[DataModelFact]
    repositories: list[RepositoryFact]
    services: list[ServiceFact]
    contract_details: list[ContractDetailFact]
    api_contracts: list[ApiContractFact]


@dataclass(frozen=True)
class FrontendScan:
    frontend_routes: list[FrontendRouteFact]
    components: list[ComponentFact]
    api_calls: list[ApiCallFact]
    state_usages: list[StateUsageFact]
    pages: list[PageFact]
    forms: list[FormFact]
    assets: list[AssetFact]
    styles: list[StyleFact]


@dataclass(frozen=True)
class ConnectedScan:
    api_links: list[ApiLinkFact]
    api_calls: list[ApiCallFact]
    data_layers: list[DataLayerFact]
    runtime_configs: list[RuntimeConfigFact]
    config_files: list[FileFact]
    test_files: list[FileFact]
    test_maps: list[TestMapFact]
    backend_surfaces: list[BackendSurfaceFact]
    frontend_maps: list[FrontendMapFact]
    frontend_surfaces: list[FrontendSurfaceFact]
    feature_maps: list[FeatureMapFact]
    module_boundaries: list[ModuleBoundaryFact]
    refactor_findings: list[RefactorFindingFact]
    contract_gaps: list[ContractGapFact]


def scan_project(root: str | Path) -> ProjectFacts:
    root_path = Path(root).resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"Project path does not exist: {root_path}")
    if not root_path.is_dir():
        raise NotADirectoryError(f"Project path is not a directory: {root_path}")

    files = list(iter_source_files(root_path))
    file_facts = [file_fact(root_path, path) for path in files]
    dependencies = collect_dependencies(root_path)
    entrypoints = collect_entrypoints(root_path, file_facts)
    language_scan = _scan_language_surfaces(root_path, file_facts)
    frameworks = detect_frameworks(
        root_path,
        file_facts,
        dependencies,
        language_scan.imports,
    )
    backend_scan = _scan_backend_surfaces(
        root_path,
        file_facts,
        language_scan.symbols,
        frameworks,
    )
    frontend_scan = _scan_frontend_surfaces(
        root_path,
        file_facts,
        language_scan.symbols,
        frameworks,
    )
    connected_scan = _build_connected_surfaces(
        root_path,
        file_facts,
        entrypoints,
        frameworks,
        language_scan,
        backend_scan,
        frontend_scan,
    )

    return ProjectFacts(
        root=str(root_path),
        name=root_path.name,
        files=file_facts,
        dependencies=dependencies,
        entrypoints=entrypoints,
        commands=language_scan.commands,
        frameworks=frameworks,
        api_routes=backend_scan.api_routes,
        backend_surfaces=connected_scan.backend_surfaces,
        frontend_routes=frontend_scan.frontend_routes,
        components=frontend_scan.components,
        api_calls=connected_scan.api_calls,
        frontend_surfaces=connected_scan.frontend_surfaces,
        pages=frontend_scan.pages,
        forms=frontend_scan.forms,
        assets=frontend_scan.assets,
        styles=frontend_scan.styles,
        state_usages=frontend_scan.state_usages,
        frontend_maps=connected_scan.frontend_maps,
        java_web_surfaces=backend_scan.java_web_surfaces,
        servlets=backend_scan.servlets,
        jsp_pages=backend_scan.jsp_pages,
        data_models=backend_scan.data_models,
        repositories=backend_scan.repositories,
        services=backend_scan.services,
        api_contracts=backend_scan.api_contracts,
        contract_details=backend_scan.contract_details,
        api_links=connected_scan.api_links,
        data_layers=connected_scan.data_layers,
        runtime_configs=connected_scan.runtime_configs,
        test_maps=connected_scan.test_maps,
        feature_maps=connected_scan.feature_maps,
        module_boundaries=connected_scan.module_boundaries,
        refactor_findings=connected_scan.refactor_findings,
        contract_gaps=connected_scan.contract_gaps,
        imports=language_scan.imports,
        symbols=language_scan.symbols,
        extraction_issues=language_scan.issues,
        config_files=connected_scan.config_files,
        test_files=connected_scan.test_files,
    )


def _scan_language_surfaces(root_path: Path, file_facts: list[FileFact]) -> LanguageScan:
    python_imports, python_symbols, python_commands, python_issues = extract_python_facts(
        root_path,
        file_facts,
    )
    ts_imports, ts_symbols, ts_commands, ts_issues = extract_typescript_facts(
        root_path,
        file_facts,
    )
    imports = [*python_imports, *ts_imports]
    symbols = [*python_symbols, *ts_symbols]
    commands = [*python_commands, *ts_commands]
    extraction_issues = [*python_issues, *ts_issues]
    return LanguageScan(
        imports=imports,
        symbols=symbols,
        commands=commands,
        issues=extraction_issues,
    )


def _scan_backend_surfaces(
    root_path: Path,
    file_facts: list[FileFact],
    symbols: list[SymbolFact],
    frameworks: list[FrameworkFact],
) -> BackendScan:
    api_routes, backend_surfaces = extract_backend_facts(root_path, file_facts, symbols, frameworks)
    (
        java_web_surfaces,
        servlets,
        jsp_pages,
        data_models,
        repositories,
        services,
    ) = extract_java_web_facts(root_path, file_facts)
    contract_details = extract_contract_details(root_path, file_facts, api_routes)
    api_contracts = build_api_contracts(api_routes, contract_details)
    return BackendScan(
        api_routes=api_routes,
        backend_surfaces=backend_surfaces,
        java_web_surfaces=java_web_surfaces,
        servlets=servlets,
        jsp_pages=jsp_pages,
        data_models=data_models,
        repositories=repositories,
        services=services,
        contract_details=contract_details,
        api_contracts=api_contracts,
    )


def _scan_frontend_surfaces(
    root_path: Path,
    file_facts: list[FileFact],
    symbols: list[SymbolFact],
    frameworks: list[FrameworkFact],
) -> FrontendScan:
    frontend_routes, components, api_calls, state_usages, _frontend_surfaces = extract_frontend_facts(
        root_path,
        file_facts,
        symbols,
        frameworks,
    )
    (
        pages,
        forms,
        assets,
        styles,
        static_routes,
        static_api_calls,
    ) = extract_static_frontend_facts(root_path, file_facts)
    frontend_routes = _dedupe_frontend_routes([*frontend_routes, *static_routes])
    api_calls = _dedupe_api_calls([*api_calls, *static_api_calls])
    return FrontendScan(
        frontend_routes=frontend_routes,
        components=components,
        api_calls=api_calls,
        state_usages=state_usages,
        pages=pages,
        forms=forms,
        assets=assets,
        styles=styles,
    )


def _build_connected_surfaces(
    root_path: Path,
    file_facts: list[FileFact],
    entrypoints: list[EntrypointFact],
    frameworks: list[FrameworkFact],
    language_scan: LanguageScan,
    backend_scan: BackendScan,
    frontend_scan: FrontendScan,
) -> ConnectedScan:
    api_links, api_calls = build_api_links(frontend_scan.api_calls, backend_scan.api_routes)
    data_layers = extract_data_layer_facts(
        root_path,
        file_facts,
        backend_scan.data_models,
        backend_scan.repositories,
        backend_scan.services,
    )
    runtime_configs = extract_runtime_config_facts(root_path, file_facts)
    config_files = [fact for fact in file_facts if fact.role == "config"]
    test_files = [fact for fact in file_facts if fact.role == "test"]
    test_maps = build_test_maps(
        root_path,
        test_files,
        backend_scan.api_routes,
        frontend_scan.components,
        language_scan.commands,
        backend_scan.services,
        backend_scan.repositories,
        backend_scan.data_models,
    )
    backend_surfaces = _augment_backend_surfaces(
        backend_scan.backend_surfaces,
        data_layers=len(data_layers),
        runtime_configs=len(runtime_configs),
        test_maps=len(test_maps),
    )
    frontend_maps = build_frontend_maps(
        frontend_scan.pages,
        frontend_scan.components,
        api_calls,
        frontend_scan.state_usages,
        frontend_scan.styles,
        frontend_scan.assets,
    )
    frontend_surfaces = build_frontend_surfaces(
        frontend_scan.frontend_routes,
        frontend_scan.components,
        api_calls,
        frameworks,
        pages=frontend_scan.pages,
        forms=frontend_scan.forms,
        styles=frontend_scan.styles,
        assets=frontend_scan.assets,
        state_usages=frontend_scan.state_usages,
    )
    feature_maps, module_boundaries, refactor_findings, contract_gaps = build_relationship_facts(
        root_path,
        file_facts,
        entrypoints,
        language_scan.commands,
        frontend_scan.frontend_routes,
        frontend_scan.pages,
        frontend_scan.components,
        frontend_scan.forms,
        api_calls,
        backend_scan.api_routes,
        backend_scan.api_contracts,
        api_links,
        backend_scan.data_models,
        backend_scan.repositories,
        backend_scan.services,
        data_layers,
        runtime_configs,
        test_maps,
        frontend_scan.styles,
        frontend_scan.assets,
        frontend_scan.state_usages,
        test_files,
    )
    return ConnectedScan(
        api_links=api_links,
        api_calls=api_calls,
        data_layers=data_layers,
        runtime_configs=runtime_configs,
        config_files=config_files,
        test_files=test_files,
        test_maps=test_maps,
        backend_surfaces=backend_surfaces,
        frontend_maps=frontend_maps,
        frontend_surfaces=frontend_surfaces,
        feature_maps=feature_maps,
        module_boundaries=module_boundaries,
        refactor_findings=refactor_findings,
        contract_gaps=contract_gaps,
    )








def _dedupe_frontend_routes(routes: list[FrontendRouteFact]) -> list[FrontendRouteFact]:
    seen: set[tuple[str, str, str]] = set()
    result: list[FrontendRouteFact] = []
    for route in routes:
        key = (route.route, route.path, route.kind)
        if key in seen:
            continue
        seen.add(key)
        result.append(route)
    return result


def _dedupe_api_calls(calls: list[ApiCallFact]) -> list[ApiCallFact]:
    seen: set[tuple[str, str, str | None, str]] = set()
    result: list[ApiCallFact] = []
    for call in calls:
        key = (call.path, call.endpoint, call.method, call.client)
        if key in seen:
            continue
        seen.add(key)
        result.append(call)
    return result


def _augment_backend_surfaces(
    surfaces: list[BackendSurfaceFact],
    data_layers: int,
    runtime_configs: int,
    test_maps: int,
) -> list[BackendSurfaceFact]:
    return [
        BackendSurfaceFact(
            framework=surface.framework,
            route_count=surface.route_count,
            handler_count=surface.handler_count,
            service_count=surface.service_count,
            model_count=surface.model_count,
            data_layer_count=data_layers,
            runtime_config_count=runtime_configs,
            test_map_count=test_maps,
            evidence=surface.evidence,
        )
        for surface in surfaces
    ]
