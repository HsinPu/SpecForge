from __future__ import annotations

import json
import re
import tomllib
import xml.etree.ElementTree as ET
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
from specforge.extractors.runtime_config import extract_runtime_config_facts
from specforge.extractors.static_frontend import build_frontend_maps, extract_static_frontend_facts
from specforge.extractors.test_map import build_test_maps
from specforge.extractors.typescript_text import extract_typescript_facts
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
    DependencyFact,
    EntrypointFact,
    Evidence,
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
    PageFact,
    ProjectFacts,
    RepositoryFact,
    RuntimeConfigFact,
    ServiceFact,
    ServletFact,
    StateUsageFact,
    StyleFact,
    SymbolFact,
    TestMapFact,
)


IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "target",
    ".pytest_cache",
    ".ruff_cache",
    ".code2spec",
    ".specforge",
    "spec-output",
    "specforge-output",
}

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".java": "java",
    ".kt": "kotlin",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".cs": "csharp",
    ".php": "php",
    ".rb": "ruby",
    ".sh": "shell",
    ".sql": "sql",
    ".prisma": "prisma",
    ".md": "markdown",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    ".ftl": "freemarker",
    ".hbs": "handlebars",
    ".handlebars": "handlebars",
    ".mustache": "mustache",
    ".ejs": "ejs",
    ".pug": "pug",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".jsp": "jsp",
    ".toml": "toml",
    ".xml": "xml",
    ".properties": "properties",
    ".gradle": "gradle",
    ".nix": "nix",
    ".lock": "lockfile",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".webp": "image",
    ".ico": "image",
    ".svg": "svg",
    ".woff": "font",
    ".woff2": "font",
    ".ttf": "font",
    ".otf": "font",
}

CONFIG_NAMES = {
    ".env",
    ".env.example",
    ".env.sample",
    ".env.template",
    ".gitignore",
    "application.properties",
    "application.yml",
    "application.yaml",
    "build.gradle",
    "build.gradle.kts",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "Dockerfile",
    "package.json",
    "pom.xml",
    "pyproject.toml",
    "requirements.txt",
    "settings.py",
    "tailwind.config.js",
    "tailwind.config.ts",
    "vite.config.js",
    "vite.config.ts",
    "vite.config.mjs",
    "next.config.js",
    "next.config.ts",
    "next.config.mjs",
    "postcss.config.js",
    "postcss.config.ts",
    "tsconfig.json",
    "web.xml",
}


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


def scan_project(root: str | Path) -> ProjectFacts:
    root_path = Path(root).resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"Project path does not exist: {root_path}")
    if not root_path.is_dir():
        raise NotADirectoryError(f"Project path is not a directory: {root_path}")

    files = list(_iter_source_files(root_path))
    file_facts = [_file_fact(root_path, path) for path in files]
    dependencies = _collect_dependencies(root_path)
    entrypoints = _collect_entrypoints(root_path, file_facts)
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
    test_files = [fact for fact in file_facts if _is_test_path(fact.path)]
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
    )


def _iter_source_files(root: Path) -> list[Path]:
    result: list[Path] = []
    for path in root.rglob("*"):
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            result.append(path)
    return sorted(result)


def _file_fact(root: Path, path: Path) -> FileFact:
    relative = path.relative_to(root).as_posix()
    return FileFact(
        path=relative,
        language=_detect_language(path),
        role=_classify_role(relative),
        size_bytes=path.stat().st_size,
        evidence=Evidence(file=relative, kind="file", note="File discovered during scan"),
    )


def _detect_language(path: Path) -> str:
    if path.name == ".gitignore":
        return "gitignore"
    if path.name == "Dockerfile" or path.name.startswith("Dockerfile."):
        return "dockerfile"
    if path.name in {"LICENSE", "CODEOWNERS"}:
        return path.name.lower()
    if path.name == ".actrc":
        return "config"
    return LANGUAGE_BY_SUFFIX.get(path.suffix.lower(), "unknown")


def _classify_role(relative_path: str) -> str:
    lower = relative_path.lower()
    name = Path(lower).name
    if _is_test_path(lower):
        return "test"
    if name in CONFIG_NAMES or lower.startswith(".github/workflows/"):
        return "config"
    if lower.endswith(".sql") or lower.endswith("schema.prisma") or lower.endswith("mapper.xml"):
        return "data-layer"
    if lower.endswith((".css", ".scss", ".sass", ".less")) or "/styles/" in f"/{lower}":
        return "style"
    if lower.endswith((".html", ".htm", ".ftl", ".hbs", ".handlebars", ".mustache", ".ejs", ".pug")):
        return "frontend-page"
    if lower.endswith(".jsp"):
        return "frontend-page"
    if lower.startswith(("public/", "static/", "assets/")) or any(
        marker in f"/{lower}"
        for marker in (
            "/src/main/resources/static/",
            "/src/main/resources/templates/",
            "/assets/",
        )
    ):
        return "asset"
    if lower.startswith("docs/") or lower.endswith(".md"):
        return "documentation"
    if "/controller" in lower or name.endswith("controller.java"):
        return "api"
    if "/model" in lower or "/entity" in lower or name.endswith("entity.java"):
        return "data-model"
    if "/repository" in lower or name.endswith("repository.java"):
        return "repository"
    if "/service" in lower or name.endswith("service.java"):
        return "service"
    if "/src/main/webapp/" in f"/{lower}":
        return "webapp"
    if name in {"main.py", "cli.py", "index.ts", "index.js"}:
        return "entrypoint"
    return "source"


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


def _is_test_path(relative_path: str) -> bool:
    normalized = relative_path.replace("\\", "/").lower()
    name = Path(normalized).name
    return (
        normalized.startswith("test/")
        or normalized.startswith("tests/")
        or "/test/" in normalized
        or "/tests/" in normalized
        or name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith(".test.ts")
        or name.endswith(".test.js")
    )


def _collect_dependencies(root: Path) -> list[DependencyFact]:
    collectors = [
        _dependencies_from_pyproject,
        _dependencies_from_requirements,
        _dependencies_from_package_json,
        _dependencies_from_pom,
        _dependencies_from_gradle,
    ]
    dependencies: list[DependencyFact] = []
    for collector in collectors:
        dependencies.extend(collector(root))
    return sorted(dependencies, key=lambda item: (item.source, item.scope, item.name))


def _dependencies_from_pyproject(root: Path) -> list[DependencyFact]:
    path = root / "pyproject.toml"
    if not path.exists():
        return []
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = data.get("project", {})
    items = project.get("dependencies", [])
    result = [_dependency(str(item), "pyproject.toml", "runtime") for item in items]
    optional = project.get("optional-dependencies", {})
    for group_name, group_items in optional.items():
        result.extend(_dependency(str(item), "pyproject.toml", group_name) for item in group_items)
    return result


def _dependencies_from_requirements(root: Path) -> list[DependencyFact]:
    path = root / "requirements.txt"
    if not path.exists():
        return []
    result: list[DependencyFact] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        result.append(_dependency(stripped, "requirements.txt", "runtime"))
    return result


def _dependencies_from_package_json(root: Path) -> list[DependencyFact]:
    path = root / "package.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    result: list[DependencyFact] = []
    for scope_name, scope in [("dependencies", "runtime"), ("devDependencies", "development")]:
        for name in data.get(scope_name, {}):
            result.append(_dependency(name, "package.json", scope))
    return result


def _dependencies_from_pom(root: Path) -> list[DependencyFact]:
    path = root / "pom.xml"
    if not path.exists():
        return []
    result: list[DependencyFact] = []
    tree = ET.parse(path)
    root_element = tree.getroot()
    namespace_match = re.match(r"\{.*\}", root_element.tag)
    namespace = namespace_match.group(0) if namespace_match else ""
    for dependency in root_element.findall(f".//{namespace}dependency"):
        group = dependency.findtext(f"{namespace}groupId") or ""
        artifact = dependency.findtext(f"{namespace}artifactId") or ""
        scope = dependency.findtext(f"{namespace}scope") or "runtime"
        if artifact:
            result.append(_dependency(f"{group}:{artifact}" if group else artifact, "pom.xml", scope))
    return result


def _dependencies_from_gradle(root: Path) -> list[DependencyFact]:
    candidates = [root / "build.gradle", root / "build.gradle.kts"]
    result: list[DependencyFact] = []
    pattern = re.compile(r"""(?:implementation|api|runtimeOnly|testImplementation)\s*\(?\s*["']([^"']+)["']""")
    for path in candidates:
        if not path.exists():
            continue
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            result.append(_dependency(match.group(1), path.name, "gradle"))
    return result


def _dependency(name: str, source: str, scope: str) -> DependencyFact:
    return DependencyFact(
        name=name,
        source=source,
        scope=scope,
        evidence=Evidence(file=source, kind="dependency", note=f"Declared in {source}"),
    )


def _collect_entrypoints(root: Path, files: list[FileFact]) -> list[EntrypointFact]:
    result: list[EntrypointFact] = []
    package_json = root / "package.json"
    if package_json.exists():
        data = json.loads(package_json.read_text(encoding="utf-8"))
        bins = data.get("bin", {})
        if isinstance(bins, str):
            result.append(_entrypoint(bins, "node-bin", None, "package.json"))
        elif isinstance(bins, dict):
            for command, target in bins.items():
                result.append(_entrypoint(str(target), "node-bin", str(command), "package.json"))

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        scripts = data.get("project", {}).get("scripts", {})
        for command, target in scripts.items():
            result.append(_entrypoint(str(target), "python-console-script", str(command), "pyproject.toml"))

    for file_fact in files:
        name = Path(file_fact.path).name
        if name in {"main.py", "cli.py"} and file_fact.role == "entrypoint":
            result.append(_entrypoint(file_fact.path, "file-entrypoint", None, file_fact.path))
    return sorted(result, key=lambda item: (item.kind, item.path, item.command or ""))


def _entrypoint(path: str, kind: str, command: str | None, evidence_file: str) -> EntrypointFact:
    return EntrypointFact(
        path=path,
        kind=kind,
        command=command,
        evidence=Evidence(file=evidence_file, kind="entrypoint"),
    )
