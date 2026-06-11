from __future__ import annotations

import json
import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

from specforge.models import DependencyFact, EntrypointFact, Evidence, FileFact

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

def iter_source_files(root: Path) -> list[Path]:
    result: list[Path] = []
    for path in root.rglob("*"):
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            result.append(path)
    return sorted(result)

def file_fact(root: Path, path: Path) -> FileFact:
    relative = path.relative_to(root).as_posix()
    return FileFact(
        path=relative,
        language=detect_language(path),
        role=classify_role(relative),
        size_bytes=path.stat().st_size,
        evidence=Evidence(file=relative, kind="file", note="File discovered during scan"),
    )

def detect_language(path: Path) -> str:
    if path.name == ".gitignore":
        return "gitignore"
    if path.name == "Dockerfile" or path.name.startswith("Dockerfile."):
        return "dockerfile"
    if path.name in {"LICENSE", "CODEOWNERS"}:
        return path.name.lower()
    if path.name == ".actrc":
        return "config"
    return LANGUAGE_BY_SUFFIX.get(path.suffix.lower(), "unknown")

def classify_role(relative_path: str) -> str:
    lower = relative_path.lower()
    name = Path(lower).name
    if is_test_path(lower):
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

def is_test_path(relative_path: str) -> bool:
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

def collect_dependencies(root: Path) -> list[DependencyFact]:
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

def collect_entrypoints(root: Path, files: list[FileFact]) -> list[EntrypointFact]:
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
