from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


FACT_SCHEMA_VERSION = "2.0"


@dataclass(frozen=True)
class Evidence:
    file: str
    kind: str
    line_start: int | None = None
    line_end: int | None = None
    note: str | None = None


@dataclass(frozen=True)
class FileFact:
    path: str
    language: str
    role: str
    size_bytes: int
    evidence: Evidence


@dataclass(frozen=True)
class DependencyFact:
    name: str
    source: str
    scope: str
    evidence: Evidence


@dataclass(frozen=True)
class EntrypointFact:
    path: str
    kind: str
    command: str | None
    evidence: Evidence


@dataclass(frozen=True)
class CommandFact:
    path: str
    name: str
    description: str | None
    arguments: list[str]
    options: list[str]
    evidence: Evidence


@dataclass(frozen=True)
class FrameworkFact:
    name: str
    category: str
    source: str
    confidence: float
    evidence: Evidence


@dataclass(frozen=True)
class RequestParamFact:
    name: str
    source: str
    type: str | None
    required: bool | None
    evidence: Evidence


@dataclass(frozen=True)
class ApiRouteFact:
    method: str
    path: str
    handler: str | None
    framework: str
    kind: str
    evidence: Evidence
    class_prefix: str | None = None
    parameters: list[RequestParamFact] = field(default_factory=list)
    request_body: str | None = None
    response_type: str | None = None


@dataclass(frozen=True)
class BackendSurfaceFact:
    framework: str
    route_count: int
    handler_count: int
    service_count: int
    model_count: int
    data_layer_count: int = 0
    runtime_config_count: int = 0
    test_map_count: int = 0
    evidence: list[Evidence] = field(default_factory=list)


@dataclass(frozen=True)
class FrontendRouteFact:
    route: str
    path: str
    framework: str
    kind: str
    evidence: Evidence


@dataclass(frozen=True)
class ComponentFact:
    name: str
    path: str
    framework: str
    props: list[str]
    hooks: list[str]
    evidence: Evidence


@dataclass(frozen=True)
class ApiCallFact:
    path: str
    endpoint: str
    method: str | None
    client: str
    evidence: Evidence
    trigger: str | None = None
    context: str | None = None
    matched_route: str | None = None


@dataclass(frozen=True)
class FrontendSurfaceFact:
    framework: str
    route_count: int
    component_count: int
    api_call_count: int
    page_count: int = 0
    form_count: int = 0
    style_count: int = 0
    asset_count: int = 0
    state_count: int = 0
    evidence: list[Evidence] = field(default_factory=list)


@dataclass(frozen=True)
class PageFact:
    path: str
    route: str
    title: str | None
    kind: str
    template_engine: str | None
    evidence: Evidence


@dataclass(frozen=True)
class FormFact:
    source: str
    method: str | None
    action: str | None
    fields: list[str]
    evidence: Evidence


@dataclass(frozen=True)
class AssetFact:
    source: str
    asset_path: str
    asset_kind: str
    usage_kind: str
    evidence: Evidence


@dataclass(frozen=True)
class StyleFact:
    path: str
    selectors: list[str]
    classes: list[str]
    ids: list[str]
    css_variables: list[str]
    imports: list[str]
    asset_urls: list[str]
    evidence: Evidence


@dataclass(frozen=True)
class StateUsageFact:
    source: str
    library: str
    usage: str
    name: str
    evidence: Evidence


@dataclass(frozen=True)
class FrontendMapFact:
    route: str
    page: str | None
    components: list[str]
    api_calls: list[str]
    state: list[str]
    styles: list[str]
    assets: list[str]
    evidence: list[Evidence] = field(default_factory=list)


@dataclass(frozen=True)
class JavaWebSurfaceFact:
    spring_controller_count: int
    servlet_count: int
    jsp_page_count: int
    data_model_count: int
    repository_count: int
    service_count: int
    evidence: list[Evidence] = field(default_factory=list)


@dataclass(frozen=True)
class ServletFact:
    name: str
    class_name: str | None
    url_patterns: list[str]
    source: str
    evidence: Evidence


@dataclass(frozen=True)
class JspPageFact:
    path: str
    route: str
    form_actions: list[str]
    links: list[str]
    includes: list[str]
    uses_jstl: bool
    uses_el: bool
    evidence: Evidence


@dataclass(frozen=True)
class DataModelFact:
    name: str
    path: str
    kind: str
    fields: list[str]
    annotations: list[str]
    evidence: Evidence


@dataclass(frozen=True)
class RepositoryFact:
    name: str
    path: str
    entity: str | None
    base_interface: str | None
    evidence: Evidence


@dataclass(frozen=True)
class ServiceFact:
    name: str
    path: str
    methods: list[str]
    evidence: Evidence


@dataclass(frozen=True)
class ApiContractFact:
    method: str
    path: str
    handler: str | None
    framework: str
    parameters: list[RequestParamFact]
    request_body: str | None
    response_type: str | None
    evidence: Evidence
    request_hints: list[str] = field(default_factory=list)
    response_hints: list[str] = field(default_factory=list)
    status_codes: list[str] = field(default_factory=list)
    error_hints: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ContractDetailFact:
    method: str
    path: str
    framework: str
    request_hints: list[str]
    response_hints: list[str]
    status_codes: list[str]
    error_hints: list[str]
    evidence: Evidence


@dataclass(frozen=True)
class ApiLinkFact:
    source: str
    endpoint: str
    method: str | None
    matched_route: str | None
    matched_method: str | None
    matched_framework: str | None
    match_type: str
    confidence: str
    evidence: list[Evidence] = field(default_factory=list)


@dataclass(frozen=True)
class DataLayerFact:
    path: str
    kind: str
    name: str
    details: list[str]
    evidence: Evidence


@dataclass(frozen=True)
class RuntimeConfigFact:
    path: str
    kind: str
    name: str
    values: list[str]
    evidence: Evidence


@dataclass(frozen=True)
class TestMapFact:
    test_path: str
    target_kind: str
    target: str | None
    confidence: str
    evidence: Evidence


@dataclass(frozen=True)
class FeatureMapFact:
    name: str
    summary: str
    frontend_sources: list[str]
    frontend_routes: list[str]
    pages: list[str]
    components: list[str]
    forms: list[str]
    api_calls: list[str]
    backend_routes: list[str]
    contracts: list[str]
    services: list[str]
    repositories: list[str]
    data_models: list[str]
    tests: list[str]
    confidence: str
    commands: list[str] = field(default_factory=list)
    implementation_sources: list[str] = field(default_factory=list)
    implementation_reasons: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)


@dataclass(frozen=True)
class ModuleBoundaryFact:
    name: str
    kind: str
    paths: list[str]
    responsibilities: list[str]
    depends_on: list[str]
    evidence: list[Evidence] = field(default_factory=list)


@dataclass(frozen=True)
class RefactorFindingFact:
    title: str
    severity: str
    subject: str
    detail: str
    recommendation: str
    evidence: list[Evidence] = field(default_factory=list)


@dataclass(frozen=True)
class ContractGapFact:
    contract: str
    gap_type: str
    detail: str
    evidence: list[Evidence] = field(default_factory=list)


@dataclass(frozen=True)
class ImportFact:
    path: str
    module: str | None
    names: list[str]
    kind: str
    level: int
    evidence: Evidence


@dataclass(frozen=True)
class SymbolFact:
    path: str
    name: str
    qualname: str
    kind: str
    parent: str | None
    line_start: int
    line_end: int | None
    signature: str
    decorators: list[str]
    docstring: str | None
    evidence: Evidence


@dataclass(frozen=True)
class ExtractionIssue:
    path: str
    extractor: str
    message: str
    evidence: Evidence


@dataclass(frozen=True)
class ProjectFacts:
    root: str
    name: str
    schema_version: str = FACT_SCHEMA_VERSION
    files: list[FileFact] = field(default_factory=list)
    dependencies: list[DependencyFact] = field(default_factory=list)
    entrypoints: list[EntrypointFact] = field(default_factory=list)
    commands: list[CommandFact] = field(default_factory=list)
    frameworks: list[FrameworkFact] = field(default_factory=list)
    api_routes: list[ApiRouteFact] = field(default_factory=list)
    backend_surfaces: list[BackendSurfaceFact] = field(default_factory=list)
    frontend_routes: list[FrontendRouteFact] = field(default_factory=list)
    components: list[ComponentFact] = field(default_factory=list)
    api_calls: list[ApiCallFact] = field(default_factory=list)
    frontend_surfaces: list[FrontendSurfaceFact] = field(default_factory=list)
    pages: list[PageFact] = field(default_factory=list)
    forms: list[FormFact] = field(default_factory=list)
    assets: list[AssetFact] = field(default_factory=list)
    styles: list[StyleFact] = field(default_factory=list)
    state_usages: list[StateUsageFact] = field(default_factory=list)
    frontend_maps: list[FrontendMapFact] = field(default_factory=list)
    java_web_surfaces: list[JavaWebSurfaceFact] = field(default_factory=list)
    servlets: list[ServletFact] = field(default_factory=list)
    jsp_pages: list[JspPageFact] = field(default_factory=list)
    data_models: list[DataModelFact] = field(default_factory=list)
    repositories: list[RepositoryFact] = field(default_factory=list)
    services: list[ServiceFact] = field(default_factory=list)
    api_contracts: list[ApiContractFact] = field(default_factory=list)
    contract_details: list[ContractDetailFact] = field(default_factory=list)
    api_links: list[ApiLinkFact] = field(default_factory=list)
    data_layers: list[DataLayerFact] = field(default_factory=list)
    runtime_configs: list[RuntimeConfigFact] = field(default_factory=list)
    test_maps: list[TestMapFact] = field(default_factory=list)
    feature_maps: list[FeatureMapFact] = field(default_factory=list)
    module_boundaries: list[ModuleBoundaryFact] = field(default_factory=list)
    refactor_findings: list[RefactorFindingFact] = field(default_factory=list)
    contract_gaps: list[ContractGapFact] = field(default_factory=list)
    imports: list[ImportFact] = field(default_factory=list)
    symbols: list[SymbolFact] = field(default_factory=list)
    extraction_issues: list[ExtractionIssue] = field(default_factory=list)
    config_files: list[FileFact] = field(default_factory=list)
    test_files: list[FileFact] = field(default_factory=list)

    @property
    def languages(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for file_fact in self.files:
            counts[file_fact.language] = counts.get(file_fact.language, 0) + 1
        return dict(sorted(counts.items()))


@dataclass(frozen=True)
class TraceClaim:
    claim_id: str
    claim: str
    claim_type: str
    confidence: float
    evidence: list[Evidence]
    status: str = "observed"


@dataclass(frozen=True)
class Gap:
    gap_id: str
    title: str
    detail: str
    severity: str
    evidence: list[Evidence] = field(default_factory=list)


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    return value


def evidence_from_dict(value: dict[str, Any]) -> Evidence:
    return Evidence(
        file=value["file"],
        kind=value["kind"],
        line_start=value.get("line_start"),
        line_end=value.get("line_end"),
        note=value.get("note"),
    )


def file_fact_from_dict(value: dict[str, Any]) -> FileFact:
    return FileFact(
        path=value["path"],
        language=value["language"],
        role=value["role"],
        size_bytes=value["size_bytes"],
        evidence=evidence_from_dict(value["evidence"]),
    )


def dependency_fact_from_dict(value: dict[str, Any]) -> DependencyFact:
    return DependencyFact(
        name=value["name"],
        source=value["source"],
        scope=value["scope"],
        evidence=evidence_from_dict(value["evidence"]),
    )


def entrypoint_fact_from_dict(value: dict[str, Any]) -> EntrypointFact:
    return EntrypointFact(
        path=value["path"],
        kind=value["kind"],
        command=value.get("command"),
        evidence=evidence_from_dict(value["evidence"]),
    )


def command_fact_from_dict(value: dict[str, Any]) -> CommandFact:
    return CommandFact(
        path=value["path"],
        name=value["name"],
        description=value.get("description"),
        arguments=list(value.get("arguments", [])),
        options=list(value.get("options", [])),
        evidence=evidence_from_dict(value["evidence"]),
    )


def framework_fact_from_dict(value: dict[str, Any]) -> FrameworkFact:
    return FrameworkFact(
        name=value["name"],
        category=value["category"],
        source=value["source"],
        confidence=float(value["confidence"]),
        evidence=evidence_from_dict(value["evidence"]),
    )


def request_param_fact_from_dict(value: dict[str, Any]) -> RequestParamFact:
    return RequestParamFact(
        name=value["name"],
        source=value["source"],
        type=value.get("type"),
        required=value.get("required"),
        evidence=evidence_from_dict(value["evidence"]),
    )


def api_route_fact_from_dict(value: dict[str, Any]) -> ApiRouteFact:
    return ApiRouteFact(
        method=value["method"],
        path=value["path"],
        handler=value.get("handler"),
        framework=value["framework"],
        kind=value["kind"],
        evidence=evidence_from_dict(value["evidence"]),
        class_prefix=value.get("class_prefix"),
        parameters=[
            request_param_fact_from_dict(item)
            for item in value.get("parameters", [])
        ],
        request_body=value.get("request_body"),
        response_type=value.get("response_type"),
    )


def backend_surface_fact_from_dict(value: dict[str, Any]) -> BackendSurfaceFact:
    return BackendSurfaceFact(
        framework=value["framework"],
        route_count=int(value["route_count"]),
        handler_count=int(value["handler_count"]),
        service_count=int(value["service_count"]),
        model_count=int(value["model_count"]),
        data_layer_count=int(value.get("data_layer_count", 0)),
        runtime_config_count=int(value.get("runtime_config_count", 0)),
        test_map_count=int(value.get("test_map_count", 0)),
        evidence=[evidence_from_dict(item) for item in value.get("evidence", [])],
    )


def frontend_route_fact_from_dict(value: dict[str, Any]) -> FrontendRouteFact:
    return FrontendRouteFact(
        route=value["route"],
        path=value["path"],
        framework=value["framework"],
        kind=value["kind"],
        evidence=evidence_from_dict(value["evidence"]),
    )


def component_fact_from_dict(value: dict[str, Any]) -> ComponentFact:
    return ComponentFact(
        name=value["name"],
        path=value["path"],
        framework=value["framework"],
        props=list(value.get("props", [])),
        hooks=list(value.get("hooks", [])),
        evidence=evidence_from_dict(value["evidence"]),
    )


def api_call_fact_from_dict(value: dict[str, Any]) -> ApiCallFact:
    return ApiCallFact(
        path=value["path"],
        endpoint=value["endpoint"],
        method=value.get("method"),
        client=value["client"],
        evidence=evidence_from_dict(value["evidence"]),
        trigger=value.get("trigger"),
        context=value.get("context"),
        matched_route=value.get("matched_route"),
    )


def frontend_surface_fact_from_dict(value: dict[str, Any]) -> FrontendSurfaceFact:
    return FrontendSurfaceFact(
        framework=value["framework"],
        route_count=int(value["route_count"]),
        component_count=int(value["component_count"]),
        api_call_count=int(value["api_call_count"]),
        page_count=int(value.get("page_count", 0)),
        form_count=int(value.get("form_count", 0)),
        style_count=int(value.get("style_count", 0)),
        asset_count=int(value.get("asset_count", 0)),
        state_count=int(value.get("state_count", 0)),
        evidence=[evidence_from_dict(item) for item in value.get("evidence", [])],
    )


def page_fact_from_dict(value: dict[str, Any]) -> PageFact:
    return PageFact(
        path=value["path"],
        route=value["route"],
        title=value.get("title"),
        kind=value["kind"],
        template_engine=value.get("template_engine"),
        evidence=evidence_from_dict(value["evidence"]),
    )


def form_fact_from_dict(value: dict[str, Any]) -> FormFact:
    return FormFact(
        source=value["source"],
        method=value.get("method"),
        action=value.get("action"),
        fields=list(value.get("fields", [])),
        evidence=evidence_from_dict(value["evidence"]),
    )


def asset_fact_from_dict(value: dict[str, Any]) -> AssetFact:
    return AssetFact(
        source=value["source"],
        asset_path=value["asset_path"],
        asset_kind=value["asset_kind"],
        usage_kind=value["usage_kind"],
        evidence=evidence_from_dict(value["evidence"]),
    )


def style_fact_from_dict(value: dict[str, Any]) -> StyleFact:
    return StyleFact(
        path=value["path"],
        selectors=list(value.get("selectors", [])),
        classes=list(value.get("classes", [])),
        ids=list(value.get("ids", [])),
        css_variables=list(value.get("css_variables", [])),
        imports=list(value.get("imports", [])),
        asset_urls=list(value.get("asset_urls", [])),
        evidence=evidence_from_dict(value["evidence"]),
    )


def state_usage_fact_from_dict(value: dict[str, Any]) -> StateUsageFact:
    return StateUsageFact(
        source=value["source"],
        library=value["library"],
        usage=value["usage"],
        name=value["name"],
        evidence=evidence_from_dict(value["evidence"]),
    )


def frontend_map_fact_from_dict(value: dict[str, Any]) -> FrontendMapFact:
    return FrontendMapFact(
        route=value["route"],
        page=value.get("page"),
        components=list(value.get("components", [])),
        api_calls=list(value.get("api_calls", [])),
        state=list(value.get("state", [])),
        styles=list(value.get("styles", [])),
        assets=list(value.get("assets", [])),
        evidence=[evidence_from_dict(item) for item in value.get("evidence", [])],
    )


def java_web_surface_fact_from_dict(value: dict[str, Any]) -> JavaWebSurfaceFact:
    return JavaWebSurfaceFact(
        spring_controller_count=int(value["spring_controller_count"]),
        servlet_count=int(value["servlet_count"]),
        jsp_page_count=int(value["jsp_page_count"]),
        data_model_count=int(value["data_model_count"]),
        repository_count=int(value["repository_count"]),
        service_count=int(value["service_count"]),
        evidence=[evidence_from_dict(item) for item in value.get("evidence", [])],
    )


def servlet_fact_from_dict(value: dict[str, Any]) -> ServletFact:
    return ServletFact(
        name=value["name"],
        class_name=value.get("class_name"),
        url_patterns=list(value.get("url_patterns", [])),
        source=value["source"],
        evidence=evidence_from_dict(value["evidence"]),
    )


def jsp_page_fact_from_dict(value: dict[str, Any]) -> JspPageFact:
    return JspPageFact(
        path=value["path"],
        route=value["route"],
        form_actions=list(value.get("form_actions", [])),
        links=list(value.get("links", [])),
        includes=list(value.get("includes", [])),
        uses_jstl=bool(value.get("uses_jstl", False)),
        uses_el=bool(value.get("uses_el", False)),
        evidence=evidence_from_dict(value["evidence"]),
    )


def data_model_fact_from_dict(value: dict[str, Any]) -> DataModelFact:
    return DataModelFact(
        name=value["name"],
        path=value["path"],
        kind=value["kind"],
        fields=list(value.get("fields", [])),
        annotations=list(value.get("annotations", [])),
        evidence=evidence_from_dict(value["evidence"]),
    )


def repository_fact_from_dict(value: dict[str, Any]) -> RepositoryFact:
    return RepositoryFact(
        name=value["name"],
        path=value["path"],
        entity=value.get("entity"),
        base_interface=value.get("base_interface"),
        evidence=evidence_from_dict(value["evidence"]),
    )


def service_fact_from_dict(value: dict[str, Any]) -> ServiceFact:
    return ServiceFact(
        name=value["name"],
        path=value["path"],
        methods=list(value.get("methods", [])),
        evidence=evidence_from_dict(value["evidence"]),
    )


def api_contract_fact_from_dict(value: dict[str, Any]) -> ApiContractFact:
    return ApiContractFact(
        method=value["method"],
        path=value["path"],
        handler=value.get("handler"),
        framework=value["framework"],
        parameters=[
            request_param_fact_from_dict(item)
            for item in value.get("parameters", [])
        ],
        request_body=value.get("request_body"),
        response_type=value.get("response_type"),
        evidence=evidence_from_dict(value["evidence"]),
        request_hints=list(value.get("request_hints", [])),
        response_hints=list(value.get("response_hints", [])),
        status_codes=list(value.get("status_codes", [])),
        error_hints=list(value.get("error_hints", [])),
    )


def contract_detail_fact_from_dict(value: dict[str, Any]) -> ContractDetailFact:
    return ContractDetailFact(
        method=value["method"],
        path=value["path"],
        framework=value["framework"],
        request_hints=list(value.get("request_hints", [])),
        response_hints=list(value.get("response_hints", [])),
        status_codes=list(value.get("status_codes", [])),
        error_hints=list(value.get("error_hints", [])),
        evidence=evidence_from_dict(value["evidence"]),
    )


def api_link_fact_from_dict(value: dict[str, Any]) -> ApiLinkFact:
    return ApiLinkFact(
        source=value["source"],
        endpoint=value["endpoint"],
        method=value.get("method"),
        matched_route=value.get("matched_route"),
        matched_method=value.get("matched_method"),
        matched_framework=value.get("matched_framework"),
        match_type=value["match_type"],
        confidence=value["confidence"],
        evidence=[evidence_from_dict(item) for item in value.get("evidence", [])],
    )


def data_layer_fact_from_dict(value: dict[str, Any]) -> DataLayerFact:
    return DataLayerFact(
        path=value["path"],
        kind=value["kind"],
        name=value["name"],
        details=list(value.get("details", [])),
        evidence=evidence_from_dict(value["evidence"]),
    )


def runtime_config_fact_from_dict(value: dict[str, Any]) -> RuntimeConfigFact:
    return RuntimeConfigFact(
        path=value["path"],
        kind=value["kind"],
        name=value["name"],
        values=list(value.get("values", [])),
        evidence=evidence_from_dict(value["evidence"]),
    )


def test_map_fact_from_dict(value: dict[str, Any]) -> TestMapFact:
    return TestMapFact(
        test_path=value["test_path"],
        target_kind=value["target_kind"],
        target=value.get("target"),
        confidence=value["confidence"],
        evidence=evidence_from_dict(value["evidence"]),
    )


def feature_map_fact_from_dict(value: dict[str, Any]) -> FeatureMapFact:
    return FeatureMapFact(
        name=value["name"],
        summary=value["summary"],
        frontend_sources=list(value.get("frontend_sources", [])),
        frontend_routes=list(value.get("frontend_routes", [])),
        pages=list(value.get("pages", [])),
        components=list(value.get("components", [])),
        forms=list(value.get("forms", [])),
        api_calls=list(value.get("api_calls", [])),
        backend_routes=list(value.get("backend_routes", [])),
        contracts=list(value.get("contracts", [])),
        services=list(value.get("services", [])),
        repositories=list(value.get("repositories", [])),
        data_models=list(value.get("data_models", [])),
        tests=list(value.get("tests", [])),
        confidence=value.get("confidence", "low"),
        commands=list(value.get("commands", [])),
        implementation_sources=list(value.get("implementation_sources", [])),
        implementation_reasons=list(value.get("implementation_reasons", [])),
        evidence=[evidence_from_dict(item) for item in value.get("evidence", [])],
    )


def module_boundary_fact_from_dict(value: dict[str, Any]) -> ModuleBoundaryFact:
    return ModuleBoundaryFact(
        name=value["name"],
        kind=value["kind"],
        paths=list(value.get("paths", [])),
        responsibilities=list(value.get("responsibilities", [])),
        depends_on=list(value.get("depends_on", [])),
        evidence=[evidence_from_dict(item) for item in value.get("evidence", [])],
    )


def refactor_finding_fact_from_dict(value: dict[str, Any]) -> RefactorFindingFact:
    return RefactorFindingFact(
        title=value["title"],
        severity=value["severity"],
        subject=value["subject"],
        detail=value["detail"],
        recommendation=value["recommendation"],
        evidence=[evidence_from_dict(item) for item in value.get("evidence", [])],
    )


def contract_gap_fact_from_dict(value: dict[str, Any]) -> ContractGapFact:
    return ContractGapFact(
        contract=value["contract"],
        gap_type=value["gap_type"],
        detail=value["detail"],
        evidence=[evidence_from_dict(item) for item in value.get("evidence", [])],
    )


def import_fact_from_dict(value: dict[str, Any]) -> ImportFact:
    return ImportFact(
        path=value["path"],
        module=value.get("module"),
        names=list(value.get("names", [])),
        kind=value["kind"],
        level=int(value.get("level", 0)),
        evidence=evidence_from_dict(value["evidence"]),
    )


def symbol_fact_from_dict(value: dict[str, Any]) -> SymbolFact:
    return SymbolFact(
        path=value["path"],
        name=value["name"],
        qualname=value["qualname"],
        kind=value["kind"],
        parent=value.get("parent"),
        line_start=int(value["line_start"]),
        line_end=value.get("line_end"),
        signature=value["signature"],
        decorators=list(value.get("decorators", [])),
        docstring=value.get("docstring"),
        evidence=evidence_from_dict(value["evidence"]),
    )


def extraction_issue_from_dict(value: dict[str, Any]) -> ExtractionIssue:
    return ExtractionIssue(
        path=value["path"],
        extractor=value["extractor"],
        message=value["message"],
        evidence=evidence_from_dict(value["evidence"]),
    )


def project_facts_from_dict(value: dict[str, Any]) -> ProjectFacts:
    return ProjectFacts(
        root=value["root"],
        name=value["name"],
        schema_version=value.get("schema_version", FACT_SCHEMA_VERSION),
        files=[file_fact_from_dict(item) for item in value.get("files", [])],
        dependencies=[
            dependency_fact_from_dict(item)
            for item in value.get("dependencies", [])
        ],
        entrypoints=[
            entrypoint_fact_from_dict(item)
            for item in value.get("entrypoints", [])
        ],
        commands=[
            command_fact_from_dict(item)
            for item in value.get("commands", [])
        ],
        frameworks=[
            framework_fact_from_dict(item)
            for item in value.get("frameworks", [])
        ],
        api_routes=[
            api_route_fact_from_dict(item)
            for item in value.get("api_routes", [])
        ],
        backend_surfaces=[
            backend_surface_fact_from_dict(item)
            for item in value.get("backend_surfaces", [])
        ],
        frontend_routes=[
            frontend_route_fact_from_dict(item)
            for item in value.get("frontend_routes", [])
        ],
        components=[
            component_fact_from_dict(item)
            for item in value.get("components", [])
        ],
        api_calls=[
            api_call_fact_from_dict(item)
            for item in value.get("api_calls", [])
        ],
        frontend_surfaces=[
            frontend_surface_fact_from_dict(item)
            for item in value.get("frontend_surfaces", [])
        ],
        pages=[
            page_fact_from_dict(item)
            for item in value.get("pages", [])
        ],
        forms=[
            form_fact_from_dict(item)
            for item in value.get("forms", [])
        ],
        assets=[
            asset_fact_from_dict(item)
            for item in value.get("assets", [])
        ],
        styles=[
            style_fact_from_dict(item)
            for item in value.get("styles", [])
        ],
        state_usages=[
            state_usage_fact_from_dict(item)
            for item in value.get("state_usages", [])
        ],
        frontend_maps=[
            frontend_map_fact_from_dict(item)
            for item in value.get("frontend_maps", [])
        ],
        java_web_surfaces=[
            java_web_surface_fact_from_dict(item)
            for item in value.get("java_web_surfaces", [])
        ],
        servlets=[
            servlet_fact_from_dict(item)
            for item in value.get("servlets", [])
        ],
        jsp_pages=[
            jsp_page_fact_from_dict(item)
            for item in value.get("jsp_pages", [])
        ],
        data_models=[
            data_model_fact_from_dict(item)
            for item in value.get("data_models", [])
        ],
        repositories=[
            repository_fact_from_dict(item)
            for item in value.get("repositories", [])
        ],
        services=[
            service_fact_from_dict(item)
            for item in value.get("services", [])
        ],
        api_contracts=[
            api_contract_fact_from_dict(item)
            for item in value.get("api_contracts", [])
        ],
        contract_details=[
            contract_detail_fact_from_dict(item)
            for item in value.get("contract_details", [])
        ],
        api_links=[
            api_link_fact_from_dict(item)
            for item in value.get("api_links", [])
        ],
        data_layers=[
            data_layer_fact_from_dict(item)
            for item in value.get("data_layers", [])
        ],
        runtime_configs=[
            runtime_config_fact_from_dict(item)
            for item in value.get("runtime_configs", [])
        ],
        test_maps=[
            test_map_fact_from_dict(item)
            for item in value.get("test_maps", [])
        ],
        feature_maps=[
            feature_map_fact_from_dict(item)
            for item in value.get("feature_maps", [])
        ],
        module_boundaries=[
            module_boundary_fact_from_dict(item)
            for item in value.get("module_boundaries", [])
        ],
        refactor_findings=[
            refactor_finding_fact_from_dict(item)
            for item in value.get("refactor_findings", [])
        ],
        contract_gaps=[
            contract_gap_fact_from_dict(item)
            for item in value.get("contract_gaps", [])
        ],
        imports=[
            import_fact_from_dict(item)
            for item in value.get("imports", [])
        ],
        symbols=[
            symbol_fact_from_dict(item)
            for item in value.get("symbols", [])
        ],
        extraction_issues=[
            extraction_issue_from_dict(item)
            for item in value.get("extraction_issues", [])
        ],
        config_files=[
            file_fact_from_dict(item)
            for item in value.get("config_files", [])
        ],
        test_files=[
            file_fact_from_dict(item)
            for item in value.get("test_files", [])
        ],
    )


def trace_claim_from_dict(value: dict[str, Any]) -> TraceClaim:
    return TraceClaim(
        claim_id=value["claim_id"],
        claim=value["claim"],
        claim_type=value["claim_type"],
        confidence=float(value["confidence"]),
        evidence=[evidence_from_dict(item) for item in value.get("evidence", [])],
        status=value.get("status", "observed"),
    )


def gap_from_dict(value: dict[str, Any]) -> Gap:
    return Gap(
        gap_id=value["gap_id"],
        title=value["title"],
        detail=value["detail"],
        severity=value["severity"],
        evidence=[evidence_from_dict(item) for item in value.get("evidence", [])],
    )
