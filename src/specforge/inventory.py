from __future__ import annotations

import json
import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

from specforge.models import CommandFact, DependencyFact, EntrypointFact, Evidence, FileFact

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
    ".clj-kondo",
    ".code2spec",
    ".specforge",
    ".dart_tool",
    ".yarn",
    ".gradle",
    ".next",
    ".svelte-kit",
    "spec-output",
    "specforge-output",
    "vendor",
}

SWIFT_PACKAGE_DEPENDENCY_RE = re.compile(r"\.package\s*\((?P<body>[\s\S]*?)\)", re.MULTILINE)
SWIFT_PACKAGE_URL_RE = re.compile(r"\burl\s*:\s*['\"](?P<url>[^'\"]+)['\"]")
SWIFT_PACKAGE_NAME_RE = re.compile(r"\bname\s*:\s*['\"](?P<name>[^'\"]+)['\"]")
SWIFTUI_MAIN_APP_RE = re.compile(
    r"@main\s*(?:\r?\n\s*)+(?:public\s+|internal\s+|private\s+|fileprivate\s+)?"
    r"struct\s+(?P<name>[A-Za-z_]\w*)\s*:\s*App\b",
    re.MULTILINE,
)

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".java": "java",
    ".groovy": "groovy",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sbt": "scala-build",
    ".swift": "swift",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".cjs": "javascript",
    ".mjs": "javascript",
    ".gjs": "glimmer-js",
    ".vue": "vue",
    ".go": "go",
    ".rs": "rust",
    ".cs": "csharp",
    ".cshtml": "razor",
    ".razor": "razor",
    ".xaml": "xaml",
    ".axaml": "xaml",
    ".csproj": "msbuild",
    ".php": "php",
    ".inc": "php",
    ".module": "php",
    ".install": "php",
    ".profile": "php",
    ".theme": "php",
    ".rb": "ruby",
    ".erb": "erb",
    ".rake": "ruby",
    ".gemspec": "ruby",
    ".thor": "ruby",
    ".haml": "haml",
    ".liquid": "liquid",
    ".twig": "twig",
    ".eex": "eex",
    ".heex": "heex",
    ".leex": "leex",
    ".rsb": "ruby-template",
    ".ruby": "ruby-template",
    ".builder": "ruby-template",
    ".ex": "elixir",
    ".exs": "elixir",
    ".clj": "clojure",
    ".cljs": "clojure",
    ".cljc": "clojure",
    ".edn": "edn",
    ".dart": "dart",
    ".svelte": "svelte",
    ".sh": "shell",
    ".sql": "sql",
    ".prisma": "prisma",
    ".md": "markdown",
    ".mdx": "mdx",
    ".mdc": "markdown",
    ".rst": "markdown",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    ".proto": "protobuf",
    ".graphql": "graphql",
    ".graphqls": "graphql",
    ".gql": "graphql",
    ".gitignore": "gitignore",
    ".ftl": "freemarker",
    ".hbs": "handlebars",
    ".handlebars": "handlebars",
    ".mustache": "mustache",
    ".ejs": "ejs",
    ".pug": "pug",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".ipynb": "notebook",
    ".plist": "plist",
    ".jsp": "jsp",
    ".toml": "toml",
    ".tf": "hcl",
    ".tfvars": "hcl",
    ".hcl": "hcl",
    ".tofu": "hcl",
    ".tfstate": "terraform-state",
    ".xml": "xml",
    ".properties": "properties",
    ".gradle": "gradle",
    ".nix": "nix",
    ".astro": "astro",
    ".cast": "asciinema",
    ".config": "config",
    ".coffee": "coffeescript",
    ".cue": "cue",
    ".enc": "encrypted",
    ".j2": "jinja",
    ".jbuilder": "jbuilder",
    ".json5": "json5",
    ".keep": "marker",
    ".ini": "ini",
    ".cfg": "ini",
    ".conf": "conf",
    ".repo": "repo",
    ".ru": "ruby",
    ".pm": "perl",
    ".ps1": "powershell",
    ".psd1": "powershell",
    ".psm1": "powershell",
    ".fs": "fsharp",
    ".fsx": "fsharp",
    ".fsproj": "msbuild",
    ".sln": "solution",
    ".txt": "text",
    ".atom": "xml",
    ".rss": "xml",
    ".csv": "csv",
    ".dat": "data",
    ".bin": "binary",
    ".bak": "backup",
    ".orig": "backup",
    ".save": "backup",
    ".swo": "backup",
    ".swp": "backup",
    ".crx": "browser-extension",
    ".dockerfile": "dockerfile",
    ".docx": "document",
    ".dot": "graphviz",
    ".diff": "diff",
    ".dist": "config-template",
    ".eml": "email",
    ".hide": "config-template",
    ".hg": "mercurial",
    ".ignore": "ignore",
    ".me": "markdown",
    ".mo": "translation-binary",
    ".po": "translation",
    ".pot": "translation-template",
    ".rdoc": "markdown",
    ".patch": "diff",
    ".pdf": "document",
    ".production-sample": "config-template",
    ".ps": "postscript",
    ".psd": "image",
    ".response": "http-response",
    ".sample": "config-template",
    ".service": "systemd",
    ".sgi": "image",
    ".snap": "snapshot",
    ".stub": "template-stub",
    ".target": "systemd",
    ".template": "template",
    ".textile": "markdown",
    ".tga": "image",
    ".tmpl": "template",
    ".tt": "template-toolkit",
    ".xlf": "translation",
    ".xliff": "translation",
    ".unknown": "data",
    ".long-fileextension": "data",
    ".not_image": "data",
    ".123456_abcd": "data",
    ".example": "config-template",
    ".tfn": "terraform-plan",
    ".mysql": "sql",
    ".lock": "lockfile",
    ".map": "source-map",
    ".wasm": "wasm",
    ".zip": "archive",
    ".xz": "archive",
    ".war": "archive",
    ".jar": "archive",
    ".mp4": "video",
    ".mp3": "audio",
    ".ogg": "audio",
    ".mov": "video",
    ".mkv": "video",
    ".webm": "video",
    ".flac": "audio",
    ".gz": "archive",
    ".xlsx": "spreadsheet",
    ".crt": "certificate",
    ".pem": "certificate",
    ".key": "certificate",
    ".p8": "certificate",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".webp": "image",
    ".avif": "image",
    ".tif": "image",
    ".tiff": "image",
    ".bmp": "image",
    ".heic": "image",
    ".jp2": "image",
    ".pct": "image",
    ".ico": "image",
    ".svg": "svg",
    ".woff": "font",
    ".woff2": "font",
    ".eot": "font",
    ".ttf": "font",
    ".otf": "font",
    ".sqlite": "database",
    ".db": "database",
    ".sqlite-shm": "database",
    ".sqlite-wal": "database",
    ".neon": "config",
    ".dfxp": "caption",
    ".vtt": "caption",
    ".ldif": "ldap-data",
    ".rtf": "document",
    ".tsv": "csv",
    ".xsl": "xml",
    ".xtmpl": "template",
    ".engine": "config",
    ".make": "config",
    ".grammar": "grammar",
    ".sublime-project": "config",
    ".svgz": "svg",
    ".script": "html",
    ".log": "log",
    ".odt": "document",
    ".mmdb": "data",
    ".tunnel": "config",
    ".dev": "env",
    ".demo": "env",
    ".test": "env",
}

CONFIG_NAMES = {
    ".env",
    ".env.example",
    ".env.sample",
    ".env.template",
    ".all-contributorsrc",
    ".ansible-lint",
    ".browserslistrc",
    ".buildpacks",
    ".csslintrc",
    ".dockerignore",
    ".ember-cli",
    ".editorconfig",
    ".eslintignore",
    ".foreman",
    ".gitattributes",
    ".gitignore",
    ".gitmodules",
    ".git-blame-ignore-revs",
    ".ignore",
    ".jsdoc",
    ".jshintrc",
    ".mailmap",
    ".mintgnore",
    ".netrc",
    ".node-version",
    ".npmrc",
    ".npmignore",
    ".nvmrc",
    ".opentofu-version",
    ".prettierignore",
    ".prettierrc",
    ".ruby-version",
    ".ruby-gemset",
    ".rspec",
    ".rspec_parallel",
    ".shellcheckrc",
    ".simplecov",
    ".slugignore",
    ".streerc",
    ".stylelintignore",
    ".stylelintrc",
    ".streamlit/config.toml",
    ".terraform.lock.hcl",
    ".terraform-version",
    ".tfswitchrc",
    ".tool-versions",
    ".watchmanconfig",
    ".yamllint",
    "ansible.cfg",
    "application.properties",
    "application.yml",
    "application.yaml",
    "build.gradle",
    "build.gradle.kts",
    "Cargo.toml",
    "composer.json",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "dvc.yaml",
    "dvc.lock",
    "Dockerfile",
    "MLproject",
    "Packerfile",
    "Procfile",
    "Procfile.tunnel",
    "Pulumi.yaml",
    "Pulumi.yml",
    "params.yaml",
    "params.yml",
    "package.json",
    "pom.xml",
    "pubspec.yaml",
    "pyproject.toml",
    "Gemfile",
    "gems.rb",
    "gems.locked",
    "Aptfile",
    "go.mod",
    "go.sum",
    "backend_config",
    "env",
    "METADATA",
    "priv-config",
    "version_cw",
    "version_cwctl",
    "mix.exs",
    "deps.edn",
    "project.clj",
    "Makefile",
    "Pipfile",
    "Pipfile.lock",
    "Rakefile",
    "requirements.txt",
    "redwood.toml",
    "settings.py",
    "settings.gradle",
    "settings.gradle.kts",
    "terraformrc",
    "svelte.config.js",
    "svelte.config.ts",
    "svelte.config.mjs",
    "tailwind.config.js",
    "tailwind.config.ts",
    "vite.config.js",
    "vite.config.ts",
    "vite.config.mjs",
    "next.config.js",
    "next.config.ts",
    "next.config.mjs",
    "nuxt.config.js",
    "nuxt.config.ts",
    "nuxt.config.mjs",
    "dbt_project.yml",
    "dbt_project.yaml",
    "dagster.yaml",
    "great_expectations.yml",
    "great_expectations.yaml",
    "packages.yml",
    "packages.yaml",
    "prefect.yaml",
    "profiles.yml",
    "profiles.yaml",
    "workspace.yaml",
    "workspace.yml",
    "postcss.config.js",
    "postcss.config.ts",
    "tsconfig.json",
    "Vagrantfile",
    "web.xml",
}
CONFIG_NAMES_LOWER = {item.lower() for item in CONFIG_NAMES}

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
    lower_name = path.name.lower()
    normalized = path.as_posix().lower()
    if lower_name.startswith(".env"):
        return "env"
    if path.name == ".gitignore":
        return "gitignore"
    if lower_name == ".dockerignore":
        return "dockerignore"
    if lower_name == ".gitmodules":
        return "gitmodules"
    if lower_name in {".gitkeep"}:
        return "marker"
    if lower_name.endswith("~"):
        return "backup"
    if lower_name == ".htaccess" or lower_name.endswith("htaccess"):
        return "apache-config"
    if lower_name in {
        ".all-contributorsrc",
        ".ansible-lint",
        ".browserslistrc",
        ".buildpacks",
        ".csslintrc",
        ".ember-cli",
        ".editorconfig",
        ".eslintignore",
        ".foreman",
        ".git-blame-ignore-revs",
        ".gitattributes",
        ".ignore",
        ".jsdoc",
        ".jshintrc",
        ".mailmap",
        ".mintgnore",
        ".node-version",
        ".npmignore",
        ".npmrc",
        ".nvmrc",
        ".prettierignore",
        ".prettierrc",
        ".rspec",
        ".rspec_parallel",
        ".ruby-gemset",
        ".shellcheckrc",
        ".simplecov",
        ".slugignore",
        ".streerc",
        ".stylelintignore",
        ".stylelintrc",
        ".watchmanconfig",
        ".yamllint",
        "aptfile",
        "brewfile",
        "capfile",
        "procfile.tunnel",
        "procfile",
        "priv-config",
        "version_cw",
        "version_cwctl",
    }:
        return "config"
    if lower_name in {
        ".netrc",
        ".opentofu-version",
        ".ruby-version",
        ".terraform-version",
        ".tfswitchrc",
        ".tool-versions",
        "backend_config",
        "env",
        "metadata",
        "netrc",
        "terraformrc",
    }:
        return "config"
    if path.name == "Dockerfile" or path.name.startswith("Dockerfile."):
        return "dockerfile"
    if path.name.startswith("Dockerfile-"):
        return "dockerfile"
    if path.name in {"LICENSE", "CODEOWNERS"}:
        return path.name.lower()
    if lower_name in {"makefile", "gnumakefile"}:
        return "makefile"
    if lower_name == "vagrantfile":
        return "vagrant"
    if lower_name == "go.mod":
        return "gomod"
    if lower_name == "go.sum":
        return "gosum"
    if lower_name in {"gemfile", "gems.rb"}:
        return "ruby-manifest"
    if lower_name == "build.sbt" or lower_name.endswith(".sbt"):
        return "scala-build"
    if lower_name == "routes" and "/conf/" in f"/{normalized}":
        return "play-routes"
    if lower_name.endswith(".scala.html"):
        return "twirl"
    if lower_name == "artisan":
        return "php"
    if lower_name == "gems.locked":
        return "lockfile"
    if lower_name == "rakefile":
        return "ruby"
    if lower_name == "requirements.txt":
        return "requirements"
    if not path.suffix:
        shebang_language = _language_from_shebang(path)
        if shebang_language:
            return shebang_language
        if (
            "/.well-known/" in f"/{normalized}"
            or "/.claude/skills/" in f"/{normalized}"
            or "/deployment/" in f"/{normalized}"
        ):
            return "config"
    if (
        lower_name in {"bootstrap", "chrome_wrapper", "console", "importmap", "iptables-save", "phpunit", "skills", "start"}
        or lower_name in {"about", "bundle", "dev", "rails", "rake", "setup", "spring", "update"}
        or lower_name.startswith(("install_", "start_", "sync_"))
        or "/bin/" in f"/{normalized}"
        or "/.husky/" in f"/{normalized}"
        or "/script/" in f"/{normalized}"
        or "/scripts/" in f"/{normalized}"
        or normalized.startswith("script/")
        or normalized.startswith("deployment/")
    ):
        return "shell"
    if lower_name in {"changelog", "copying", "install", "mit-license", "readme", "readme_for_app", "running_tests", "upgrading", "usage"}:
        return "markdown"
    if lower_name in {"empty", "placeholder", "teapot", "fake_file", "d", "image_no_extension", "not_an_image"}:
        return "data"
    if lower_name in {"csslintrc", "editorconfig", "eslintignore", "gitattributes", "htaccess", "unicorn_launcher"}:
        return "config"
    if lower_name.startswith("rpm-gpg-key"):
        return "certificate"
    if lower_name in {"secret", "secrets"}:
        return "secret"
    if lower_name == ".keep":
        return "marker"
    if _is_ansible_inventory_path(normalized):
        return "ansible-inventory"
    if _is_ansible_variable_path(normalized):
        return "yaml"
    if not path.suffix and any(part in {"test", "tests"} for part in normalized.split("/")):
        return "text"
    if path.name == ".actrc":
        return "config"
    if lower_name == "web.config":
        return "xml"
    if lower_name.endswith(".blade.php"):
        return "blade"
    return LANGUAGE_BY_SUFFIX.get(path.suffix.lower(), "unknown")


def _language_from_shebang(path: Path) -> str | None:
    try:
        with path.open("rb") as handle:
            first_line = handle.read(200).splitlines()[0].decode("utf-8", errors="ignore").lower()
    except (OSError, IndexError):
        return None
    if not first_line.startswith("#!"):
        return None
    if "ruby" in first_line:
        return "ruby"
    if "php" in first_line:
        return "php"
    if "python" in first_line:
        return "python"
    if "node" in first_line or "deno" in first_line:
        return "javascript"
    if any(shell in first_line for shell in ("sh", "bash", "zsh", "fish")):
        return "shell"
    return "script"


def classify_role(relative_path: str) -> str:
    lower = relative_path.lower()
    name = Path(lower).name
    if is_generated_path(lower):
        return "generated"
    if is_test_path(lower):
        return "test"
    if is_sample_path(lower):
        return "sample"
    if is_resource_help_page(lower):
        return "documentation"
    if (
        name in CONFIG_NAMES_LOWER
        or lower in CONFIG_NAMES_LOWER
        or _is_config_artifact_name(name)
        or lower.endswith(".csproj")
        or lower.endswith(".config")
        or lower.endswith(".sbt")
        or lower.endswith(".dist")
        or lower.endswith(".production-sample")
        or lower.endswith((".gitignore", ".template", ".tunnel", ".engine", ".make", ".sublime-project"))
        or name == ".htaccess"
        or name.endswith("htaccess")
        or name.startswith(".env")
        or name in {"capfile", "procfile", "procfile.tunnel", "unicorn_launcher"}
        or lower.startswith(".github/workflows/")
        or re.fullmatch(r"pulumi\.[^.]+\.(?:ya?ml)", name) is not None
        or name.startswith("dockerfile-")
        or lower.endswith((".tf", ".tfvars", ".tfvars.json", ".tofu", ".pkr.hcl"))
        or name in {"terragrunt.hcl", "terraform.tfvars", ".terraform.lock.hcl"}
        or _is_ansible_project_config(lower)
    ):
        return "config"
    if lower.endswith(".sql") or lower.endswith("schema.prisma") or lower.endswith("mapper.xml"):
        return "data-layer"
    if lower.endswith(".ipynb"):
        return "notebook"
    if _is_data_project_config(lower):
        return "config"
    if _is_data_project_catalog(lower):
        return "data-layer"
    if lower.endswith((".proto", ".graphql", ".graphqls", ".gql")):
        return "api"
    if lower == "conf/routes" or lower.endswith("/conf/routes"):
        return "api"
    if lower.endswith((".css", ".scss", ".sass", ".less")) or "/styles/" in f"/{lower}":
        return "style"
    if lower.endswith((".html", ".htm", ".ftl", ".hbs", ".handlebars", ".mustache", ".ejs", ".pug", ".twig", ".haml", ".liquid", ".erb", ".rsb", ".builder", ".ruby", ".cshtml", ".razor", ".xaml", ".axaml", ".blade.php", ".scala.html")):
        return "frontend-page"
    if lower.endswith(".jsp"):
        return "frontend-page"
    if lower.endswith((".svelte", ".dart", ".vue", ".swift")):
        return "frontend-page" if "/routes/" in f"/{lower}" or "/pages/" in f"/{lower}" else "source"
    if lower.startswith(("public/", "static/", "assets/")) or any(
        marker in f"/{lower}"
        for marker in (
            "/src/main/resources/static/",
            "/src/main/resources/templates/",
            "/assets/",
        )
    ):
        return "asset"
    if (
        lower.endswith((".zip", ".xz", ".gz", ".war", ".jar", ".mp4", ".mp3", ".ogg", ".mov", ".mkv", ".webm", ".flac", ".xlsx", ".sqlite", ".db", ".sqlite-shm", ".sqlite-wal", ".crt", ".pem", ".key", ".p8"))
        or name.startswith("rpm-gpg-key")
    ):
        return "asset"
    if lower.endswith((".eot", ".woff", ".woff2", ".ttf", ".otf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".svgz", ".avif", ".tif", ".tiff", ".bmp", ".heic", ".jp2", ".pct", ".ico", ".mmdb")):
        return "asset"
    if lower.endswith((".pdf", ".docx", ".odt", ".rtf", ".ps", ".crx", ".bin", ".dat")):
        return "asset"
    if lower.endswith((".vtt", ".dfxp", ".log")):
        return "documentation"
    if lower.endswith((".po", ".pot", ".mo", ".xlf", ".xliff")):
        return "documentation"
    if lower.endswith((".md", ".mdx", ".rdoc", ".rst", ".me", ".textile")) or lower.startswith(("docs/", "doc/")) or name.startswith(("license.", "readme.")):
        return "documentation"
    if "/controller" in lower or name.endswith(("controller.java", "controller.scala")):
        return "api"
    if "/model" in lower or "/entity" in lower or name.endswith("entity.java"):
        return "data-model"
    if "/repository" in lower or name.endswith("repository.java"):
        return "repository"
    if "/service" in lower or name.endswith("service.java"):
        return "service"
    if "/src/main/webapp/" in f"/{lower}":
        return "webapp"
    if name in {"main.py", "cli.py", "index.ts", "index.js", "artisan"}:
        return "entrypoint"
    return "source"


def is_generated_path(relative_path: str) -> bool:
    normalized = relative_path.replace("\\", "/").lower()
    name = Path(normalized).name
    if normalized.endswith((".map", ".wasm", ".tfstate", ".tfstate.backup")):
        return True
    if name in {"secret", "secrets"}:
        return True
    if name in {".keep", ".gitkeep"} or normalized.endswith(".enc"):
        return True
    if normalized.endswith((".bak", ".orig", ".save", ".swo", ".swp")) or name.endswith("~"):
        return True
    if normalized.endswith((".snap", ".mo")):
        return True
    if name.endswith((".min.js", ".bundle.js", ".chunk.js")):
        return True
    if re.fullmatch(r"[0-9a-f]{6,}-.+hmr\.js", name):
        return True
    if re.fullmatch(r"[A-Za-z0-9_]+/output\.js", normalized) or normalized.endswith("/deps/output.js"):
        return True
    if name.endswith((".pb.go", "_grpc.pb.go", "_pb2.py", "_pb2_grpc.py", ".pb.ts", ".pb.js")):
        return True
    if name.endswith((".generated.ts", ".generated.tsx", ".generated.js", ".generated.jsx")):
        return True
    if name.endswith((".g.dart", ".freezed.dart", ".gr.dart")):
        return True
    if name.startswith("main.") and name.endswith(".dart.js"):
        return True
    generated_markers = (
        "/public/build/",
        "/public/canvaskit/",
        "/build/generated/",
        "/generated/",
        "/coverage/",
        "/storybook-static/",
    )
    return any(marker in f"/{normalized}" for marker in generated_markers)

def is_test_path(relative_path: str) -> bool:
    normalized = relative_path.replace("\\", "/").lower()
    name = Path(normalized).name
    is_root_python_test = "/" not in normalized and (
        name.startswith("test_") or name.endswith(("_test.py", "_tests.py"))
    )
    is_test_named_source = name.endswith(
        (
            "_test.go",
            "_test.rs",
            "_test.exs",
            "_test.rb",
            "_test.php",
            "_test.cs",
            "_test.ts",
            "_test.tsx",
            "_test.js",
            "_test.jsx",
            "_spec.rb",
            "_spec.php",
            ".test.ts",
            ".test.tsx",
            ".test.js",
            ".test.jsx",
            ".test.mjs",
            ".test.cjs",
            ".spec.ts",
            ".spec.tsx",
            ".spec.js",
            ".spec.jsx",
            ".spec.mjs",
            ".spec.cjs",
            ".e2e.ts",
            ".e2e.tsx",
            ".e2e.js",
            ".e2e.jsx",
            ".e2e.mjs",
            ".e2e.cjs",
        )
    ) or "test-cases" in name or "test_cases" in name
    is_mobile_test_source_set = re.search(r"/src/(?:androidtest|test[a-z0-9_-]*)/", f"/{normalized}/") is not None
    return (
        normalized.startswith("test/")
        or normalized.startswith("tests/")
        or normalized.startswith("spec/")
        or normalized.startswith("features/")
        or normalized.startswith(".astro/test_")
        or normalized.startswith("molecule/")
        or "/molecule/" in normalized
        or "/test/" in normalized
        or "/tests/" in normalized
        or "/spec/" in normalized
        or is_mobile_test_source_set
        or normalized.startswith("e2e/")
        or normalized.startswith("playwright/")
        or "/e2e/" in normalized
        or "/playwright/" in normalized
        or "__tests__" in normalized.split("/")
        or "__mocks__" in normalized.split("/")
        or "__testfixtures__" in normalized.split("/")
        or "testfixtures" in normalized.split("/")
        or "test-fixtures" in normalized.split("/")
        or "testutils" in normalized.split("/")
        or "test-utils" in normalized.split("/")
        or is_root_python_test
        or is_test_named_source
        or name.endswith(".tftest.hcl")
        or name.endswith(".feature")
    )


def _is_config_artifact_name(name: str) -> bool:
    return bool(
        re.fullmatch(r"(?:tsconfig|jsconfig)(?:[.\w-]*)?\.json", name)
        or name in {".eslintrc.json", ".eslintrc.js", ".eslintrc.cjs", ".stylelintrc.json"}
        or name.endswith((".config.js", ".config.ts", ".config.mjs", ".config.cjs", ".conf.js", ".conf.ts"))
    )


def is_sample_path(relative_path: str) -> bool:
    normalized = relative_path.replace("\\", "/").lower()
    parts = normalized.split("/")
    name = Path(normalized).name
    if "/create-woo-extension/variants/" in f"/{normalized}":
        return True
    return any(
        part in {"fixtures", "fixture", "__fixtures__", "fakes", "testdata", "snapshots", "__snapshots__", "bench", "benchmark", "benchmarks", "evals", "examples", ".storybook", "storybookutils", "storybook-utils"}
        or part.startswith("benchmark-")
        for part in parts
    ) or name.endswith((".eml", ".response", ".sample", ".stories.ts", ".stories.tsx", ".stories.js", ".stories.jsx", ".stories.mjs", ".stories.cjs"))


def is_resource_help_page(relative_path: str) -> bool:
    normalized = relative_path.replace("\\", "/").lower()
    name = Path(normalized).name
    return (
        (
            "/src/main/resources/" in f"/{normalized}"
            or "/src/main/webapp/help/" in f"/{normalized}"
            or "/war/src/main/webapp/help/" in f"/{normalized}"
        )
        and name.endswith(".html")
        and (
            name == "help.html"
            or name.startswith("help-")
            or name.startswith("help_")
            or "/src/main/webapp/help/" in f"/{normalized}"
            or "/war/src/main/webapp/help/" in f"/{normalized}"
        )
    )


def _is_data_project_config(lower: str) -> bool:
    name = Path(lower).name
    return (
        name in {
            "dbt_project.yml",
            "dbt_project.yaml",
            "dagster.yaml",
            "great_expectations.yml",
            "great_expectations.yaml",
            "packages.yml",
            "packages.yaml",
            "prefect.yaml",
            "profiles.yml",
            "profiles.yaml",
            "workspace.yaml",
            "workspace.yml",
        }
        or lower.startswith(("great_expectations/", "gx/")) and name.endswith((".yml", ".yaml", ".json"))
    )


def _is_data_project_catalog(lower: str) -> bool:
    name = Path(lower).name
    return (
        name in {"catalog.yml", "catalog.yaml", "parameters.yml", "parameters.yaml"}
        and ("/conf/" in f"/{lower}" or lower.startswith("conf/"))
    )


def _is_ansible_project_config(lower: str) -> bool:
    name = Path(lower).name
    if name in {
        "ansible.cfg",
        "galaxy.yml",
        "galaxy.yaml",
        "hosts",
        "inventory",
        "molecule.yml",
        "molecule.yaml",
        "requirements.yml",
        "requirements.yaml",
    }:
        return True
    parts = lower.split("/")
    if _is_ansible_inventory_path(lower) or _is_ansible_variable_path(lower):
        return True
    if "roles" in parts and "templates" in parts:
        return True
    return bool(
        lower.endswith((".yml", ".yaml"))
        and any(part in {"tasks", "handlers", "defaults", "vars", "meta", "playbooks", "group_vars", "host_vars"} for part in parts)
    )


def _is_ansible_inventory_path(lower: str) -> bool:
    name = Path(lower).name
    return (
        name in {"hosts", "inventory"}
        or name.startswith("hosts.")
        or name.startswith("inventory-")
        or name.startswith("inventory_")
        or name.startswith("inventory.")
        or "/inventory/" in f"/{lower}/"
    )


def _is_ansible_variable_path(lower: str) -> bool:
    parts = lower.split("/")
    name = Path(lower).name
    return (
        any(part in {"group_vars", "host_vars"} for part in parts)
        and not name.startswith(".")
        and (Path(lower).suffix in {"", ".yml", ".yaml", ".j2"} or name in {"all", "vault"})
    )

def collect_dependencies(root: Path) -> list[DependencyFact]:
    collectors = [
        _dependencies_from_pyproject,
        _dependencies_from_requirements,
        _dependencies_from_package_json,
        _dependencies_from_pom,
        _dependencies_from_gradle,
        _dependencies_from_gradle_version_catalogs,
        _dependencies_from_cargo,
        _dependencies_from_composer,
        _dependencies_from_csproj,
        _dependencies_from_gemfile,
        _dependencies_from_gemspec,
        _dependencies_from_go_mod,
        _dependencies_from_mix,
        _dependencies_from_project_clj,
        _dependencies_from_build_sbt,
        _dependencies_from_pubspec,
        _dependencies_from_deps_edn,
        _dependencies_from_swift_package,
    ]
    dependencies: list[DependencyFact] = []
    for collector in collectors:
        dependencies.extend(collector(root))
    return sorted(dependencies, key=lambda item: (item.source, item.scope, item.name))

def _dependencies_from_pyproject(root: Path) -> list[DependencyFact]:
    path = root / "pyproject.toml"
    if not path.exists():
        return []
    data = tomllib.loads(_read_manifest_text(path))
    project = data.get("project", {})
    items = project.get("dependencies", [])
    result = [_dependency(str(item), "pyproject.toml", "runtime") for item in items]
    optional = project.get("optional-dependencies", {})
    for group_name, group_items in optional.items():
        result.extend(_dependency(str(item), "pyproject.toml", group_name) for item in group_items)
    return result

def _dependencies_from_requirements(root: Path) -> list[DependencyFact]:
    result: list[DependencyFact] = []
    for path in _manifest_paths(root, "requirements.txt"):
        source = path.relative_to(root).as_posix()
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith(("-r ", "--")):
                continue
            result.append(_dependency(stripped, source, "runtime"))
    return result

def _dependencies_from_package_json(root: Path) -> list[DependencyFact]:
    result: list[DependencyFact] = []
    for path in _manifest_paths(root, "package.json"):
        data = _read_json_manifest(path)
        if not isinstance(data, dict):
            continue
        source = path.relative_to(root).as_posix()
        for scope_name, scope in [("dependencies", "runtime"), ("devDependencies", "development")]:
            section = data.get(scope_name, {})
            if isinstance(section, dict):
                for name in section:
                    result.append(_dependency(name, source, scope))
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
    result: list[DependencyFact] = []
    candidates = sorted(
        {
            *(path for path in root.rglob("build.gradle")),
            *(path for path in root.rglob("build.gradle.kts")),
        }
    )
    dependency_pattern = re.compile(r"""(?:implementation|api|runtimeOnly|testImplementation)\s*\(?\s*["']([^"']+)["']""")
    plugin_pattern = re.compile(r"""\bid\s*\(\s*["']([^"']+)["']\s*\)""")
    for path in candidates:
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        relative = path.relative_to(root).as_posix()
        source = path.read_text(encoding="utf-8", errors="ignore")
        for match in dependency_pattern.finditer(source):
            result.append(_dependency(match.group(1), relative, "gradle"))
        for match in plugin_pattern.finditer(source):
            result.append(_dependency(match.group(1), relative, "gradle-plugin"))
    return result


def _dependencies_from_gradle_version_catalogs(root: Path) -> list[DependencyFact]:
    result: list[DependencyFact] = []
    for path in sorted(root.rglob("libs.versions.toml")):
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        source = path.relative_to(root).as_posix()
        try:
            data = tomllib.loads(_read_manifest_text(path))
        except tomllib.TOMLDecodeError:
            continue
        libraries = data.get("libraries", {})
        if isinstance(libraries, dict):
            for item in libraries.values():
                if isinstance(item, str):
                    result.append(_dependency(item, source, "version-catalog"))
                elif isinstance(item, dict):
                    module = item.get("module")
                    group = item.get("group")
                    name = item.get("name")
                    if isinstance(module, str):
                        result.append(_dependency(module, source, "version-catalog"))
                    elif isinstance(group, str) and isinstance(name, str):
                        result.append(_dependency(f"{group}:{name}", source, "version-catalog"))
        plugins = data.get("plugins", {})
        if isinstance(plugins, dict):
            for item in plugins.values():
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    result.append(_dependency(item["id"], source, "version-catalog-plugin"))
    return result


def _dependencies_from_cargo(root: Path) -> list[DependencyFact]:
    result: list[DependencyFact] = []
    for path in _manifest_paths(root, "Cargo.toml"):
        data = tomllib.loads(_read_manifest_text(path))
        source = path.relative_to(root).as_posix()
        for section_name, scope in [
            ("dependencies", "runtime"),
            ("dev-dependencies", "development"),
            ("build-dependencies", "build"),
        ]:
            section = data.get(section_name, {})
            if isinstance(section, dict):
                result.extend(_dependency(str(name), source, scope) for name in section)
    return result

def _dependencies_from_composer(root: Path) -> list[DependencyFact]:
    result: list[DependencyFact] = []
    for path in _manifest_paths(root, "composer.json"):
        data = _read_json_manifest(path)
        if not isinstance(data, dict):
            continue
        source = path.relative_to(root).as_posix()
        for section_name, scope in [("require", "runtime"), ("require-dev", "development")]:
            section = data.get(section_name, {})
            if isinstance(section, dict):
                result.extend(_dependency(str(name), source, scope) for name in section)
    return result

def _dependencies_from_csproj(root: Path) -> list[DependencyFact]:
    result: list[DependencyFact] = []
    for path in root.rglob("*.csproj"):
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        relative = path.relative_to(root).as_posix()
        try:
            source = _read_manifest_text(path)
        except UnicodeDecodeError:
            continue
        for match in re.finditer(r"<PackageReference\b[^>]*\bInclude=['\"]([^'\"]+)['\"]", source):
            result.append(_dependency(match.group(1), relative, "msbuild"))
        for match in re.finditer(r"<FrameworkReference\b[^>]*\bInclude=['\"]([^'\"]+)['\"]", source):
            result.append(_dependency(match.group(1), relative, "msbuild"))
    return result

def _dependencies_from_gemfile(root: Path) -> list[DependencyFact]:
    path = root / "Gemfile"
    if not path.exists():
        return []
    result: list[DependencyFact] = []
    for match in re.finditer(r"^\s*gem\s+['\"]([^'\"]+)['\"]", _read_manifest_text(path), re.MULTILINE):
        result.append(_dependency(match.group(1), "Gemfile", "runtime"))
    return result


def _dependencies_from_gemspec(root: Path) -> list[DependencyFact]:
    result: list[DependencyFact] = []
    for path in sorted(root.rglob("*.gemspec")):
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        relative = path.relative_to(root).as_posix()
        source = _read_manifest_text(path)
        for match in re.finditer(r"\.add_(?:runtime_)?dependency\s+['\"]([^'\"]+)['\"]", source):
            result.append(_dependency(match.group(1), relative, "gemspec"))
    return result


def _dependencies_from_go_mod(root: Path) -> list[DependencyFact]:
    path = root / "go.mod"
    if not path.exists():
        return []
    result: list[DependencyFact] = []
    for line in _read_manifest_text(path).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "module ", "go ", "require (", ")")):
            continue
        if stripped.startswith("require "):
            stripped = stripped.removeprefix("require ").strip()
        module = stripped.split()[0] if stripped.split() else ""
        if module and "/" in module:
            result.append(_dependency(module, "go.mod", "runtime"))
    return result

def _dependencies_from_mix(root: Path) -> list[DependencyFact]:
    path = root / "mix.exs"
    if not path.exists():
        return []
    result: list[DependencyFact] = []
    for match in re.finditer(r"\{\s*:(?P<name>[A-Za-z_]\w*)\s*,", _read_manifest_text(path)):
        result.append(_dependency(match.group("name"), "mix.exs", "runtime"))
    return result


def _dependencies_from_project_clj(root: Path) -> list[DependencyFact]:
    result: list[DependencyFact] = []
    for path in _manifest_paths(root, "project.clj"):
        relative = path.relative_to(root).as_posix()
        source = _read_manifest_text(path)
        for match in re.finditer(r"\[\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\s+['\"]", source):
            result.append(_dependency(match.group(1), relative, "leiningen"))
    return result


def _dependencies_from_build_sbt(root: Path) -> list[DependencyFact]:
    result: list[DependencyFact] = []
    for path in _manifest_paths(root, "build.sbt"):
        relative = path.relative_to(root).as_posix()
        source = _read_manifest_text(path)
        for match in re.finditer(
            r"['\"](?P<org>[A-Za-z0-9_.-]+)['\"]\s+%{1,2}\s+['\"](?P<artifact>[A-Za-z0-9_.-]+)['\"]",
            source,
        ):
            result.append(_dependency(f"{match.group('org')}/{match.group('artifact')}", relative, "sbt"))
        for module in re.findall(r"\b(guice|javaWs|ws|jdbc|evolutions|ehcache|cacheApi|filters)\b", source):
            result.append(_dependency(f"play:{module}", relative, "sbt"))
        if "PlayScala" in source:
            result.append(_dependency("playframework/play-scala", relative, "sbt-plugin"))
        if "PlayJava" in source:
            result.append(_dependency("playframework/play-java", relative, "sbt-plugin"))
        if "PlayEbean" in source:
            result.append(_dependency("playframework/play-ebean", relative, "sbt-plugin"))
    return result


def _dependencies_from_pubspec(root: Path) -> list[DependencyFact]:
    result: list[DependencyFact] = []
    for path in sorted(root.rglob("pubspec.yaml")):
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        relative = path.relative_to(root).as_posix()
        section: str | None = None
        for line in _read_manifest_text(path).splitlines():
            if re.match(r"^(dependencies|dev_dependencies):\s*$", line):
                section = line.split(":", 1)[0]
                continue
            if section and line and not line.startswith((" ", "\t")):
                section = None
            if not section:
                continue
            match = re.match(r"^\s{2}([A-Za-z_][\w-]*):", line)
            if match:
                scope = "development" if section == "dev_dependencies" else "runtime"
                result.append(_dependency(match.group(1), relative, scope))
    return result

def _dependencies_from_deps_edn(root: Path) -> list[DependencyFact]:
    path = root / "deps.edn"
    if not path.exists():
        return []
    result: list[DependencyFact] = []
    source = _read_manifest_text(path)
    for match in re.finditer(r"(?P<name>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\s+\{", source):
        result.append(_dependency(match.group("name"), "deps.edn", "runtime"))
    return result

def _dependencies_from_swift_package(root: Path) -> list[DependencyFact]:
    result: list[DependencyFact] = []
    for path in _manifest_paths(root, "Package.swift"):
        source = _read_manifest_text(path)
        relative = path.relative_to(root).as_posix()
        for match in SWIFT_PACKAGE_DEPENDENCY_RE.finditer(source):
            body = match.group("body")
            url_match = SWIFT_PACKAGE_URL_RE.search(body)
            if not url_match:
                continue
            name = _swift_package_dependency_name(body, url_match.group("url"))
            if not name:
                continue
            line = _line_for_offset(source, match.start())
            result.append(
                DependencyFact(
                    name=name,
                    source=relative,
                    scope="swift-package",
                    evidence=Evidence(file=relative, kind="dependency", line_start=line, line_end=line),
                )
            )
    return result


def _swift_package_dependency_name(body: str, url: str) -> str | None:
    explicit_name = SWIFT_PACKAGE_NAME_RE.search(body)
    if explicit_name:
        return explicit_name.group("name")
    cleaned = url.rstrip("/")
    stem = cleaned.rsplit("/", 1)[-1].removesuffix(".git")
    return stem or None

def _dependency(name: str, source: str, scope: str) -> DependencyFact:
    return DependencyFact(
        name=name,
        source=source,
        scope=scope,
        evidence=Evidence(file=source, kind="dependency", note=f"Declared in {source}"),
    )


def _manifest_paths(root: Path, name: str) -> list[Path]:
    result: list[Path] = []
    for path in sorted(root.rglob(name)):
        relative = path.relative_to(root).as_posix()
        if (
            any(part in IGNORED_DIRS for part in path.relative_to(root).parts)
            or is_generated_path(relative)
            or is_test_path(relative)
            or is_sample_path(relative)
        ):
            continue
        result.append(path)
    return result


def collect_entrypoints(root: Path, files: list[FileFact]) -> list[EntrypointFact]:
    result: list[EntrypointFact] = []
    result.extend(_node_package_entrypoints(root))
    result.extend(_node_frontend_entrypoints(root))
    result.extend(_node_app_entrypoints(root))
    result.extend(_redwood_entrypoints(root))
    result.extend(_swift_vapor_entrypoints(root))
    result.extend(_swiftui_app_entrypoints(root, files))
    result.extend(_streamlit_entrypoints(root, files))
    result.extend(_gradio_entrypoints(root, files))
    result.extend(_dash_entrypoints(root, files))
    result.extend(_django_entrypoints(root))
    result.extend(_symfony_entrypoints(root))
    result.extend(_laravel_entrypoints(root))
    result.extend(_slim_entrypoints(root))
    result.extend(_sinatra_entrypoints(root))
    result.extend(_grape_entrypoints(root))
    result.extend(_go_entrypoints(root, files))
    result.extend(_cargo_entrypoints(root, files))
    result.extend(_gradle_entrypoints(root))
    result.extend(_mix_entrypoints(root))
    result.extend(_clojure_entrypoints(root, files))
    result.extend(_play_entrypoints(root))

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        data = tomllib.loads(_read_manifest_text(pyproject))
        scripts = data.get("project", {}).get("scripts", {})
        for command, target in scripts.items():
            result.append(_entrypoint(str(target), "python-console-script", str(command), "pyproject.toml"))

    result.extend(_rails_entrypoints(root))
    result.extend(_yii_entrypoints(root))

    for file_fact in files:
        name = Path(file_fact.path).name
        if name in {"main.py", "cli.py"} and file_fact.role == "entrypoint":
            result.append(_entrypoint(file_fact.path, "file-entrypoint", None, file_fact.path))
        if name == "Program.cs" and file_fact.language == "csharp" and file_fact.role not in {"test", "sample", "generated"}:
            command = _dotnet_run_command_for_program(root, file_fact)
            if command:
                result.append(_entrypoint(file_fact.path, "dotnet-program", command, file_fact.path))
    return sorted(result, key=lambda item: (item.kind, item.path, item.command or ""))

def _entrypoint(path: str, kind: str, command: str | None, evidence_file: str) -> EntrypointFact:
    return EntrypointFact(
        path=path,
        kind=kind,
        command=command,
        evidence=Evidence(file=evidence_file, kind="entrypoint"),
    )


def _swiftui_app_entrypoints(root: Path, files: list[FileFact]) -> list[EntrypointFact]:
    entrypoints: list[EntrypointFact] = []
    command = "swift build" if _swift_package_paths(root) else None
    for file_fact in files:
        if file_fact.language != "swift" or file_fact.role in {"test", "sample", "generated", "documentation"}:
            continue
        normalized = file_fact.path.replace("\\", "/").lower()
        if "/previews/" in f"/{normalized}":
            continue
        source = _read_manifest_text(root / file_fact.path)
        for match in SWIFTUI_MAIN_APP_RE.finditer(source):
            line = _line_for_offset(source, match.start())
            entrypoints.append(
                EntrypointFact(
                    path=file_fact.path,
                    kind="swiftui-app",
                    command=command,
                    evidence=Evidence(file=file_fact.path, kind="entrypoint", line_start=line, line_end=line),
                )
            )
    return entrypoints


def _clojure_entrypoints(root: Path, files: list[FileFact]) -> list[EntrypointFact]:
    entrypoints: list[EntrypointFact] = []
    if not _looks_like_clojure_project(root):
        return entrypoints
    for file_fact in files:
        if file_fact.language != "clojure" or file_fact.role in {"test", "sample", "generated", "documentation"}:
            continue
        source = _read_manifest_text(root / file_fact.path)
        if "(:gen-class)" not in source or not re.search(r"\(defn\s+-main\b", source):
            continue
        namespace = _clojure_namespace_from_source(source)
        command = f"clojure -M -m {namespace}" if namespace else "clojure -M -m <namespace>"
        line = _line_for_offset(source, source.find("(:gen-class)"))
        entrypoints.append(
            EntrypointFact(
                path=file_fact.path,
                kind="clojure-main",
                command=command,
                evidence=Evidence(file=file_fact.path, kind="entrypoint", line_start=line, line_end=line),
            )
        )
    return entrypoints


def _play_entrypoints(root: Path) -> list[EntrypointFact]:
    entrypoints: list[EntrypointFact] = []
    for project_dir in _play_project_dirs(root):
        routes = project_dir / "conf" / "routes"
        relative_routes = routes.relative_to(root).as_posix()
        entrypoints.append(
            EntrypointFact(
                path=relative_routes,
                kind="play-app",
                command="sbt run",
                evidence=Evidence(file=relative_routes, kind="entrypoint", line_start=1, line_end=1),
            )
        )
    return entrypoints


def collect_project_commands(root: Path, files: list[FileFact]) -> list[CommandFact]:
    commands: list[CommandFact] = []
    commands.extend(_node_package_script_commands(root))
    commands.extend(_redwood_project_commands(root))
    commands.extend(_swift_package_project_commands(root))
    commands.extend(_composer_script_commands(root))
    commands.extend(_wordpress_cli_commands(root, files))
    commands.extend(_streamlit_project_commands(root, files))
    commands.extend(_gradio_project_commands(root, files))
    commands.extend(_dash_project_commands(root, files))
    commands.extend(_django_project_commands(root))
    commands.extend(_symfony_project_commands(root))
    commands.extend(_rails_project_commands(root))
    commands.extend(_laravel_project_commands(root))
    commands.extend(_slim_project_commands(root))
    commands.extend(_sinatra_project_commands(root))
    commands.extend(_grape_project_commands(root))
    commands.extend(_yii_project_commands(root))
    commands.extend(_go_project_commands(root, files))
    commands.extend(_cargo_project_commands(root))
    commands.extend(_gradle_project_commands(root))
    commands.extend(_mix_project_commands(root))
    commands.extend(_clojure_project_commands(root))
    commands.extend(_sbt_project_commands(root))
    solution_paths = _dotnet_solution_paths(root)
    project_paths = _dotnet_project_paths(root)
    test_projects = [path for path in project_paths if is_test_path(path)]

    for solution in solution_paths:
        commands.append(
            _command(
                solution,
                "dotnet build",
                "Build .NET solution",
                [solution],
                [],
            )
        )
    if solution_paths and test_projects:
        for solution in solution_paths:
            commands.append(
                _command(
                    solution,
                    "dotnet test",
                    "Run .NET test suite",
                    [solution],
                    [],
                )
            )
    elif test_projects:
        for project in test_projects:
            commands.append(
                _command(
                    project,
                    "dotnet test",
                    "Run .NET test project",
                    [project],
                    [],
                )
            )

    for project in project_paths:
        source = _read_manifest_text(root / project)
        if _looks_like_dotnet_runnable_project(source):
            commands.append(
                _command(
                    project,
                    "dotnet run",
                    "Run .NET application project",
                    ["--project", project],
                    [],
                )
            )

    return _dedupe_commands(commands)


def _node_package_entrypoints(root: Path) -> list[EntrypointFact]:
    entrypoints: list[EntrypointFact] = []
    for package_json in _manifest_paths(root, "package.json"):
        data = _read_json_manifest(package_json)
        if not isinstance(data, dict):
            continue
        relative_manifest = package_json.relative_to(root).as_posix()
        package_dir = package_json.parent
        bins = data.get("bin", {})
        if isinstance(bins, str):
            target = _node_bin_target(root, package_dir, bins)
            entrypoints.append(_entrypoint(target, "node-bin", _string_value(data.get("name")), relative_manifest))
        elif isinstance(bins, dict):
            for command, target_value in bins.items():
                target = _string_value(target_value)
                if not target:
                    continue
                entrypoints.append(_entrypoint(_node_bin_target(root, package_dir, target), "node-bin", str(command), relative_manifest))
    return entrypoints


def _swift_package_project_commands(root: Path) -> list[CommandFact]:
    commands: list[CommandFact] = []
    for manifest in _swift_package_paths(root):
        relative_manifest = manifest.relative_to(root).as_posix()
        package_dir = manifest.parent.relative_to(root).as_posix()
        package_args = [] if package_dir == "." else ["--package-path", package_dir]
        package_prefix = "" if package_dir == "." else f" --package-path {package_dir}"
        commands.append(
            _command(
                relative_manifest,
                f"swift build{package_prefix}",
                "Build Swift package",
                [*package_args, "build"],
                [],
            )
        )
        commands.append(
            _command(
                relative_manifest,
                f"swift test{package_prefix}",
                "Run Swift package tests",
                [*package_args, "test"],
                [],
            )
        )
        commands.append(
            _command(
                relative_manifest,
                f"swift package resolve{package_prefix}",
                "Resolve Swift package dependencies",
                [*package_args, "package", "resolve"],
                [],
            )
        )
        source = _read_manifest_text(manifest)
        if _looks_like_vapor_package_source(source):
            for target in _swift_executable_targets(source):
                commands.append(
                    _command(
                        relative_manifest,
                        f"swift run{package_prefix} {target}".strip(),
                        "Run Vapor Swift server",
                        [*package_args, "run", target],
                        [],
                    )
                )
    return commands


def _swift_package_paths(root: Path) -> list[Path]:
    return _manifest_paths(root, "Package.swift")


def _swift_vapor_entrypoints(root: Path) -> list[EntrypointFact]:
    entrypoints: list[EntrypointFact] = []
    for manifest in _swift_package_paths(root):
        source = _read_manifest_text(manifest)
        if not _looks_like_vapor_package_source(source):
            continue
        relative_manifest = manifest.relative_to(root).as_posix()
        package_dir = manifest.parent
        package_relative = package_dir.relative_to(root).as_posix()
        package_prefix = "" if package_relative == "." else f" --package-path {package_relative}"
        for target in _swift_executable_targets(source):
            main_path = package_dir / "Sources" / target / "main.swift"
            path = main_path.relative_to(root).as_posix() if main_path.exists() else relative_manifest
            entrypoints.append(_entrypoint(path, "vapor-app", f"swift run{package_prefix} {target}".strip(), relative_manifest))
    return entrypoints


def _looks_like_vapor_package_source(source: str) -> bool:
    lowered = source.lower()
    return "github.com/vapor/vapor" in lowered or '.product(name: "vapor"' in lowered or "vapor" in lowered and "fluent" in lowered


def _swift_executable_targets(source: str) -> list[str]:
    targets = re.findall(r"\.executableTarget\s*\(\s*name\s*:\s*['\"]([^'\"]+)['\"]", source)
    targets.extend(re.findall(r"\.executable\s*\(\s*name\s*:\s*['\"]([^'\"]+)['\"]", source))
    return list(dict.fromkeys(targets))


def _clojure_project_commands(root: Path) -> list[CommandFact]:
    commands: list[CommandFact] = []
    deps = root / "deps.edn"
    project = root / "project.clj"
    if deps.exists():
        source = _read_manifest_text(deps)
        commands.append(_command("deps.edn", "clojure -M", "Run Clojure project with deps.edn", [], []))
        if ":test" in source:
            commands.append(_command("deps.edn", "clojure -M:test", "Run Clojure test alias", [], []))
        if ":build" in source:
            commands.append(_command("deps.edn", "clojure -T:build", "Run Clojure tools.build alias", [], []))
        main_ns = _clojure_main_namespace(root)
        if main_ns:
            commands.append(_command("deps.edn", f"clojure -M -m {main_ns}", "Run Clojure main namespace", [], []))
    if project.exists():
        project_source = _read_manifest_text(project)
        commands.append(_command("project.clj", "lein test", "Run Leiningen test suite", [], []))
        commands.append(_command("project.clj", "lein run", "Run Leiningen application", [], []))
        if "lein-ring" in project_source or "ring/ring-jetty-adapter" in project_source:
            commands.append(_command("project.clj", "lein ring server", "Run Ring development server", [], []))
    return commands


def _sbt_project_commands(root: Path) -> list[CommandFact]:
    commands: list[CommandFact] = []
    for build in _manifest_paths(root, "build.sbt"):
        project_dir = build.parent
        relative = build.relative_to(root).as_posix()
        project_relative = project_dir.relative_to(root).as_posix()
        options = [] if project_relative == "." else [f"cwd:{project_relative}"]
        commands.append(_command(relative, "sbt compile", "Compile sbt project", [], options))
        commands.append(_command(relative, "sbt test", "Run sbt test suite", [], options))
        if _looks_like_play_project_dir(project_dir):
            commands.append(_command(relative, "sbt run", "Run Play/sbt application", [], options))
            commands.append(_command(relative, "sbt routes", "Inspect Play routes", [], options))
    return commands


def _play_project_dirs(root: Path) -> list[Path]:
    dirs: list[Path] = []
    for build in _manifest_paths(root, "build.sbt"):
        project_dir = build.parent
        if _looks_like_play_project_dir(project_dir):
            dirs.append(project_dir)
    return sorted(_dedupe_paths(dirs), key=lambda item: item.relative_to(root).as_posix())


def _looks_like_play_project_dir(project_dir: Path) -> bool:
    build = project_dir / "build.sbt"
    routes = project_dir / "conf" / "routes"
    if not build.exists() or not routes.exists():
        return False
    source = _read_manifest_text(build)
    return "PlayScala" in source or "PlayJava" in source or "playframework" in source.lower() or "play-" in source.lower()


def _go_entrypoints(root: Path, files: list[FileFact]) -> list[EntrypointFact]:
    entrypoints: list[EntrypointFact] = []
    for file_fact in files:
        if file_fact.language != "go" or file_fact.role in {"test", "sample", "generated", "documentation"}:
            continue
        source = _read_manifest_text(root / file_fact.path)
        main_offset = _go_main_offset(source)
        if main_offset is None:
            continue
        line = _line_for_offset(source, main_offset)
        entrypoints.append(
            EntrypointFact(
                path=file_fact.path,
                kind="go-main",
                command=_go_run_command(root, file_fact.path),
                evidence=Evidence(file=file_fact.path, kind="entrypoint", line_start=line, line_end=line),
            )
        )
    return entrypoints


def _go_project_commands(root: Path, files: list[FileFact]) -> list[CommandFact]:
    if not (root / "go.mod").exists():
        return []
    commands = [
        _command("go.mod", "go test ./...", "Run Go test suite", ["test", "./..."], []),
        _command("go.mod", "go build ./...", "Build Go packages", ["build", "./..."], []),
    ]
    for command in _go_main_run_commands(root, files):
        commands.append(command)
    return commands


def _go_main_run_commands(root: Path, files: list[FileFact]) -> list[CommandFact]:
    commands: list[CommandFact] = []
    seen_dirs: set[str] = set()
    for file_fact in files:
        if file_fact.language != "go" or file_fact.role in {"test", "sample", "generated", "documentation"}:
            continue
        source = _read_manifest_text(root / file_fact.path)
        if _go_main_offset(source) is None:
            continue
        run_command = _go_run_command(root, file_fact.path)
        command_dir = _go_package_dir(file_fact.path)
        if command_dir in seen_dirs:
            continue
        seen_dirs.add(command_dir)
        commands.append(
            _command(
                file_fact.path,
                run_command,
                "Run Go main package",
                ["run", "." if command_dir == "." else f"./{command_dir}"],
                [],
            )
        )
    return commands


def _go_main_offset(source: str) -> int | None:
    if re.search(r"(?m)^\s*package\s+main\b", source) is None:
        return None
    match = re.search(r"(?m)^\s*func\s+main\s*\(", source)
    return match.start() if match else None


def _go_run_command(root: Path, relative_path: str) -> str:
    if (root / "go.mod").exists():
        package_dir = _go_package_dir(relative_path)
        return "go run ." if package_dir == "." else f"go run ./{package_dir}"
    return f"go run {relative_path}"


def _go_package_dir(relative_path: str) -> str:
    normalized = relative_path.replace("\\", "/")
    if "/" not in normalized:
        return "."
    return normalized.rsplit("/", 1)[0]


def _cargo_entrypoints(root: Path, files: list[FileFact]) -> list[EntrypointFact]:
    entrypoints: list[EntrypointFact] = []
    for file_fact in files:
        if file_fact.language != "rust" or file_fact.role in {"test", "sample", "generated", "documentation"}:
            continue
        manifest = _nearest_cargo_manifest(root, file_fact.path)
        if manifest is None or not _is_cargo_entrypoint_path(root, manifest, file_fact.path):
            continue
        source = _read_manifest_text(root / file_fact.path)
        main_offset = _rust_main_offset(source)
        if main_offset is None:
            continue
        line = _line_for_offset(source, main_offset)
        entrypoints.append(
            EntrypointFact(
                path=file_fact.path,
                kind="cargo-main",
                command=_cargo_run_command(root, manifest, file_fact.path),
                evidence=Evidence(file=file_fact.path, kind="entrypoint", line_start=line, line_end=line),
            )
        )
    return entrypoints


def _is_cargo_entrypoint_path(root: Path, manifest: Path, relative_path: str) -> bool:
    normalized = relative_path.replace("\\", "/")
    if normalized.endswith("/build.rs") or normalized == "build.rs":
        return False
    package_dir = manifest.parent.relative_to(root).as_posix()
    local_path = normalized
    if package_dir != "." and normalized.startswith(f"{package_dir}/"):
        local_path = normalized[len(package_dir) + 1 :]
    if local_path == "src/main.rs":
        return True
    if re.fullmatch(r"src/bin/[^/]+\.rs", local_path):
        return True
    return normalized in _cargo_manifest_bin_paths(root, manifest)


def _cargo_manifest_bin_paths(root: Path, manifest: Path) -> set[str]:
    source = _read_manifest_text(manifest)
    paths: set[str] = set()
    for section in re.findall(r"(?ms)^\s*\[\[bin\]\]\s*(.*?)(?=^\s*\[|\Z)", source):
        path_match = re.search(r'(?m)^\s*path\s*=\s*["\'](?P<path>[^"\']+)["\']', section)
        if path_match:
            paths.add((manifest.parent / path_match.group("path")).relative_to(root).as_posix())
    return paths


def _cargo_project_commands(root: Path) -> list[CommandFact]:
    commands: list[CommandFact] = []
    for manifest in _manifest_paths(root, "Cargo.toml"):
        relative_manifest = manifest.relative_to(root).as_posix()
        manifest_arg = _cargo_manifest_arg(root, manifest)
        commands.append(
            _command(
                relative_manifest,
                f"cargo build{manifest_arg}",
                "Build Rust crate",
                _cargo_arguments("build", manifest_arg),
                [],
            )
        )
        commands.append(
            _command(
                relative_manifest,
                f"cargo test{manifest_arg}",
                "Run Rust test suite",
                _cargo_arguments("test", manifest_arg),
                [],
            )
        )
        if (manifest.parent / "src" / "main.rs").exists():
            commands.append(
                _command(
                    relative_manifest,
                    f"cargo run{manifest_arg}",
                    "Run Rust binary",
                    _cargo_arguments("run", manifest_arg),
                    [],
                )
            )
    return commands


def _rust_main_offset(source: str) -> int | None:
    match = re.search(r"(?m)^\s*(?:pub\s+)?(?:async\s+)?fn\s+main\s*\(", source)
    return match.start() if match else None


def _nearest_cargo_manifest(root: Path, relative_path: str) -> Path | None:
    current = (root / relative_path).parent
    while current == root or root in current.parents:
        manifest = current / "Cargo.toml"
        if manifest.exists():
            return manifest
        if current == root:
            break
        current = current.parent
    return root / "Cargo.toml" if (root / "Cargo.toml").exists() else None


def _cargo_run_command(root: Path, manifest: Path, relative_path: str) -> str:
    manifest_arg = _cargo_manifest_arg(root, manifest)
    normalized = relative_path.replace("\\", "/")
    package_dir = manifest.parent.relative_to(root).as_posix()
    local_path = normalized
    if package_dir != "." and normalized.startswith(f"{package_dir}/"):
        local_path = normalized[len(package_dir) + 1 :]
    bin_match = re.fullmatch(r"src/bin/(?P<name>[^/]+)\.rs", local_path)
    if bin_match:
        return f"cargo run{manifest_arg} --bin {bin_match.group('name')}"
    return f"cargo run{manifest_arg}"


def _cargo_manifest_arg(root: Path, manifest: Path) -> str:
    relative_manifest = manifest.relative_to(root).as_posix()
    return "" if relative_manifest == "Cargo.toml" else f" --manifest-path {relative_manifest}"


def _cargo_arguments(action: str, manifest_arg: str) -> list[str]:
    if not manifest_arg:
        return [action]
    parts = manifest_arg.strip().split()
    return [action, *parts]


def _node_bin_target(root: Path, package_dir: Path, target: str) -> str:
    target_path = Path(target.replace("\\", "/"))
    if target_path.is_absolute():
        return target_path.as_posix()
    return (package_dir / target_path).relative_to(root).as_posix()


def _node_frontend_entrypoints(root: Path) -> list[EntrypointFact]:
    entrypoints: list[EntrypointFact] = []
    package_manager = _node_package_manager(root)
    for package_json in _manifest_paths(root, "package.json"):
        data = _read_json_manifest(package_json)
        if not isinstance(data, dict):
            continue
        package_dir = package_json.parent
        candidates: list[Path]
        if _looks_like_next_frontend_package(package_dir, data):
            kind = "next-entrypoint"
            candidates = _next_entrypoint_candidates(package_dir)
        elif _looks_like_astro_frontend_package(package_dir, data):
            kind = "astro-entrypoint"
            candidates = _astro_entrypoint_candidates(package_dir)
        elif _looks_like_sveltekit_frontend_package(package_dir, data):
            kind = "sveltekit-entrypoint"
            candidates = _sveltekit_entrypoint_candidates(package_dir)
        elif _looks_like_vite_frontend_package(root, package_dir, data):
            kind = "vite-react-entrypoint" if _package_has_dependency(data, "react") else "vite-entrypoint"
            candidates = _frontend_entrypoint_candidates(package_dir)
        elif _looks_like_nuxt_frontend_package(package_dir, data):
            kind = "nuxt-entrypoint"
            candidates = _nuxt_entrypoint_candidates(package_dir)
        elif _looks_like_angular_frontend_package(package_dir, data):
            kind = "angular-entrypoint"
            candidates = _angular_entrypoint_candidates(package_dir)
        else:
            continue
        scripts = data.get("scripts", {})
        if not isinstance(scripts, dict):
            scripts = {}
        if kind == "angular-entrypoint":
            script_name = "start" if "start" in scripts else "dev" if "dev" in scripts else None
        else:
            script_name = "dev" if "dev" in scripts else "start" if "start" in scripts else None
        package_dir_arg = package_dir.relative_to(root).as_posix()
        if package_dir_arg == ".":
            package_dir_arg = ""
        command = _node_package_script_command(package_manager, package_dir_arg, script_name) if script_name else None
        relative_manifest = package_json.relative_to(root).as_posix()
        for target in candidates:
            if target.exists() and target.is_file():
                entrypoints.append(_entrypoint(target.relative_to(root).as_posix(), kind, command, relative_manifest))
                break
    return entrypoints


def _looks_like_vite_frontend_package(root: Path, package_dir: Path, data: dict[str, object]) -> bool:
    if _package_has_dependency(data, "vite"):
        return True
    return any((package_dir / name).exists() for name in ("vite.config.js", "vite.config.ts", "vite.config.mjs", "vite.config.mts"))


def _looks_like_next_frontend_package(package_dir: Path, data: dict[str, object]) -> bool:
    if _package_has_dependency(data, "next"):
        return True
    return any((package_dir / name).exists() for name in ("next.config.js", "next.config.ts", "next.config.mjs"))


def _looks_like_astro_frontend_package(package_dir: Path, data: dict[str, object]) -> bool:
    if _package_has_dependency(data, "astro") or _package_has_dependency(data, "@astrojs/starlight"):
        return True
    return any(
        (package_dir / name).exists()
        for name in ("astro.config.js", "astro.config.ts", "astro.config.mjs", "astro.config.mts")
    )


def _looks_like_sveltekit_frontend_package(package_dir: Path, data: dict[str, object]) -> bool:
    if _package_has_dependency(data, "@sveltejs/kit"):
        return True
    return any((package_dir / name).exists() for name in ("svelte.config.js", "svelte.config.ts", "svelte.config.mjs"))


def _looks_like_nuxt_frontend_package(package_dir: Path, data: dict[str, object]) -> bool:
    if _package_has_dependency(data, "nuxt") or _package_has_dependency(data, "@nuxt/schema"):
        return True
    return any((package_dir / name).exists() for name in ("nuxt.config.js", "nuxt.config.ts", "nuxt.config.mjs"))


def _looks_like_angular_frontend_package(package_dir: Path, data: dict[str, object]) -> bool:
    if _package_has_any_dependency(data, {"@angular/core", "@angular/cli", "@angular/router"}):
        return True
    return (package_dir / "angular.json").exists()


def _package_has_dependency(data: dict[str, object], name: str) -> bool:
    for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        dependencies = data.get(section, {})
        if isinstance(dependencies, dict) and name in dependencies:
            return True
    return False


def _package_has_any_dependency(data: dict[str, object], names: set[str]) -> bool:
    return any(_package_has_dependency(data, name) for name in names)


def _frontend_entrypoint_candidates(package_dir: Path) -> list[Path]:
    return [
        package_dir / "src" / "main.tsx",
        package_dir / "src" / "main.jsx",
        package_dir / "src" / "main.ts",
        package_dir / "src" / "main.js",
        package_dir / "src" / "index.tsx",
        package_dir / "src" / "index.jsx",
        package_dir / "src" / "index.ts",
        package_dir / "src" / "index.js",
        package_dir / "main.tsx",
        package_dir / "main.jsx",
        package_dir / "index.tsx",
        package_dir / "index.jsx",
    ]


def _next_entrypoint_candidates(package_dir: Path) -> list[Path]:
    return [
        package_dir / "src" / "app" / "layout.tsx",
        package_dir / "src" / "app" / "layout.ts",
        package_dir / "src" / "app" / "page.tsx",
        package_dir / "src" / "app" / "page.ts",
        package_dir / "app" / "layout.tsx",
        package_dir / "app" / "layout.ts",
        package_dir / "app" / "page.tsx",
        package_dir / "app" / "page.ts",
        package_dir / "src" / "pages" / "_app.tsx",
        package_dir / "src" / "pages" / "_app.ts",
        package_dir / "src" / "pages" / "index.tsx",
        package_dir / "src" / "pages" / "index.ts",
        package_dir / "pages" / "_app.tsx",
        package_dir / "pages" / "_app.ts",
        package_dir / "pages" / "index.tsx",
        package_dir / "pages" / "index.ts",
        package_dir / "next.config.ts",
        package_dir / "next.config.js",
        package_dir / "next.config.mjs",
    ]


def _astro_entrypoint_candidates(package_dir: Path) -> list[Path]:
    return [
        package_dir / "src" / "pages" / "index.astro",
        package_dir / "src" / "pages" / "index.mdx",
        package_dir / "src" / "pages" / "index.md",
        package_dir / "src" / "layouts" / "Layout.astro",
        package_dir / "src" / "content.config.ts",
        package_dir / "src" / "content.config.js",
        package_dir / "astro.config.ts",
        package_dir / "astro.config.mjs",
        package_dir / "astro.config.js",
    ]


def _sveltekit_entrypoint_candidates(package_dir: Path) -> list[Path]:
    return [
        package_dir / "src" / "routes" / "+page.svelte",
        package_dir / "src" / "routes" / "+layout.svelte",
        package_dir / "src" / "app.html",
        package_dir / "svelte.config.ts",
        package_dir / "svelte.config.js",
        package_dir / "svelte.config.mjs",
    ]


def _nuxt_entrypoint_candidates(package_dir: Path) -> list[Path]:
    return [
        package_dir / "app.vue",
        package_dir / "pages" / "index.vue",
        package_dir / "src" / "app.vue",
        package_dir / "src" / "pages" / "index.vue",
        package_dir / "src" / "main.ts",
        package_dir / "src" / "main.js",
    ]


def _angular_entrypoint_candidates(package_dir: Path) -> list[Path]:
    return [
        package_dir / "src" / "main.ts",
        package_dir / "src" / "main.js",
        package_dir / "src" / "app" / "app.module.ts",
        package_dir / "src" / "app" / "app.config.ts",
        package_dir / "main.ts",
        package_dir / "main.js",
    ]


def _node_app_entrypoints(root: Path) -> list[EntrypointFact]:
    entrypoints: list[EntrypointFact] = []
    package_manager = _node_package_manager(root)
    for package_json in _manifest_paths(root, "package.json"):
        data = _read_json_manifest(package_json)
        if not isinstance(data, dict):
            continue
        package_dir = package_json.parent
        scripts = data.get("scripts", {})
        if not isinstance(scripts, dict):
            scripts = {}
        if not _looks_like_node_app_package(package_dir, data, scripts):
            continue
        script_name = _node_app_script_name(scripts)
        package_dir_arg = package_dir.relative_to(root).as_posix()
        if package_dir_arg == ".":
            package_dir_arg = ""
        command = _node_package_script_command(package_manager, package_dir_arg, script_name) if script_name else None
        relative_manifest = package_json.relative_to(root).as_posix()
        if _looks_like_remix_server_package(data):
            kind = "remix-server-entrypoint"
        elif _package_has_any_dependency(data, {"@nestjs/core", "@nestjs/common"}):
            kind = "nestjs-entrypoint"
        else:
            kind = "node-app-entrypoint"
        for target in _node_app_entrypoint_candidates(package_dir, data, scripts):
            if target.exists() and target.is_file():
                entrypoints.append(_entrypoint(target.relative_to(root).as_posix(), kind, command, relative_manifest))
                break
    return entrypoints


def _looks_like_node_app_package(package_dir: Path, data: dict[str, object], scripts: dict[object, object]) -> bool:
    is_remix_server = _looks_like_remix_server_package(data)
    if (
        not is_remix_server
        and (
            _looks_like_vite_frontend_package(package_dir, package_dir, data)
            or _looks_like_nuxt_frontend_package(package_dir, data)
            or _looks_like_angular_frontend_package(package_dir, data)
        )
    ):
        return False
    server_dependencies = {
        "@nestjs/core",
        "@nestjs/common",
        "express",
        "fastify",
        "koa",
        "hono",
        "hapi",
        "@hapi/hapi",
        "@feathersjs/feathers",
        "@feathersjs/express",
        "feathers",
        "@remix-run/express",
    }
    if not _package_has_any_dependency(data, server_dependencies):
        return False
    return bool(_node_app_entrypoint_candidates(package_dir, data, scripts))


def _looks_like_remix_server_package(data: dict[str, object]) -> bool:
    return _package_has_any_dependency(data, {"@remix-run/express", "@remix-run/node", "@remix-run/server-runtime"})


def _node_app_script_name(scripts: dict[object, object]) -> str | None:
    for script_name in ("start", "dev", "serve"):
        if isinstance(scripts.get(script_name), str):
            return script_name
    for script_name, script_body in scripts.items():
        if isinstance(script_name, str) and isinstance(script_body, str) and "ENTRYPOINT=" in script_body:
            return script_name
    return None


def _node_app_entrypoint_candidates(package_dir: Path, data: dict[str, object], scripts: dict[object, object]) -> list[Path]:
    explicit_entrypoints: list[Path] = []
    for script_body in scripts.values():
        if not isinstance(script_body, str):
            continue
        for token in re.findall(r"\bENTRYPOINT=([^\s]+)", script_body):
            explicit_entrypoints.extend(_resolve_node_entrypoint_token(package_dir, token))
    if explicit_entrypoints:
        return _dedupe_paths(explicit_entrypoints)

    candidates: list[Path] = []
    for script_body in scripts.values():
        if isinstance(script_body, str):
            candidates.extend(_node_script_entrypoint_candidates(package_dir, script_body))

    script_name = _node_app_script_name(scripts)
    script_body = scripts.get(script_name) if script_name else None
    if isinstance(script_body, str):
        match = re.search(r"\b(?:node|tsx|ts-node|nest\s+start)\s+([^\s;&|]+)", script_body)
        if match:
            candidates.extend(_resolve_node_entrypoint_token(package_dir, match.group(1)))
    candidates.extend(
        [
            package_dir / "src" / "main.ts",
            package_dir / "src" / "main.js",
            package_dir / "src" / "server.ts",
            package_dir / "src" / "server.js",
            package_dir / "src" / "app.ts",
            package_dir / "src" / "app.js",
            package_dir / "server.ts",
            package_dir / "server.js",
            package_dir / "app.ts",
            package_dir / "app.js",
            package_dir / "index.ts",
            package_dir / "index.js",
        ]
    )
    if script_name:
        main_value = _string_value(data.get("main"))
        if main_value:
            candidates.extend(_resolve_node_entrypoint_token(package_dir, main_value))
    return _dedupe_paths(candidates)


def _node_script_entrypoint_candidates(package_dir: Path, script_body: str) -> list[Path]:
    candidates: list[Path] = []
    for token in re.findall(
        r"(?<![\w@])(?:\.{0,2}/)?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:ts|tsx|js|mjs|cjs)\b",
        script_body,
    ):
        cleaned = token.strip("'\"")
        normalized = cleaned.replace("\\", "/")
        basename = Path(normalized).name.lower()
        if "/" not in normalized and basename not in {
            "app.js",
            "app.ts",
            "index.js",
            "index.ts",
            "main.js",
            "main.ts",
            "server.js",
            "server.ts",
        }:
            continue
        candidates.extend(_resolve_node_entrypoint_token(package_dir, cleaned))
    return candidates


def _resolve_node_entrypoint_token(package_dir: Path, token: str) -> list[Path]:
    cleaned = token.strip().strip("'\"")
    if not cleaned or cleaned.startswith("-"):
        return []
    path = Path(cleaned.replace("\\", "/"))
    if path.is_absolute():
        base = path
    else:
        base = package_dir / path
    if base.suffix:
        return [*_node_source_entrypoint_candidates(package_dir, base), base]
    return [
        *[base.with_suffix(suffix) for suffix in (".ts", ".tsx", ".js", ".mjs", ".cjs")],
        *[base / f"index{suffix}" for suffix in (".ts", ".tsx", ".js", ".mjs", ".cjs")],
    ]


def _node_source_entrypoint_candidates(package_dir: Path, built_path: Path) -> list[Path]:
    try:
        relative = built_path.relative_to(package_dir)
    except ValueError:
        return []
    parts = relative.parts
    if not parts or parts[0] not in {"dist", "build", "out"}:
        return []
    source_relative = Path(*parts[1:]) if len(parts) > 1 else Path("")
    if not source_relative or source_relative.name == "":
        return []
    base = package_dir / source_relative
    if base.suffix.lower() in {".js", ".mjs", ".cjs"}:
        return [base.with_suffix(suffix) for suffix in (".ts", ".tsx", ".js", ".mjs", ".cjs")]
    return [base]


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = path.as_posix()
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def _redwood_entrypoints(root: Path) -> list[EntrypointFact]:
    if not _looks_like_redwood_project(root):
        return []
    command = f"{_redwood_command_prefix(root)} dev"
    entrypoints: list[EntrypointFact] = []
    for relative, kind in (
        ("web/src/App.js", "redwood-web-app"),
        ("web/src/App.tsx", "redwood-web-app"),
        ("web/src/App.jsx", "redwood-web-app"),
        ("api/src/functions/graphql.js", "redwood-graphql-function"),
        ("api/src/functions/graphql.ts", "redwood-graphql-function"),
    ):
        if (root / relative).exists():
            entrypoints.append(_entrypoint(relative, kind, command, relative))
    if not entrypoints and (root / "redwood.toml").exists():
        entrypoints.append(_entrypoint("redwood.toml", "redwood-project", command, "redwood.toml"))
    return entrypoints


def _redwood_project_commands(root: Path) -> list[CommandFact]:
    if not _looks_like_redwood_project(root):
        return []
    evidence = "redwood.toml" if (root / "redwood.toml").exists() else "package.json"
    redwood = _redwood_command_prefix(root)
    commands = [
        _command(evidence, f"{redwood} dev", "Run Redwood development server", ["dev"], []),
        _command(evidence, f"{redwood} test", "Run Redwood test suite", ["test"], []),
        _command(evidence, f"{redwood} build", "Build Redwood application", ["build"], []),
        _command(evidence, f"{redwood} prisma migrate dev", "Run Redwood Prisma migrations", ["prisma", "migrate", "dev"], []),
    ]
    if (root / "scripts" / "seed.js").exists() or _redwood_package_seed_script(root):
        commands.append(_command(evidence, f"{redwood} prisma db seed", "Seed Redwood Prisma database", ["prisma", "db", "seed"], []))
    return commands


def _looks_like_redwood_project(root: Path) -> bool:
    if (root / "redwood.toml").exists():
        return True
    package_json = root / "package.json"
    if not package_json.exists():
        return False
    data = _read_json_manifest(package_json)
    return isinstance(data, dict) and _package_has_dependency(data, "@redwoodjs/core")


def _redwood_package_seed_script(root: Path) -> bool:
    package_json = root / "package.json"
    if not package_json.exists():
        return False
    data = _read_json_manifest(package_json)
    if not isinstance(data, dict):
        return False
    prisma = data.get("prisma")
    return isinstance(prisma, dict) and isinstance(prisma.get("seed"), str)


def _redwood_command_prefix(root: Path) -> str:
    if (root / "yarn.lock").exists():
        return "yarn redwood"
    return "npx redwood"


def _node_package_script_commands(root: Path) -> list[CommandFact]:
    commands: list[CommandFact] = []
    package_manager = _node_package_manager(root)
    for package_json in _manifest_paths(root, "package.json"):
        data = _read_json_manifest(package_json)
        if not isinstance(data, dict):
            continue
        scripts = data.get("scripts", {})
        if not isinstance(scripts, dict):
            continue
        relative_manifest = package_json.relative_to(root).as_posix()
        package_dir = package_json.parent.relative_to(root).as_posix()
        for script_name, script_body in scripts.items():
            if not isinstance(script_body, str) or not script_body.strip():
                continue
            commands.append(
                _command(
                    relative_manifest,
                    _node_package_script_command(package_manager, package_dir, str(script_name)),
                    f"Run package script `{script_name}`",
                    [str(script_name)],
                    [f"script:{' '.join(script_body.split())[:180]}"],
                )
            )
    return commands


def _node_package_manager(root: Path) -> str:
    if (root / "bun.lock").exists() or (root / "bun.lockb").exists():
        return "bun"
    if (root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (root / "yarn.lock").exists():
        return "yarn"
    return "npm"


def _node_package_script_command(package_manager: str, package_dir: str, script_name: str) -> str:
    if package_dir in {"", "."}:
        return f"{package_manager} run {script_name}"
    if package_manager == "bun":
        return f"bun --cwd {package_dir} run {script_name}"
    if package_manager == "pnpm":
        return f"pnpm --dir {package_dir} run {script_name}"
    if package_manager == "yarn":
        return f"yarn --cwd {package_dir} run {script_name}"
    return f"npm --prefix {package_dir} run {script_name}"


def _streamlit_entrypoints(root: Path, files: list[FileFact]) -> list[EntrypointFact]:
    main_file = _streamlit_main_file(root, files)
    if not main_file:
        return []
    source = _read_manifest_text(root / main_file.path)
    line = _streamlit_signal_line(source)
    return [
        EntrypointFact(
            path=main_file.path,
            kind="streamlit-app",
            command=f"streamlit run {main_file.path}",
            evidence=Evidence(file=main_file.path, kind="entrypoint", line_start=line, line_end=line),
        )
    ]


def _streamlit_project_commands(root: Path, files: list[FileFact]) -> list[CommandFact]:
    main_file = _streamlit_main_file(root, files)
    commands: list[CommandFact] = []
    if main_file:
        commands.append(
            _command(
                main_file.path,
                f"streamlit run {main_file.path}",
                "Run Streamlit app",
                ["run", main_file.path],
                [],
            )
        )
    has_python_tests = any(file.language == "python" and file.role == "test" for file in files)
    if main_file and (_project_uses_pytest(root) or has_python_tests):
        commands.append(
            _command(
                _python_test_command_source(root, main_file.path),
                "pytest",
                "Run pytest suite",
                [],
                [],
            )
        )
    return commands


def _gradio_entrypoints(root: Path, files: list[FileFact]) -> list[EntrypointFact]:
    main_file = _gradio_main_file(root, files)
    if not main_file:
        return []
    source = _read_manifest_text(root / main_file.path)
    line = _gradio_signal_line(source)
    return [
        EntrypointFact(
            path=main_file.path,
            kind="gradio-app",
            command=f"python {main_file.path}",
            evidence=Evidence(file=main_file.path, kind="entrypoint", line_start=line, line_end=line),
        )
    ]


def _gradio_project_commands(root: Path, files: list[FileFact]) -> list[CommandFact]:
    main_file = _gradio_main_file(root, files)
    commands: list[CommandFact] = []
    if main_file:
        commands.extend(
            [
                _command(
                    main_file.path,
                    f"python {main_file.path}",
                    "Run Gradio app",
                    [main_file.path],
                    [],
                ),
                _command(
                    main_file.path,
                    f"gradio {main_file.path}",
                    "Run Gradio app with reload",
                    [main_file.path],
                    [],
                ),
            ]
        )
    has_python_tests = any(file.language == "python" and file.role == "test" for file in files)
    if main_file and (_project_uses_pytest(root) or has_python_tests):
        commands.append(
            _command(
                _python_test_command_source(root, main_file.path),
                "pytest",
                "Run pytest suite",
                [],
                [],
            )
        )
    return commands


def _dash_entrypoints(root: Path, files: list[FileFact]) -> list[EntrypointFact]:
    main_file = _dash_main_file(root, files)
    if not main_file:
        return []
    source = _read_manifest_text(root / main_file.path)
    line = _dash_signal_line(source)
    return [
        EntrypointFact(
            path=main_file.path,
            kind="dash-app",
            command=f"python {main_file.path}",
            evidence=Evidence(file=main_file.path, kind="entrypoint", line_start=line, line_end=line),
        )
    ]


def _dash_project_commands(root: Path, files: list[FileFact]) -> list[CommandFact]:
    main_file = _dash_main_file(root, files)
    commands: list[CommandFact] = []
    if main_file:
        commands.append(
            _command(
                main_file.path,
                f"python {main_file.path}",
                "Run Dash app",
                [main_file.path],
                [],
            )
        )
    has_python_tests = any(file.language == "python" and file.role == "test" for file in files)
    if main_file and (_project_uses_pytest(root) or has_python_tests):
        commands.append(
            _command(
                _python_test_command_source(root, main_file.path),
                "pytest",
                "Run pytest suite",
                [],
                [],
            )
        )
    return commands


def _streamlit_main_file(root: Path, files: list[FileFact]) -> FileFact | None:
    candidates: list[tuple[tuple[int, str], FileFact]] = []
    for file_fact in files:
        if file_fact.language != "python" or file_fact.role in {"test", "sample", "generated", "documentation"}:
            continue
        if not _looks_like_streamlit_file(root, file_fact):
            continue
        candidates.append((_streamlit_main_score(file_fact.path), file_fact))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[0])[0][1]


def _gradio_main_file(root: Path, files: list[FileFact]) -> FileFact | None:
    candidates: list[tuple[tuple[int, str], FileFact]] = []
    for file_fact in files:
        if file_fact.language != "python" or file_fact.role in {"test", "sample", "generated", "documentation"}:
            continue
        if not _looks_like_gradio_file(root, file_fact):
            continue
        candidates.append((_gradio_main_score(file_fact.path), file_fact))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[0])[0][1]


def _dash_main_file(root: Path, files: list[FileFact]) -> FileFact | None:
    candidates: list[tuple[tuple[int, str], FileFact]] = []
    for file_fact in files:
        if file_fact.language != "python" or file_fact.role in {"test", "sample", "generated", "documentation"}:
            continue
        if not _looks_like_dash_file(root, file_fact):
            continue
        candidates.append((_dash_main_score(file_fact.path), file_fact))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[0])[0][1]


def _streamlit_main_score(path: str) -> tuple[int, str]:
    normalized = path.replace("\\", "/")
    lower = normalized.lower()
    name = Path(lower).name
    page_penalty = 20 if "/pages/" in f"/{lower}" or lower.startswith("pages/") else 0
    cleaned_name = re.sub(r"^\d+[_\-\s]+", "", name)
    priority = {
        "streamlit_app.py": 0,
        "app.py": 1,
        "home.py": 2,
        "homepage.py": 2,
        "main.py": 3,
    }.get(cleaned_name, 8)
    depth_penalty = lower.count("/")
    return (page_penalty + priority + depth_penalty, lower)


def _gradio_main_score(path: str) -> tuple[int, str]:
    normalized = path.replace("\\", "/")
    lower = normalized.lower()
    name = Path(lower).name
    priority = {
        "app.py": 0,
        "gradio_app.py": 1,
        "demo.py": 2,
        "main.py": 3,
        "run.py": 4,
    }.get(name, 8)
    launch_bonus = 0 if lower.count("/") == 0 else 2
    return (priority + launch_bonus + lower.count("/"), lower)


def _dash_main_score(path: str) -> tuple[int, str]:
    normalized = path.replace("\\", "/")
    lower = normalized.lower()
    name = Path(lower).name
    priority = {
        "app.py": 0,
        "dash_app.py": 1,
        "dashboard.py": 2,
        "main.py": 3,
        "usage.py": 4,
        "run.py": 5,
    }.get(name, 8)
    return (priority + lower.count("/"), lower)


def _looks_like_streamlit_file(root: Path, file_fact: FileFact) -> bool:
    source = _read_manifest_text(root / file_fact.path)
    return _looks_like_streamlit_source(source)


def _looks_like_gradio_file(root: Path, file_fact: FileFact) -> bool:
    source = _read_manifest_text(root / file_fact.path)
    return _looks_like_gradio_source(source)


def _looks_like_dash_file(root: Path, file_fact: FileFact) -> bool:
    source = _read_manifest_text(root / file_fact.path)
    return _looks_like_dash_source(source)


def _looks_like_streamlit_source(source: str) -> bool:
    return bool(
        re.search(r"^\s*(?:import\s+streamlit\b|from\s+streamlit\s+import\b)", source, re.MULTILINE)
        or re.search(r"\bstreamlit\.", source)
        or re.search(
            r"\bst\."
            r"(?:set_page_config|title|header|write|markdown|sidebar|session_state|"
            r"text_input|button|chat_input)\b",
            source,
        )
    )


def _looks_like_gradio_source(source: str) -> bool:
    return bool(
        re.search(r"\bgr\.(?:Interface|Blocks|ChatInterface|TabbedInterface|load)\b", source)
        or re.search(
            r"\bgradio\.(?:Interface|Blocks|ChatInterface|TabbedInterface|load)\b",
            source,
        )
    )


def _looks_like_dash_source(source: str) -> bool:
    return bool(
        re.search(r"\b(?:dash\.)?Dash\s*\(", source)
        or re.search(r"\bapp\.layout\s*=", source)
        or re.search(r"@\s*app\.callback\s*\(", source)
    )


def _streamlit_signal_line(source: str) -> int:
    match = re.search(
        r"^\s*(?:import\s+streamlit\b|from\s+streamlit\s+import\b)|"
        r"\bst\.(?:set_page_config|title|header|write)\b|\bstreamlit\.",
        source,
        re.MULTILINE,
    )
    return _line_for_offset(source, match.start()) if match else 1


def _gradio_signal_line(source: str) -> int:
    match = re.search(
        r"^\s*(?:import\s+gradio\b|from\s+gradio\s+import\b)|"
        r"\bgr\.(?:Interface|Blocks|ChatInterface|TabbedInterface|load)\b|\bgradio\.",
        source,
        re.MULTILINE,
    )
    return _line_for_offset(source, match.start()) if match else 1


def _dash_signal_line(source: str) -> int:
    match = re.search(
        r"\b(?:dash\.)?Dash\s*\(|\bapp\.layout\s*=|@\s*app\.callback\s*\(",
        source,
        re.MULTILINE,
    )
    return _line_for_offset(source, match.start()) if match else 1


def _python_test_command_source(root: Path, fallback: str) -> str:
    for path in ("pyproject.toml", "pytest.ini", "requirements-dev.txt", "requirements.txt", "setup.cfg"):
        if (root / path).exists():
            return path
    return fallback


def _django_entrypoints(root: Path) -> list[EntrypointFact]:
    entrypoints: list[EntrypointFact] = []
    manage_py = root / "manage.py"
    if _looks_like_django_manage_py(manage_py):
        entrypoints.append(_entrypoint("manage.py", "django-manage", "python manage.py runserver", "manage.py"))

    for path in _python_runtime_candidates(root, {"asgi.py", "wsgi.py", "celery.py", "celeryconf.py"}):
        source = _read_manifest_text(path)
        relative = path.relative_to(root).as_posix()
        module = _python_module_path(root, path)
        if path.name == "wsgi.py" and "application" in source and "get_wsgi_application" in source:
            entrypoints.append(_entrypoint(relative, "django-wsgi", f"gunicorn {module}:application", relative))
        elif path.name in {"asgi.py", "__init__.py"} and "application" in source and "get_asgi_application" in source:
            entrypoints.append(_entrypoint(relative, "django-asgi", f"uvicorn {module}:application", relative))
        elif path.name in {"celery.py", "celeryconf.py"} and "Celery(" in source:
            target = f"{module}:app" if re.search(r"^\s*app\s*=\s*Celery\(", source, re.MULTILINE) else module
            entrypoints.append(_entrypoint(relative, "celery-app", f"celery -A {target} worker -l info", relative))
    return entrypoints


def _django_project_commands(root: Path) -> list[CommandFact]:
    if not _looks_like_django_manage_py(root / "manage.py"):
        return []
    commands = [
        _command("manage.py", "python manage.py runserver", "Run Django development server", [], []),
        _command("manage.py", "python manage.py migrate", "Apply Django database migrations", [], []),
    ]
    if _project_uses_pytest(root):
        commands.append(_command("pyproject.toml" if (root / "pyproject.toml").exists() else "manage.py", "pytest", "Run pytest suite", [], []))
    else:
        commands.append(_command("manage.py", "python manage.py test", "Run Django test suite", [], []))

    for path in _python_runtime_candidates(root, {"celery.py", "celeryconf.py"}):
        source = _read_manifest_text(path)
        if "Celery(" not in source:
            continue
        relative = path.relative_to(root).as_posix()
        module = _python_module_path(root, path)
        target = f"{module}:app" if re.search(r"^\s*app\s*=\s*Celery\(", source, re.MULTILINE) else module
        commands.append(_command(relative, f"celery -A {target} worker -l info", "Run Celery worker", [], []))
    return commands


def _looks_like_django_manage_py(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    source = _read_manifest_text(path)
    return "DJANGO_SETTINGS_MODULE" in source and "django.core.management" in source


def _project_uses_pytest(root: Path) -> bool:
    for manifest in ("pyproject.toml", "requirements.txt", "requirements-dev.txt", "setup.cfg"):
        path = root / manifest
        if path.exists() and re.search(r"\bpytest(?:[-\w]*)?\b", _read_manifest_text(path), re.IGNORECASE):
            return True
    return (root / "pytest.ini").exists() or (root / "conftest.py").exists()


def _python_runtime_candidates(root: Path, names: set[str]) -> list[Path]:
    candidates: list[Path] = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root)
        relative_text = relative.as_posix()
        if (
            any(part in IGNORED_DIRS for part in relative.parts)
            or is_generated_path(relative_text)
            or is_test_path(relative_text)
            or is_sample_path(relative_text)
        ):
            continue
        if path.name in names or relative_text.endswith("asgi/__init__.py"):
            candidates.append(path)
    return candidates


def _python_module_path(root: Path, path: Path) -> str:
    relative = path.relative_to(root)
    parts = list(relative.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _composer_script_commands(root: Path) -> list[CommandFact]:
    commands: list[CommandFact] = []
    for composer_json in _manifest_paths(root, "composer.json"):
        data = _read_json_manifest(composer_json)
        if not isinstance(data, dict):
            continue
        scripts = data.get("scripts", {})
        if not isinstance(scripts, dict):
            continue
        relative_manifest = composer_json.relative_to(root).as_posix()
        for script_name, script_body in scripts.items():
            details = _composer_script_details(script_body)
            if not details:
                continue
            commands.append(
                _command(
                    relative_manifest,
                    f"composer run {script_name}",
                    f"Run Composer script `{script_name}`",
                    [str(script_name)],
                    details,
                )
            )
    return commands


def _composer_script_details(script_body: object) -> list[str]:
    values: list[str] = []
    if isinstance(script_body, str):
        values.append(script_body)
    elif isinstance(script_body, list):
        values.extend(item for item in script_body if isinstance(item, str))
    elif isinstance(script_body, dict):
        for key, value in script_body.items():
            if isinstance(value, str):
                values.append(f"{key}:{value}")
            elif isinstance(value, list):
                values.extend(f"{key}:{item}" for item in value if isinstance(item, str))
    return [f"script:{' '.join(value.split())[:180]}" for value in values if value.strip()]


def _symfony_entrypoints(root: Path) -> list[EntrypointFact]:
    if not _looks_like_symfony_project(root):
        return []
    entrypoints: list[EntrypointFact] = []
    if (root / "public" / "index.php").exists():
        entrypoints.append(
            _entrypoint(
                "public/index.php",
                "symfony-front-controller",
                "symfony server:start",
                "public/index.php",
            )
        )
    if (root / "bin" / "console").exists():
        entrypoints.append(_entrypoint("bin/console", "symfony-console", "php bin/console", "bin/console"))
    return entrypoints


def _symfony_project_commands(root: Path) -> list[CommandFact]:
    if not _looks_like_symfony_project(root):
        return []
    evidence = "bin/console" if (root / "bin" / "console").exists() else "composer.json"
    commands: list[CommandFact] = []
    if (root / "public" / "index.php").exists():
        commands.append(_command("public/index.php", "symfony server:start", "Run Symfony local web server", [], []))
        commands.append(
            _command(
                "public/index.php",
                "php -S localhost:8000 -t public public/index.php",
                "Run Symfony through PHP built-in server",
                [],
                [],
            )
        )
    if (root / "bin" / "console").exists():
        commands.append(_command(evidence, "php bin/console", "Run Symfony console", [], []))
        commands.append(_command(evidence, "php bin/console debug:router", "List Symfony routes", ["debug:router"], []))
        if (root / "migrations").exists() or _composer_has_package(root, "doctrine/doctrine-migrations-bundle"):
            commands.append(
                _command(
                    evidence,
                    "php bin/console doctrine:migrations:migrate",
                    "Run Doctrine migrations",
                    ["doctrine:migrations:migrate"],
                    [],
                )
            )
        if (root / "src" / "DataFixtures").exists() or _composer_has_package(root, "doctrine/doctrine-fixtures-bundle"):
            commands.append(
                _command(
                    evidence,
                    "php bin/console doctrine:fixtures:load",
                    "Load Doctrine fixtures",
                    ["doctrine:fixtures:load"],
                    [],
                )
            )
    if (root / "phpunit.xml").exists() or (root / "phpunit.xml.dist").exists() or (root / "phpunit.dist.xml").exists():
        commands.append(_command("composer.json", "vendor/bin/phpunit", "Run PHPUnit test suite", [], []))
    return commands


def _looks_like_symfony_project(root: Path) -> bool:
    composer = root / "composer.json"
    if composer.exists() and _composer_has_package(root, "symfony/framework-bundle"):
        return True
    return (root / "bin" / "console").exists() and (root / "config" / "bundles.php").exists()


def _composer_has_package(root: Path, package_name: str) -> bool:
    composer = root / "composer.json"
    if not composer.exists():
        return False
    data = _read_json_manifest(composer)
    if not isinstance(data, dict):
        return False
    for section in ("require", "require-dev"):
        packages = data.get(section, {})
        if isinstance(packages, dict) and package_name in packages:
            return True
    return False


def _wordpress_cli_commands(root: Path, files: list[FileFact]) -> list[CommandFact]:
    commands: list[CommandFact] = []
    for file_fact in files:
        if file_fact.language != "php" or file_fact.role in {"test", "sample", "generated", "documentation"}:
            continue
        path = root / file_fact.path
        if not path.exists():
            continue
        source = _read_manifest_text(path)
        for match in re.finditer(
            r"\bWP_CLI::add_command\(\s*['\"](?P<name>[^'\"]+)['\"]\s*,\s*(?P<handler>[^)\n;]+)",
            source,
            re.IGNORECASE,
        ):
            name = " ".join(match.group("name").split())
            if not name:
                continue
            handler = " ".join(match.group("handler").strip().strip(",").strip("'\"").split())
            line = _line_for_offset(source, match.start())
            commands.append(
                CommandFact(
                    path=file_fact.path,
                    name=f"wp {name}",
                    description=f"Run WordPress CLI command `{name}`",
                    arguments=name.split(),
                    options=[f"handler:{handler}"] if handler else [],
                    evidence=Evidence(file=file_fact.path, kind="command", line_start=line, line_end=line),
                )
            )
    return commands


def _laravel_entrypoints(root: Path) -> list[EntrypointFact]:
    if not _looks_like_laravel_project(root):
        return []
    entrypoints: list[EntrypointFact] = []
    if (root / "artisan").exists():
        entrypoints.append(_entrypoint("artisan", "laravel-artisan", "php artisan", "artisan"))
    if (root / "public" / "index.php").exists():
        entrypoints.append(
            _entrypoint(
                "public/index.php",
                "laravel-http-front-controller",
                "php artisan serve",
                "public/index.php",
            )
        )
    return entrypoints


def _laravel_project_commands(root: Path) -> list[CommandFact]:
    if not _looks_like_laravel_project(root):
        return []
    evidence = "artisan" if (root / "artisan").exists() else "composer.json"
    commands = [
        _command(evidence, "php artisan serve", "Run Laravel development server", [], []),
        _command(evidence, "php artisan route:list", "List Laravel routes", [], []),
    ]
    if (root / "database" / "migrations").exists():
        commands.append(_command(evidence, "php artisan migrate", "Run Laravel migrations", [], []))
    if (root / "tests").exists():
        commands.append(_command(evidence, "php artisan test", "Run Laravel test suite", [], []))
    return commands


def _looks_like_laravel_project(root: Path) -> bool:
    composer = root / "composer.json"
    if composer.exists():
        data = _read_json_manifest(composer)
        if isinstance(data, dict):
            packages: dict[str, object] = {}
            for section in ("require", "require-dev"):
                values = data.get(section, {})
                if isinstance(values, dict):
                    packages.update(values)
            if "laravel/framework" in packages:
                return True
    return (root / "artisan").exists() and ((root / "bootstrap" / "app.php").exists() or (root / "routes").exists())


def _slim_entrypoints(root: Path) -> list[EntrypointFact]:
    if not _looks_like_slim_project(root):
        return []
    command = _slim_start_command(root)
    if (root / "public" / "index.php").exists():
        return [_entrypoint("public/index.php", "slim-front-controller", command, "public/index.php")]
    return [_entrypoint("composer.json", "slim-app", command, "composer.json")]


def _slim_project_commands(root: Path) -> list[CommandFact]:
    if not _looks_like_slim_project(root):
        return []
    evidence = "composer.json" if (root / "composer.json").exists() else "public/index.php"
    commands: list[CommandFact] = []
    if not _composer_has_script(root, "start"):
        commands.append(_command(evidence, _slim_start_command(root), "Run Slim application", [], []))
    if (root / "vendor" / "bin" / "phpunit").exists() or (root / "phpunit.xml").exists() or (root / "phpunit.xml.dist").exists():
        commands.append(_command(evidence, "vendor/bin/phpunit", "Run PHPUnit tests", [], []))
    if (root / "phinx.php").exists():
        commands.append(_command("phinx.php", "vendor/bin/phinx migrate", "Run Phinx migrations", ["migrate"], []))
    return commands


def _looks_like_slim_project(root: Path) -> bool:
    composer = root / "composer.json"
    if composer.exists():
        data = _read_json_manifest(composer)
        if isinstance(data, dict):
            packages: dict[str, object] = {}
            for section in ("require", "require-dev"):
                values = data.get(section, {})
                if isinstance(values, dict):
                    packages.update(values)
            if any(str(name) == "slim/slim" or str(name).startswith("slim/") for name in packages):
                return True
    index = root / "public" / "index.php"
    if index.exists():
        source = _read_manifest_text(index).lower()
        return "slim\\app" in source or "appfactory" in source
    return False


def _slim_start_command(root: Path) -> str:
    composer = root / "composer.json"
    if composer.exists():
        data = _read_json_manifest(composer)
        if isinstance(data, dict):
            scripts = data.get("scripts", {})
            if isinstance(scripts, dict) and isinstance(scripts.get("start"), str):
                return "composer run start"
    if (root / "public" / "index.php").exists():
        return "php -S localhost:8080 -t public public/index.php"
    return "php -S localhost:8080"


def _composer_has_script(root: Path, script_name: str) -> bool:
    composer = root / "composer.json"
    if not composer.exists():
        return False
    data = _read_json_manifest(composer)
    if not isinstance(data, dict):
        return False
    scripts = data.get("scripts", {})
    return isinstance(scripts, dict) and isinstance(scripts.get(script_name), str)


def _sinatra_entrypoints(root: Path) -> list[EntrypointFact]:
    if not _looks_like_sinatra_project(root):
        return []
    command = _sinatra_start_command(root)
    if (root / "config.ru").exists():
        return [_entrypoint("config.ru", "sinatra-rack-app", command, "config.ru")]
    for name in ("app.rb", "server.rb", "main.rb"):
        if (root / name).exists():
            return [_entrypoint(name, "sinatra-app", command, name)]
    return [_entrypoint("Gemfile", "sinatra-app", command, "Gemfile")]


def _sinatra_project_commands(root: Path) -> list[CommandFact]:
    if not _looks_like_sinatra_project(root):
        return []
    evidence = "config.ru" if (root / "config.ru").exists() else "Gemfile"
    commands = [_command(evidence, _sinatra_start_command(root), "Run Sinatra application", [], [])]
    if (root / "Rakefile").exists():
        commands.append(_command("Rakefile", "bundle exec rake", "Run Rake tasks", [], []))
    if (root / "db" / "migrate").exists() or _gemfile_has_gem(root, "sinatra-activerecord"):
        commands.append(_command("Rakefile" if (root / "Rakefile").exists() else evidence, "bundle exec rake db:migrate", "Run ActiveRecord migrations", ["db:migrate"], []))
    if (root / "spec").exists() or (root / "test").exists():
        commands.append(_command(evidence, "bundle exec rake test", "Run Ruby tests", [], []))
    return commands


def _looks_like_sinatra_project(root: Path) -> bool:
    if _gemfile_has_gem(root, "sinatra"):
        return True
    config_ru = root / "config.ru"
    if config_ru.exists() and "sinatra" in _read_manifest_text(config_ru).lower():
        return True
    for name in ("app.rb", "server.rb", "main.rb"):
        path = root / name
        if path.exists() and _looks_like_sinatra_ruby_source(_read_manifest_text(path)):
            return True
    return False


def _sinatra_start_command(root: Path) -> str:
    procfile_command = _procfile_web_command(root)
    if procfile_command:
        return procfile_command
    if (root / "config.ru").exists():
        return "bundle exec rackup"
    for name in ("app.rb", "server.rb", "main.rb"):
        if (root / name).exists():
            return f"bundle exec ruby {name}"
    return "bundle exec ruby app.rb"


def _procfile_web_command(root: Path) -> str | None:
    procfile = root / "Procfile"
    if not procfile.exists():
        return None
    for line in _read_manifest_text(procfile).splitlines():
        match = re.match(r"\s*web\s*:\s*(?P<command>.+?)\s*$", line)
        if match:
            return match.group("command").strip()
    return None


def _gemfile_has_gem(root: Path, gem_name: str) -> bool:
    gemfile = root / "Gemfile"
    if not gemfile.exists():
        return False
    pattern = rf"^\s*gem\s+['\"]{re.escape(gem_name)}['\"]"
    return re.search(pattern, _read_manifest_text(gemfile), re.MULTILINE) is not None


def _looks_like_sinatra_ruby_source(source: str) -> bool:
    lower = source.lower()
    if "grape::api" in lower:
        return False
    return (
        "require 'sinatra" in lower
        or 'require "sinatra' in lower
        or "sinatra::base" in lower
        or "sinatra::application" in lower
        or re.search(r"(?m)^\s*(?:get|post|put|patch|delete|options|head)\s+['\"]/", source) is not None
    )


def _grape_entrypoints(root: Path) -> list[EntrypointFact]:
    if not _looks_like_grape_project(root):
        return []
    if (root / "config.ru").exists():
        return [_entrypoint("config.ru", "grape-rack-app", "bundle exec rackup", "config.ru")]
    for path in _grape_api_files(root):
        relative = path.relative_to(root).as_posix()
        return [_entrypoint(relative, "grape-api", "bundle exec rackup", relative)]
    return []


def _grape_project_commands(root: Path) -> list[CommandFact]:
    if not _looks_like_grape_project(root):
        return []
    evidence = "config.ru" if (root / "config.ru").exists() else "Gemfile"
    commands = [_command(evidence, "bundle exec rackup", "Run Grape Rack application", [], [])]
    if (root / "spec").exists() or _gemfile_has_gem(root, "rspec"):
        commands.append(_command(evidence, "bundle exec rspec", "Run RSpec test suite", [], []))
    if (root / "Rakefile").exists():
        commands.append(_command("Rakefile", "bundle exec rake", "Run Rake tasks", [], []))
    return commands


def _looks_like_grape_project(root: Path) -> bool:
    if _gemfile_has_gem(root, "grape"):
        return True
    config_ru = root / "config.ru"
    if config_ru.exists() and "grape" in _read_manifest_text(config_ru).lower():
        return True
    return bool(_grape_api_files(root))


def _grape_api_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*.rb")):
        relative = path.relative_to(root).as_posix()
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts) or is_test_path(relative) or is_sample_path(relative):
            continue
        source = _read_manifest_text(path)
        if "Grape::API" in source:
            files.append(path)
    return files


def _yii_entrypoints(root: Path) -> list[EntrypointFact]:
    if not _looks_like_yii_project(root):
        return []
    entrypoints: list[EntrypointFact] = []
    if (root / "web" / "index.php").exists():
        entrypoints.append(
            _entrypoint(
                "web/index.php",
                "yii-web-front-controller",
                "php -S localhost:8000 -t web",
                "web/index.php",
            )
        )
    if (root / "yii").exists():
        entrypoints.append(_entrypoint("yii", "yii-console", "php yii", "yii"))
    return entrypoints


def _yii_project_commands(root: Path) -> list[CommandFact]:
    if not _looks_like_yii_project(root):
        return []
    evidence = "yii" if (root / "yii").exists() else "composer.json"
    commands = [
        _command(evidence, "php yii", "Run Yii console entrypoint", [], []),
        _command(evidence, "php yii migrate", "Run Yii database migrations", ["migrate"], []),
    ]
    if (root / "tests").exists():
        commands.append(_command("codeception.yml" if (root / "codeception.yml").exists() else evidence, "vendor/bin/codecept run", "Run Codeception tests", ["run"], []))
    for path in _yii_console_controller_paths(root):
        relative = path.relative_to(root).as_posix()
        source = _read_manifest_text(path)
        command_name = _yii_console_command_name(relative)
        if not command_name:
            continue
        for action in re.findall(r"\bpublic\s+function\s+action([A-Z][A-Za-z0-9_]*)\s*\(", source):
            action_name = _camel_to_kebab(action)
            name = f"php yii {command_name}" if action_name == "index" else f"php yii {command_name}/{action_name}"
            commands.append(_command(relative, name, "Run Yii console controller action", [command_name, action_name], []))
    return commands


def _looks_like_yii_project(root: Path) -> bool:
    composer = root / "composer.json"
    if composer.exists():
        data = _read_json_manifest(composer)
        if isinstance(data, dict):
            packages: dict[str, object] = {}
            for section in ("require", "require-dev"):
                values = data.get(section, {})
                if isinstance(values, dict):
                    packages.update(values)
            if any(str(name) == "yiisoft/yii2" or str(name).startswith("yiisoft/yii2-") for name in packages):
                return True
    return (root / "yii").exists() and (root / "config").exists() and (root / "web" / "index.php").exists()


def _yii_console_controller_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    for path in sorted(root.rglob("*Controller.php")):
        relative = path.relative_to(root).as_posix()
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts) or is_test_path(relative):
            continue
        if "/commands/" in f"/{relative}" or relative.startswith("commands/"):
            paths.append(path)
    return paths


def _yii_console_command_name(relative: str) -> str | None:
    normalized = relative.replace("\\", "/")
    if not normalized.endswith("Controller.php"):
        return None
    stem = Path(normalized).name.removesuffix("Controller.php")
    command = _camel_to_kebab(stem)
    match = re.search(r"(?:^|/)modules/([^/]+)/commands/", normalized)
    if match:
        return f"{match.group(1)}/{command}"
    return command


def _camel_to_kebab(value: str) -> str:
    return re.sub(r"(?<!^)([A-Z])", r"-\1", value).replace("_", "-").lower()


def _looks_like_clojure_project(root: Path) -> bool:
    return (root / "deps.edn").exists() or (root / "project.clj").exists()


def _clojure_main_namespace(root: Path) -> str | None:
    for source_root in ("src", "source"):
        directory = root / source_root
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*.clj")):
            if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
                continue
            source = _read_manifest_text(path)
            if "(:gen-class)" in source and re.search(r"\(defn\s+-main\b", source):
                return _clojure_namespace_from_source(source)
    return None


def _clojure_namespace_from_source(source: str) -> str | None:
    match = re.search(r"\(ns\s+(?:\^[^\s()]+\s+|\^\{[\s\S]{0,300}?\}\s+)*(?P<namespace>[A-Za-z0-9_.-]+)", source)
    return match.group("namespace") if match else None


def _rails_entrypoints(root: Path) -> list[EntrypointFact]:
    if not _looks_like_rails_project(root):
        return []
    entrypoints: list[EntrypointFact] = []
    if (root / "bin" / "rails").exists():
        entrypoints.append(_entrypoint("bin/rails", "rails-app", "bundle exec rails server", "bin/rails"))
    if (root / "config.ru").exists():
        entrypoints.append(_entrypoint("config.ru", "rack-app", "bundle exec rackup", "config.ru"))
    if not entrypoints and (root / "Gemfile").exists():
        entrypoints.append(_entrypoint("Gemfile", "rails-app", "bundle exec rails server", "Gemfile"))
    return entrypoints


def _rails_project_commands(root: Path) -> list[CommandFact]:
    if not _looks_like_rails_project(root):
        return []
    evidence = "bin/rails" if (root / "bin" / "rails").exists() else "Gemfile"
    commands = [
        _command(evidence, "bundle exec rails server", "Run Rails application server", [], []),
        _command(evidence, "bundle exec rails test", "Run Rails test suite", [], []),
        _command(evidence, "bundle exec rails db:migrate", "Run Rails database migrations", [], []),
    ]
    if (root / "Rakefile").exists():
        commands.append(_command("Rakefile", "bundle exec rake", "Run Rake tasks", [], []))
    return commands


def _gradle_entrypoints(root: Path) -> list[EntrypointFact]:
    entrypoints: list[EntrypointFact] = []
    entrypoints.extend(_ktor_gradle_entrypoints(root))
    for module, build_file in _gradle_android_app_modules(root):
        manifest = Path(build_file).parent / "src" / "main" / "AndroidManifest.xml"
        manifest_path = manifest.as_posix()
        entrypoints.append(
            _entrypoint(
                manifest_path,
                "android-app",
                f"{_gradle_command(root)} {module}:installDebug",
                manifest_path,
            )
        )
    return entrypoints


def _mix_entrypoints(root: Path) -> list[EntrypointFact]:
    path = root / "mix.exs"
    if not path.exists():
        return []
    source = _read_manifest_text(path)
    if _looks_like_phoenix_mix_source(source):
        return [_entrypoint("mix.exs", "phoenix-app", _phoenix_mix_server_command(source), "mix.exs")]
    return [_entrypoint("mix.exs", "mix-project", "mix run", "mix.exs")]


def _mix_project_commands(root: Path) -> list[CommandFact]:
    path = root / "mix.exs"
    if not path.exists():
        return []
    source = _read_manifest_text(path)
    aliases = _mix_aliases(source)
    commands = [
        _command("mix.exs", "mix deps.get", "Resolve Mix dependencies", ["deps.get"], []),
        _command("mix.exs", "mix test", "Run Mix test suite", ["test"], _mix_alias_options(aliases.get("test", []))),
    ]
    if _looks_like_phoenix_mix_source(source):
        commands.append(
            _command("mix.exs", _phoenix_mix_server_command(source), "Run Phoenix development server", ["phx.server"], [])
        )
    if _looks_like_ecto_mix_source(source):
        commands.append(_command("mix.exs", "mix ecto.migrate", "Run Ecto database migrations", ["ecto.migrate"], []))
    for alias, steps in aliases.items():
        if alias == "test":
            continue
        commands.append(
            _command(
                "mix.exs",
                f"mix {alias}",
                f"Run Mix alias `{alias}`",
                [alias],
                _mix_alias_options(steps),
            )
        )
    return commands


def _mix_aliases(source: str) -> dict[str, list[str]]:
    aliases_match = re.search(r"\bdefp\s+aliases\s+do\s*\n\s*\[(?P<body>[\s\S]*?)\n\s*\]\s*\n\s*end", source)
    if not aliases_match:
        return {}
    aliases: dict[str, list[str]] = {}
    body = aliases_match.group("body")
    alias_re = re.compile(r"(?:['\"](?P<string>[^'\"]+)['\"]|(?P<atom>[A-Za-z_][\w.?!]*))\s*:\s*\[(?P<steps>[^\]]*)\]")
    for match in alias_re.finditer(body):
        name = match.group("string") or match.group("atom")
        steps = re.findall(r"['\"]([^'\"]+)['\"]", match.group("steps"))
        if name and steps:
            aliases[name] = [" ".join(step.split()) for step in steps]
    return aliases


def _mix_alias_options(steps: list[str]) -> list[str]:
    return [f"alias-step:{step}" for step in steps]


def _looks_like_phoenix_mix_source(source: str) -> bool:
    lowered = source.lower()
    return ":phoenix" in lowered or "phoenix_live_view" in lowered or "phoenix_html" in lowered


def _looks_like_ecto_mix_source(source: str) -> bool:
    lowered = source.lower()
    return ":ecto" in lowered or ":ecto_sql" in lowered or ":postgrex" in lowered or ":myxql" in lowered


def _phoenix_mix_server_command(source: str) -> str:
    return "mix phoenix.server" if re.search(r"\{\s*:phoenix\s*,\s*['\"]~>\s*1\.[012]\.", source) else "mix phx.server"


def _ktor_gradle_entrypoints(root: Path) -> list[EntrypointFact]:
    entrypoints: list[EntrypointFact] = []
    for build_file in _gradle_build_files(root):
        project_dir = root / Path(build_file).parent
        source = _read_manifest_text(root / build_file)
        if not _looks_like_ktor_gradle_build(source) and not _project_has_ktor_application_config(project_dir):
            continue
        evidence = _ktor_entrypoint_evidence(root, project_dir) or build_file
        entrypoints.append(_entrypoint(evidence, "ktor-app", f"{_gradle_command_for_dir(project_dir)} run", evidence))
    return entrypoints


def _gradle_project_commands(root: Path) -> list[CommandFact]:
    commands: list[CommandFact] = []
    if _looks_like_gradle_project(root):
        evidence = _gradle_root_evidence(root)
        gradle = _gradle_command(root)
        commands.extend(
            [
                _command(evidence, f"{gradle} build", "Build Gradle project", ["build"], []),
                _command(evidence, f"{gradle} test", "Run Gradle unit tests", ["test"], []),
            ]
        )
        if _has_android_project(root):
            commands.append(
                _command(evidence, f"{gradle} connectedCheck", "Run Android connected checks", ["connectedCheck"], [])
            )
    for module, build_file in _gradle_android_app_modules(root):
        gradle = _gradle_command(root)
        commands.append(
            _command(
                build_file,
                f"{gradle} {module}:assembleDebug",
                "Assemble Android debug APK",
                [f"{module}:assembleDebug"],
                [],
            )
        )
        commands.append(
            _command(
                build_file,
                f"{gradle} {module}:installDebug",
                "Install Android debug APK on a connected device",
                [f"{module}:installDebug"],
                [],
            )
        )
    for build_file in _gradle_build_files(root):
        project_dir = root / Path(build_file).parent
        if project_dir == root or not _looks_like_nested_gradle_project(project_dir):
            continue
        source = _read_manifest_text(root / build_file)
        gradle = _gradle_command_for_dir(project_dir)
        relative_dir = project_dir.relative_to(root).as_posix()
        options = [f"cwd:{relative_dir}"]
        commands.append(_command(build_file, f"{gradle} build", "Build nested Gradle project", ["build"], options))
        commands.append(_command(build_file, f"{gradle} test", "Run nested Gradle tests", ["test"], options))
        if _looks_like_ktor_gradle_build(source) or _project_has_ktor_application_config(project_dir):
            commands.append(_command(build_file, f"{gradle} run", "Run Ktor Gradle application", ["run"], options))
    return commands


def _looks_like_gradle_project(root: Path) -> bool:
    return any(
        (root / name).exists()
        for name in ("settings.gradle", "settings.gradle.kts", "build.gradle", "build.gradle.kts", "gradlew", "gradlew.bat")
    )


def _has_android_project(root: Path) -> bool:
    return any("android" in _read_manifest_text(root / path).lower() for path in _gradle_build_files(root))


def _gradle_command(root: Path) -> str:
    return "./gradlew" if (root / "gradlew").exists() or (root / "gradlew.bat").exists() else "gradle"


def _gradle_command_for_dir(project_dir: Path) -> str:
    return "./gradlew" if (project_dir / "gradlew").exists() or (project_dir / "gradlew.bat").exists() else "gradle"


def _gradle_root_evidence(root: Path) -> str:
    for name in ("settings.gradle.kts", "settings.gradle", "build.gradle.kts", "build.gradle", "gradlew"):
        if (root / name).exists():
            return name
    return "."


def _gradle_build_files(root: Path) -> list[str]:
    result: list[str] = []
    for path in sorted([*root.rglob("build.gradle"), *root.rglob("build.gradle.kts")]):
        relative = path.relative_to(root).as_posix()
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts) or is_generated_path(relative) or is_sample_path(relative):
            continue
        result.append(relative)
    return result


def _looks_like_nested_gradle_project(project_dir: Path) -> bool:
    return any(
        (project_dir / name).exists()
        for name in ("settings.gradle", "settings.gradle.kts", "gradlew", "gradlew.bat")
    )


def _looks_like_ktor_gradle_build(source: str) -> bool:
    lowered = source.lower()
    return "io.ktor.plugin" in lowered or "ktor-server" in lowered


def _project_has_ktor_application_config(project_dir: Path) -> bool:
    for relative in (
        "src/main/resources/application.conf",
        "src/main/resources/application.yaml",
        "src/main/resources/application.yml",
        "src/backendMain/resources/application.conf",
    ):
        path = project_dir / relative
        if path.exists() and "ktor" in _read_manifest_text(path).lower():
            return True
    return False


def _ktor_entrypoint_evidence(root: Path, project_dir: Path) -> str | None:
    for relative in (
        "src/main/resources/application.conf",
        "src/main/resources/application.yaml",
        "src/main/resources/application.yml",
        "src/backendMain/resources/application.conf",
    ):
        path = project_dir / relative
        if path.exists():
            return path.relative_to(root).as_posix()
    for pattern in ("src/main/kotlin/**/*.kt", "src/backendMain/kotlin/**/*.kt", "src/**/*.kt"):
        for path in sorted(project_dir.glob(pattern)):
            if is_test_path(path.relative_to(project_dir).as_posix()):
                continue
            source = _read_manifest_text(path)
            if "embeddedServer(" in source or "fun Application." in source:
                return path.relative_to(root).as_posix()
    return None


def _gradle_android_app_modules(root: Path) -> list[tuple[str, str]]:
    modules: list[tuple[str, str]] = []
    for build_file in _gradle_build_files(root):
        source = _read_manifest_text(root / build_file).lower()
        if "android.application" not in source and "com.android.application" not in source:
            continue
        module_dir = Path(build_file).parent
        manifest = root / module_dir / "src" / "main" / "AndroidManifest.xml"
        if not manifest.exists() or not module_dir.parts:
            continue
        module = ":" + ":".join(module_dir.parts)
        modules.append((module, build_file))
    return modules


def _looks_like_rails_project(root: Path) -> bool:
    gemfile = root / "Gemfile"
    if gemfile.exists():
        source = _read_manifest_text(gemfile).lower()
        if re.search(r"\bgem\s+['\"](?:rails|railties)['\"]", source):
            return True
    return (root / "config" / "application.rb").exists() and (root / "config" / "routes.rb").exists()


def _dotnet_run_command_for_program(root: Path, file_fact: FileFact) -> str | None:
    program_path = root / file_fact.path
    source = _read_manifest_text(program_path)
    if not _looks_like_dotnet_program_source(source):
        return None
    project = _nearest_dotnet_project(root, program_path)
    if project:
        return f"dotnet run --project {project}"
    return "dotnet run"


def _nearest_dotnet_project(root: Path, path: Path) -> str | None:
    for parent in [path.parent, *path.parents]:
        if parent == root.parent:
            break
        projects = sorted(parent.glob("*.csproj"))
        if projects:
            return projects[0].relative_to(root).as_posix()
        if parent == root:
            break
    return None


def _dotnet_solution_paths(root: Path) -> list[str]:
    return _dotnet_manifest_paths(root, "*.sln")


def _dotnet_project_paths(root: Path) -> list[str]:
    return _dotnet_manifest_paths(root, "*.csproj")


def _dotnet_manifest_paths(root: Path, pattern: str) -> list[str]:
    result: list[str] = []
    for path in sorted(root.rglob(pattern)):
        relative = path.relative_to(root).as_posix()
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts) or is_generated_path(relative) or is_sample_path(relative):
            continue
        result.append(relative)
    return result


def _looks_like_dotnet_program_source(source: str) -> bool:
    return any(
        marker in source
        for marker in (
            "WebApplication.CreateBuilder",
            "Host.CreateDefaultBuilder",
            "CreateHostBuilder",
            "builder.Services",
            "app.Map",
            "app.Run(",
        )
    )


def _looks_like_dotnet_runnable_project(source: str) -> bool:
    lowered = source.lower()
    return (
        "microsoft.net.sdk.web" in lowered
        or "microsoft.net.sdk.blazorwebassembly" in lowered
        or "microsoft.aspnetcore.components.webassembly" in lowered
        or "<outputtype>exe</outputtype>" in lowered
    )


def _command(path: str, name: str, description: str, arguments: list[str], options: list[str]) -> CommandFact:
    return CommandFact(
        path=path,
        name=name,
        description=description,
        arguments=arguments,
        options=options,
        evidence=Evidence(file=path, kind="command", line_start=1, line_end=1),
    )


def _dedupe_commands(commands: list[CommandFact]) -> list[CommandFact]:
    seen: set[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = set()
    result: list[CommandFact] = []
    for command in commands:
        key = (command.path, command.name, tuple(command.arguments), tuple(command.options))
        if key in seen:
            continue
        seen.add(key)
        result.append(command)
    return sorted(result, key=lambda item: (item.name, item.path, item.arguments))


def _read_json_manifest(path: Path) -> object:
    return json.loads(_read_manifest_text(path))


def _string_value(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _line_for_offset(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _read_manifest_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="ignore")
