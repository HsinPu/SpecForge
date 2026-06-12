from __future__ import annotations

import re
from pathlib import Path

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
    CommandFact,
    ComponentFact,
    ContractGapFact,
    DataLayerFact,
    DataModelFact,
    EntrypointFact,
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
    root_path: Path,
    files: list[FileFact],
    entrypoints: list[EntrypointFact],
    commands: list[CommandFact],
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
        root_path,
        files,
        entrypoints,
        commands,
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
        entrypoints,
        commands,
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
    root_path: Path,
    files: list[FileFact],
    entrypoints: list[EntrypointFact],
    commands: list[CommandFact],
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
                implementation_sources=[],
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
                implementation_sources=[route.evidence.file],
            )
        )

    for command in commands:
        key = f"command:{command.path}:{command.name}"
        if key in seen:
            continue
        seen.add(key)
        tokens = _tokens(command.name)
        related_tests = _related_tests(test_maps, tokens, [], [command.name])
        implementation_sources, implementation_reasons = _command_implementation_matches(
            root_path,
            command,
            files,
        )
        implementation_evidence = _evidence_for_paths(files, implementation_sources)
        features.append(
            FeatureMapFact(
                name=f"Command {_title(command.name)}",
                summary=_command_summary(command),
                frontend_sources=[],
                frontend_routes=[],
                pages=[],
                components=[],
                forms=[],
                api_calls=[],
                backend_routes=[],
                contracts=[],
                services=[],
                repositories=[],
                data_models=[],
                tests=_dedupe(related_tests),
                confidence="high",
                commands=[_command_label(command)],
                implementation_sources=implementation_sources,
                implementation_reasons=implementation_reasons,
                evidence=_dedupe_evidence([command.evidence, *implementation_evidence]),
            )
        )

    if not features:
        for entrypoint in entrypoints:
            label = entrypoint.command or entrypoint.path
            key = f"entrypoint:{entrypoint.kind}:{label}:{entrypoint.path}"
            if key in seen:
                continue
            seen.add(key)
            tokens = _tokens(label)
            tokens.update(_tokens(entrypoint.path))
            features.append(
                FeatureMapFact(
                    name=f"Entrypoint {_title(label)}",
                    summary=(
                        f"Runtime entrypoint `{label}` is declared as `{entrypoint.kind}` "
                        f"and points to `{entrypoint.path}`."
                    ),
                    frontend_sources=[],
                    frontend_routes=[],
                    pages=[],
                    components=[],
                    forms=[],
                    api_calls=[],
                    backend_routes=[],
                    contracts=[],
                    services=[],
                    repositories=[],
                    data_models=[],
                    tests=_dedupe(_related_tests(test_maps, tokens, [], [])),
                    confidence="medium",
                    commands=[label],
                    implementation_sources=[],
                    implementation_reasons=[],
                    evidence=[entrypoint.evidence],
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


def _command_label(command: CommandFact) -> str:
    parts = [command.name, *command.arguments, *command.options]
    return " ".join(part for part in parts if part)


def _command_summary(command: CommandFact) -> str:
    details: list[str] = []
    if command.arguments:
        details.append(f"arguments={', '.join(command.arguments)}")
    if command.options:
        details.append(f"options={', '.join(command.options)}")
    suffix = f" ({'; '.join(details)})" if details else ""
    description = f" {command.description}" if command.description else ""
    return f"CLI command `{command.name}` is declared in `{command.path}`.{description}{suffix}"


def _command_implementation_matches(
    root_path: Path,
    command: CommandFact,
    files: list[FileFact],
) -> tuple[list[str], list[str]]:
    matches: dict[str, str] = {command.path: "command declaration source"}
    command_tokens = _tokens(command.name)
    if not command_tokens:
        return list(matches), list(matches.values())
    candidates = [command.path]
    for file_fact in files:
        if file_fact.path == command.path or not _is_source_like(file_fact):
            continue
        if _is_command_source_path(file_fact.path, command.name, command_tokens):
            candidates.append(file_fact.path)
            matches.setdefault(
                file_fact.path,
                f"source filename matches command {command.name}",
            )
    action_matches = _command_action_import_matches(root_path, command, files)
    for source, reason in action_matches:
        candidates.append(source)
        matches[source] = reason
    sources = _dedupe(candidates)
    return sources, [matches[source] for source in sources if source in matches]


def _command_action_import_matches(
    root_path: Path,
    command: CommandFact,
    files: list[FileFact],
) -> list[tuple[str, str]]:
    source_path = root_path / command.path
    try:
        source = source_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    block = _command_block(source, command)
    if not block:
        return []
    file_paths = {file_fact.path for file_fact in files}
    matches: list[tuple[str, str]] = []
    for specifier in _dynamic_import_specifiers(block):
        resolved = _resolve_import_path(command.path, specifier, file_paths)
        if resolved:
            matches.append((resolved, f"action dynamically imports {specifier}"))
    for symbol, specifier in _static_imports(source).items():
        if symbol not in block:
            continue
        resolved = _resolve_import_path(command.path, specifier, file_paths)
        if resolved:
            matches.append((resolved, f"action uses imported symbol {symbol} from {specifier}"))
    return _dedupe_pairs(matches)


def _command_block(source: str, command: CommandFact) -> str:
    start = _offset_for_line(source, command.evidence.line_start)
    if start is None:
        pattern = re.compile(rf"\.command\(\s*['\"]{re.escape(command.name)}(?:\s|['\"])", re.MULTILINE)
        match = pattern.search(source)
        if not match:
            return ""
        start = match.start()
    end = _next_command_start(source, start + 1)
    return source[start:end]


def _offset_for_line(source: str, line: int | None) -> int | None:
    if line is None or line < 1:
        return None
    offset = 0
    for index, segment in enumerate(source.splitlines(keepends=True), start=1):
        if index == line:
            return offset
        offset += len(segment)
    return None


def _next_command_start(source: str, start: int) -> int:
    match = re.search(r"\n\s*[A-Za-z_$][\w$]*\s*\n\s*\.command\(", source[start:])
    if match:
        return start + match.start()
    return min(len(source), start + 4000)


def _dynamic_import_specifiers(block: str) -> list[str]:
    return [
        match.group("specifier")
        for match in re.finditer(r"import\(\s*['\"](?P<specifier>[^'\"]+)['\"]\s*\)", block)
    ]


def _static_imports(source: str) -> dict[str, str]:
    imports: dict[str, str] = {}
    pattern = re.compile(
        r"^\s*import\s+(?P<names>.+?)\s+from\s+['\"](?P<specifier>[^'\"]+)['\"]",
        re.MULTILINE,
    )
    for match in pattern.finditer(source):
        specifier = match.group("specifier")
        raw_names = match.group("names").strip()
        for name in _imported_symbol_names(raw_names):
            imports[name] = specifier
    return imports


def _imported_symbol_names(raw_names: str) -> list[str]:
    if raw_names.startswith("{") and raw_names.endswith("}"):
        names = raw_names[1:-1]
        return [
            part.strip().split(" as ")[-1].strip()
            for part in names.split(",")
            if part.strip()
        ]
    if raw_names.startswith("* as "):
        return [raw_names.removeprefix("* as ").strip()]
    default_name = raw_names.split(",", 1)[0].strip()
    return [default_name] if default_name else []


def _resolve_import_path(command_path: str, specifier: str, file_paths: set[str]) -> str | None:
    if not specifier.startswith("."):
        return None
    base = Path(command_path).parent
    candidate = (base / specifier).as_posix()
    candidate = _normalize_posix_path(candidate)
    suffixes = ["", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".py"]
    candidate_stems = [candidate]
    if candidate.endswith((".js", ".mjs", ".jsx", ".ts", ".tsx")):
        candidate_stems.append(str(Path(candidate).with_suffix("").as_posix()))
    for stem in candidate_stems:
        for suffix in suffixes:
            path = stem if stem.endswith(suffix) and suffix else f"{stem}{suffix}"
            if path in file_paths:
                return path
            index_path = f"{stem}/index{suffix}" if suffix else f"{stem}/index"
            if index_path in file_paths:
                return index_path
    return None


def _normalize_posix_path(path: str) -> str:
    parts: list[str] = []
    for part in path.replace("\\", "/").split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def _dedupe_pairs(values: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[str] = set()
    result: list[tuple[str, str]] = []
    for path, reason in values:
        if path in seen:
            continue
        seen.add(path)
        result.append((path, reason))
    return result


def _is_source_like(file_fact: FileFact) -> bool:
    if file_fact.role not in {"source", "entrypoint", "api", "service", "repository", "data-model", "webapp"}:
        return False
    return file_fact.language not in {"json", "markdown", "yaml", "toml", "lockfile", "image", "font", "svg"}


def _is_command_source_path(path: str, command_name: str, command_tokens: set[str]) -> bool:
    stem = path.replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()
    if stem.startswith("__") and stem.endswith("__"):
        return False
    if stem == command_name.lower():
        return True
    return _tokens(stem) == command_tokens


def _evidence_for_paths(files: list[FileFact], paths: list[str]) -> list[Evidence]:
    by_path = {file_fact.path: file_fact.evidence for file_fact in files}
    return [by_path[path] for path in paths if path in by_path]


def _title(value: str) -> str:
    tokens = sorted(_tokens(value))
    if not tokens:
        return "General"
    return " ".join(token.capitalize() for token in tokens[:3])


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
