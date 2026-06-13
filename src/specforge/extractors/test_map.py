from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re
from pathlib import Path

from specforge.models import ApiRouteFact, CommandFact, ComponentFact, DataModelFact, Evidence, FileFact, RepositoryFact, ServiceFact, TestMapFact


MAX_TEST_MAP_SOURCE_BYTES = 256_000
GENERIC_TEST_MAP_TOKENS = {
    "api",
    "app",
    "base",
    "body",
    "client",
    "config",
    "controller",
    "create",
    "data",
    "delete",
    "get",
    "handler",
    "index",
    "list",
    "local",
    "main",
    "path",
    "post",
    "put",
    "read",
    "root",
    "route",
    "server",
    "service",
    "test",
    "update",
}
GENERIC_COMPONENT_TEST_TOKENS = {
    "admin",
    "avatar",
    "base",
    "button",
    "cell",
    "checkbox",
    "container",
    "content",
    "custom",
    "date",
    "dropdown",
    "field",
    "form",
    "header",
    "icon",
    "image",
    "input",
    "item",
    "label",
    "link",
    "links",
    "list",
    "menu",
    "modal",
    "navigation",
    "notification",
    "notifications",
    "result",
    "results",
    "row",
    "step",
    "table",
    "text",
    "topic",
    "topics",
    "upload",
    "user",
    "users",
}
GENERIC_TEST_RUNNER_COMMANDS = {
    "clojure -m:test",
    "go test",
    "mix test",
    "npm run test",
    "npm test",
    "php artisan test",
    "pnpm run test",
    "pnpm test",
    "pytest",
    "python manage.py test",
    "sbt test",
    "yarn test",
}
TEST_MAP_CONTENT_LANGUAGES = {
    "python",
    "javascript",
    "typescript",
    "go",
    "java",
    "kotlin",
    "php",
    "ruby",
    "rust",
    "scala",
    "csharp",
    "dart",
    "elixir",
    "clojure",
    "shell",
    "swift",
    "vue",
    "svelte",
    "astro",
    "html",
    "jsp",
}
TEST_MAP_ARTIFACT_SUFFIXES = {
    ".avif",
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".properties",
    ".snap",
    ".svg",
    ".txt",
    ".webp",
}
SWIFT_TCA_INITIAL_STATE_RE = re.compile(
    r"\binitialState\s*:\s*(?P<target>[A-Za-z_]\w*(?:<[^>\n]+>)?(?:\.[A-Za-z_]\w*)*)\s*\.State\b",
    re.IGNORECASE | re.MULTILINE,
)
SWIFT_TCA_TESTSTORE_REDUCER_RE = re.compile(
    r"\bTestStore\s*\([\s\S]{0,900}?\)\s*\{\s*(?P<target>[A-Za-z_]\w*)\s*\(",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class _SearchContext:
    haystack: str
    terms: frozenset[str]


def build_test_maps(
    root: Path,
    test_files: list[FileFact],
    api_routes: list[ApiRouteFact],
    components: list[ComponentFact],
    commands: list[CommandFact],
    services: list[ServiceFact],
    repositories: list[RepositoryFact],
    data_models: list[DataModelFact],
) -> list[TestMapFact]:
    maps: list[TestMapFact] = []
    for test_file in test_files:
        if _should_skip_test_map_artifact(test_file):
            continue
        should_read_content = _should_read_test_content(test_file)
        source = _read(root / test_file.path) if should_read_content else ""
        search = _build_search_context(test_file.path, source)
        match = None
        if should_read_content:
            api_route_match = _match_api_route(
                search,
                api_routes,
                allow_root_route=_allows_root_route_match(test_file),
                allow_symbolic_match=_allows_symbolic_route_match(test_file),
            )
            component_match = _match_component(search, components) if _should_match_components(test_file) else None
            command_match = _match_command(search, commands)
            named_target_match = _match_named_code_target(
                search,
                test_file,
                services,
                repositories,
                data_models,
            )
            swift_tca_match = _match_swift_tca_target(search, data_models) if _is_swift_test_file(test_file) else None
            if _should_prefer_swift_tca_before_components(test_file):
                match = api_route_match or swift_tca_match or named_target_match or component_match or command_match
            elif _should_prefer_named_code_targets(test_file):
                match = api_route_match or swift_tca_match or named_target_match or component_match or command_match
            else:
                match = api_route_match or component_match or swift_tca_match or command_match or named_target_match
        if match:
            kind, target, confidence = match
            maps.append(
                TestMapFact(
                    test_path=test_file.path,
                    target_kind=kind,
                    target=target,
                    confidence=confidence,
                    evidence=Evidence(file=test_file.path, kind="test-map", line_start=1, line_end=1),
                )
            )
        else:
            maps.append(
                TestMapFact(
                    test_path=test_file.path,
                    target_kind="unmatched",
                    target=None,
                    confidence="low",
                    evidence=Evidence(file=test_file.path, kind="test-map", line_start=1, line_end=1),
                )
            )
    return maps


def _build_search_context(path: str, source: str) -> _SearchContext:
    raw_haystack = f"{path}\n{source}"
    return _SearchContext(haystack=raw_haystack.lower(), terms=frozenset(_tokenize(raw_haystack)))


def _tokenize(value: str) -> set[str]:
    terms: set[str] = set()
    for raw_token in re.findall(r"[A-Za-z0-9_]+(?:[-.][A-Za-z0-9_]+)*", value):
        token = raw_token.strip("_").lower()
        if not token:
            continue
        terms.add(token)
        if "-" in token:
            terms.add(token.replace("-", "_"))
        if "_" in token:
            terms.add(token.replace("_", "-"))
        if "." in token:
            terms.update(part for part in token.split(".") if part)
        camel_parts = _camel_token_parts(raw_token)
        if len(camel_parts) > 1:
            joined = "".join(camel_parts)
            terms.add(joined)
            terms.update(camel_parts)
            if camel_parts[0] == "i" and len(camel_parts) > 2:
                terms.add("".join(camel_parts[1:]))
            for suffix in ("tests", "test", "specs", "spec"):
                if joined.endswith(suffix) and len(joined) > len(suffix):
                    terms.add(joined[: -len(suffix)])
    return terms


def _camel_token_parts(value: str) -> list[str]:
    parts: list[str] = []
    for segment in re.split(r"[-_.]+", value.strip("_")):
        parts.extend(
            part.lower()
            for part in re.findall(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+", segment)
            if part
        )
    return parts


def _should_read_test_content(test_file: FileFact) -> bool:
    if test_file.size_bytes > MAX_TEST_MAP_SOURCE_BYTES:
        return False
    if test_file.language in TEST_MAP_CONTENT_LANGUAGES:
        return True
    suffix = Path(test_file.path).suffix.lower()
    return suffix in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".rb", ".php", ".java", ".go", ".rs", ".scala", ".cs", ".swift", ".sh", ".bash", ".bats"}


def _should_skip_test_map_artifact(test_file: FileFact) -> bool:
    name = Path(test_file.path).name.lower()
    suffix = Path(test_file.path).suffix.lower()
    normalized = test_file.path.replace("\\", "/").lower()
    parts = set(normalized.split("/"))
    return bool(
        suffix in TEST_MAP_ARTIFACT_SUFFIXES
        or re.fullmatch(r"(?:tsconfig|jsconfig)(?:[.\w-]*)?\.json", name)
        or name in {".eslintrc.json", ".eslintrc.js", ".eslintrc.cjs", ".stylelintrc.json"}
        or bool(parts & {"fixture", "fixtures", "cassettes", "cassette", "testdata", "test_data", "__snapshots__", "snapshots", "snapshot"})
        or _is_python_test_support_artifact(name, parts)
    )


def _is_python_test_support_artifact(name: str, parts: set[str]) -> bool:
    if not name.endswith(".py"):
        return False
    if name in {"__init__.py", "conftest.py"}:
        return True
    return "tests" in parts and not (name.startswith("test_") or name.endswith("_test.py"))


def _should_match_components(test_file: FileFact) -> bool:
    if _is_swift_test_file(test_file):
        return _should_match_swift_components(test_file)
    if test_file.language in {"typescript", "javascript", "vue", "svelte", "astro", "html", "dart", "kotlin", "swift", "xaml"}:
        return True
    suffix = Path(test_file.path).suffix.lower()
    return suffix in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte", ".astro", ".html", ".htm", ".dart", ".kt", ".kts", ".swift", ".xaml"}


def _is_swift_test_file(test_file: FileFact) -> bool:
    return test_file.language == "swift" or Path(test_file.path).suffix.lower() == ".swift"


def _should_match_swift_components(test_file: FileFact) -> bool:
    normalized = test_file.path.replace("\\", "/").lower()
    stem = Path(normalized).stem
    stem_parts = set(_camel_token_parts(Path(test_file.path).stem))
    if stem_parts & {"view", "snapshot", "screen", "ui"}:
        return True
    if "/appstoresnapshottests/" in f"/{normalized}":
        return True
    non_ui_markers = (
        "/clientmodelstests/",
        "/database",
        "/server",
        "/sharedmodelstests/",
        "/routertests/",
        "/runnertests/",
        "/config",
        "/dictionary",
    )
    if any(marker in f"/{normalized}" for marker in non_ui_markers) or "middlewaretests" in normalized or "middlewareintegrationtests" in normalized:
        return False
    if stem.endswith("featuretests") or "/featuretests/" in f"/{normalized}":
        return False
    return True


def _should_match_data_models(test_file: FileFact) -> bool:
    normalized = test_file.path.replace("\\", "/").lower()
    stem = Path(normalized).stem
    path_with_slashes = f"/{normalized}"
    swift_ui_test = _is_swift_test_file(test_file) and any(marker in stem for marker in ("view", "snapshot", "screen", "ui"))
    return (
        any(
            marker in path_with_slashes
            for marker in (
                "/models/",
                "/model/",
                "/entities/",
                "/entity/",
                "/schemas/",
                "/schema/",
                "/domain/",
                "/domains/",
                "/featuretests/",
                "/sharedmodelstests/",
                "/clientmodelstests/",
            )
        )
        or re.search(r"(?:^|[_-])(model|entity|schema)(?:[_-]|$)", stem) is not None
        or (
            _is_swift_test_file(test_file)
            and not swift_ui_test
            and (stem.endswith(("featuretests", "modeltests", "codabilitytests")) or "featuretests" in normalized)
        )
    )


def _match_named_code_target(
    search: _SearchContext,
    test_file: FileFact,
    services: list[ServiceFact],
    repositories: list[RepositoryFact],
    data_models: list[DataModelFact],
) -> tuple[str, str, str] | None:
    if _should_prefer_repositories(test_file):
        return (
            _match_named_fact(search, "repository", [(item.name, item.path) for item in repositories])
            or _match_named_fact(search, "service", [(item.name, item.path) for item in services])
            or _match_data_model_target(search, test_file, data_models)
        )
    if _should_match_data_models(test_file) and not _should_prefer_services(test_file):
        return (
            _match_data_model_target(search, test_file, data_models)
            or _match_named_fact(search, "service", [(item.name, item.path) for item in services])
            or _match_named_fact(search, "repository", [(item.name, item.path) for item in repositories])
        )
    return (
        _match_named_fact(search, "service", [(item.name, item.path) for item in services])
        or _match_named_fact(search, "repository", [(item.name, item.path) for item in repositories])
        or _match_data_model_target(search, test_file, data_models)
    )


def _match_data_model_target(
    search: _SearchContext,
    test_file: FileFact,
    data_models: list[DataModelFact],
) -> tuple[str, str, str] | None:
    if not _should_match_data_models(test_file):
        return None
    stem_match = _match_named_fact_by_test_stem(test_file, "data-model", [(item.name, item.path) for item in data_models])
    if stem_match:
        return stem_match
    if _is_swift_test_file(test_file):
        return None
    return _match_named_fact(search, "data-model", [(item.name, item.path) for item in data_models])


def _match_swift_tca_target(
    search: _SearchContext,
    data_models: list[DataModelFact],
) -> tuple[str, str, str] | None:
    candidates = _swift_tca_candidate_map(data_models)
    for match in SWIFT_TCA_INITIAL_STATE_RE.finditer(search.haystack):
        target = _clean_swift_tca_target(match.group("target"))
        matched = candidates.get(target.lower())
        if matched:
            return "data-model", matched, "high"
    for match in SWIFT_TCA_TESTSTORE_REDUCER_RE.finditer(search.haystack):
        target = _clean_swift_tca_target(match.group("target"))
        matched = candidates.get(target.lower())
        if matched:
            return "data-model", matched, "high"
    return None


def _swift_tca_candidate_map(data_models: list[DataModelFact]) -> dict[str, str]:
    result: dict[str, str] = {}
    for model in data_models:
        if model.kind == "tca-reducer":
            result[model.name.lower()] = model.name
        elif model.kind == "tca-state" and model.name.endswith(".State"):
            result.setdefault(model.name.removesuffix(".State").lower(), model.name.removesuffix(".State"))
    return result


def _clean_swift_tca_target(value: str) -> str:
    target = re.sub(r"<[^>\n]+>", "", value.strip())
    return target.rsplit(".", 1)[0] if "." in target else target


def _should_prefer_repositories(test_file: FileFact) -> bool:
    normalized = test_file.path.replace("\\", "/").lower()
    stem = Path(normalized).stem
    return (
        "/data." in normalized
        or "/data/" in f"/{normalized}"
        or "/repositories/" in f"/{normalized}"
        or "/repository/" in f"/{normalized}"
        or "repository" in stem
    )


def _should_prefer_services(test_file: FileFact) -> bool:
    normalized = test_file.path.replace("\\", "/").lower()
    stem = Path(normalized).stem
    return (
        "/services." in normalized
        or "/services/" in f"/{normalized}"
        or "/service/" in f"/{normalized}"
        or "service" in stem
    )


def _should_prefer_named_code_targets(test_file: FileFact) -> bool:
    if _is_swift_test_file(test_file):
        normalized = test_file.path.replace("\\", "/").lower()
        stem = Path(normalized).stem
        if "featuretests" in normalized and "view" not in stem:
            return True
    return _should_prefer_repositories(test_file) or _should_prefer_services(test_file) or _should_match_data_models(test_file)


def _should_prefer_swift_tca_before_components(test_file: FileFact) -> bool:
    if not _is_swift_test_file(test_file):
        return False
    stem_parts = set(_camel_token_parts(Path(test_file.path).stem))
    return not bool(stem_parts & {"view", "snapshot", "screen", "ui"})


def _allows_root_route_match(test_file: FileFact) -> bool:
    suffix = Path(test_file.path).suffix.lower()
    if suffix in {".sh", ".bash", ".bats", ".sql", ".yml", ".yaml", ".json"}:
        return False
    return test_file.language in TEST_MAP_CONTENT_LANGUAGES or suffix in {".ts", ".tsx", ".js", ".jsx", ".cs", ".java", ".py", ".rb", ".php", ".go", ".rs", ".scala"}


def _allows_symbolic_route_match(test_file: FileFact) -> bool:
    normalized = test_file.path.replace("\\", "/").lower()
    path_with_slashes = f"/{normalized}"
    backend_test_markers = (
        "/api/",
        "/apis/",
        "/controller/",
        "/controllers/",
        "/endpoint/",
        "/endpoints/",
        "/integration/",
        "/request/",
        "/requests/",
        "/route/",
        "/routes/",
    )
    return any(marker in path_with_slashes for marker in backend_test_markers)


def _match_api_route(
    search: _SearchContext,
    api_routes: list[ApiRouteFact],
    *,
    allow_root_route: bool = False,
    allow_symbolic_match: bool = False,
) -> tuple[str, str, str] | None:
    for route in api_routes:
        path = route.path.lower()
        if route.framework == "trpc":
            trpc_match = _match_trpc_api_route(search.haystack, route)
            if trpc_match:
                return trpc_match
            continue
        if path.startswith("/graphql#"):
            graphql_match = _match_graphql_api_route(search.haystack, route)
            if graphql_match:
                return graphql_match
            continue
        if not path.rstrip("/") and not allow_root_route:
            continue
        if path.rstrip("/") and _contains_route_path(search, path):
            return "api-route", f"{route.method} {route.path}", "high"
        if not path.rstrip("/") and allow_root_route and _contains_route_path(search, path):
            return "api-route", f"{route.method} {route.path}", "high"
        if not allow_symbolic_match:
            continue
        phoenix_helper_match = _match_phoenix_route_helper(search.haystack, route)
        if phoenix_helper_match:
            return phoenix_helper_match
        handler = (route.handler or "").lower()
        if _is_meaningful_identifier(handler) and _contains_token(search, handler):
            return "api-route", f"{route.method} {route.path}", "medium"
        controller = Path(route.evidence.file).stem.lower() if route.evidence.file else ""
        if _is_meaningful_identifier(controller) and _contains_token(search, controller):
            return "api-route", f"{route.method} {route.path}", "medium"
        tokens = _route_path_tokens(path)
        if len(tokens) == 1 and f"{tokens[0]}controller" in search.haystack:
            return "api-route", f"{route.method} {route.path}", "medium"
        if len(tokens) >= 2 and all(_contains_token(search, token) for token in tokens[:3]):
            return "api-route", f"{route.method} {route.path}", "medium"
    return None


def _match_trpc_api_route(haystack: str, route: ApiRouteFact) -> tuple[str, str, str] | None:
    procedure = route.path.removeprefix("/trpc/").strip("/")
    if not procedure:
        return None
    parts = [part for part in procedure.split(".") if part]
    if len(parts) >= 2:
        namespace = re.escape(parts[-2].lower())
        name = re.escape(parts[-1].lower())
        if re.search(rf"\b(?:caller|trpc|api|utils)\.{namespace}\.{name}\b", haystack):
            return "api-route", f"{route.method} {route.path}", "high"
        if re.search(rf"\bapp-router\[['\"]{namespace}['\"]\]\[['\"]{name}['\"]\]", haystack):
            return "api-route", f"{route.method} {route.path}", "high"
        if re.search(rf"\bapprouter\[['\"]{namespace}['\"]\]\[['\"]{name}['\"]\]", haystack):
            return "api-route", f"{route.method} {route.path}", "high"
    name = re.escape(parts[-1].lower())
    if re.search(rf"\b(?:caller|trpc|api|utils)\.{name}\b", haystack):
        return "api-route", f"{route.method} {route.path}", "high"
    if procedure.lower() in haystack:
        return "api-route", f"{route.method} {route.path}", "medium"
    return None


def _match_phoenix_route_helper(haystack: str, route: ApiRouteFact) -> tuple[str, str, str] | None:
    handler_match = re.match(r"(?P<controller>[A-Za-z_]\w*)Controller:(?P<action>[A-Za-z_]\w*)$", route.handler or "")
    if not handler_match:
        return None
    action = handler_match.group("action").lower()
    for helper_name in _phoenix_route_helper_names(handler_match.group("controller"), route.path):
        if re.search(rf"\b{re.escape(helper_name)}_(?:path|url)\s*\([^)]*:\s*{re.escape(action)}\b", haystack):
            return "api-route", f"{route.method} {route.path}", "high"
    return None


def _phoenix_route_helper_names(controller: str, path: str) -> tuple[str, ...]:
    base = _camel_to_snake(controller.removesuffix("Controller"))
    names = [base]
    static_segments = [
        _singular_helper_segment(segment)
        for segment in path.split("/")
        if segment and not segment.startswith(":") and not _is_generic_route_prefix(segment)
    ]
    for start in range(len(static_segments)):
        candidate = "_".join(static_segments[start:])
        if candidate.endswith(base):
            names.append(candidate)
    return tuple(dict.fromkeys(name for name in names if name))


def _camel_to_snake(value: str) -> str:
    first = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", value)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", first).lower()


def _singular_helper_segment(value: str) -> str:
    normalized = value.strip("_").lower()
    if normalized.endswith("ies"):
        return f"{normalized[:-3]}y"
    if normalized.endswith("s") and len(normalized) > 1 and not normalized.endswith("ss"):
        return normalized[:-1]
    return normalized


def _is_generic_route_prefix(value: str) -> bool:
    return value.lower() == "api" or re.fullmatch(r"v\d+", value.lower()) is not None


@lru_cache(maxsize=8192)
def _route_path_tokens(path: str) -> tuple[str, ...]:
    tokens = [token for token in re.split(r"[/{}:<>\[\]-]+", path) if token and not token.startswith(":")]
    return tuple(token for token in tokens if _is_meaningful_identifier(token))


def _match_graphql_api_route(haystack: str, route: ApiRouteFact) -> tuple[str, str, str] | None:
    lowered_path = route.path.lower()
    if lowered_path in haystack:
        return "api-route", f"{route.method} {route.path}", "high"
    match = re.match(r"/graphql#(?P<operation>query|mutation|subscription)\.(?P<field>[A-Za-z_]\w*)", route.path, re.IGNORECASE)
    if not match:
        return None
    operation = match.group("operation").lower()
    field = match.group("field")
    if re.search(rf"\b{operation}\b[\s\S]{{0,1600}}\b{re.escape(field)}\b\s*(?:\(|{{|@|\n|\r)", haystack, re.IGNORECASE):
        return "api-route", f"{route.method} {route.path}", "high"
    gql_test_call = re.search(r"\b(?:graphql_query|graphql_mutation|graphql_subscription|gql|execute_graphql|post_graphql)\b", haystack)
    if gql_test_call and re.search(rf"(?<![A-Za-z0-9_]){re.escape(field)}(?![A-Za-z0-9_])", haystack):
        return "api-route", f"{route.method} {route.path}", "medium"
    return None


def _match_component(
    search: _SearchContext,
    components: list[ComponentFact],
) -> tuple[str, str, str] | None:
    for component in components:
        name = component.name.lower()
        if _is_meaningful_component_identifier(name) and _contains_token(search, name):
            return "component", component.name, "high"
    for component in components:
        stem = Path(component.path).stem.lower()
        if _is_meaningful_component_identifier(stem) and _contains_token(search, stem):
            return "component", component.name, "medium"
    return None


def _match_command(
    search: _SearchContext,
    commands: list[CommandFact],
) -> tuple[str, str, str] | None:
    for command in commands:
        name = command.name.lower()
        if _is_generic_test_runner_command(name):
            continue
        if name and _contains_token(search, name):
            return "cli-command", command.name, "medium"
    return None


def _is_generic_test_runner_command(command_name: str) -> bool:
    normalized = " ".join(command_name.strip().lower().split())
    return normalized in GENERIC_TEST_RUNNER_COMMANDS or normalized.endswith(" run test")


def _match_named_fact(
    search: _SearchContext,
    kind: str,
    candidates: list[tuple[str, str]],
) -> tuple[str, str, str] | None:
    for name, path in candidates:
        lowered = name.lower()
        if _is_meaningful_identifier(lowered) and _contains_token(search, lowered):
            return kind, name, "medium"
        stem = Path(path).stem.lower()
        if _is_meaningful_identifier(stem) and _contains_token(search, stem):
            return kind, name, "medium"
    return None


def _match_named_fact_by_test_stem(
    test_file: FileFact,
    kind: str,
    candidates: list[tuple[str, str]],
) -> tuple[str, str, str] | None:
    raw_stem = Path(test_file.path).stem
    normalized_stem = _test_stem_without_suffix(raw_stem)
    for name, path in candidates:
        for candidate in _candidate_name_values(name):
            lowered = candidate.lower()
            if _is_generic_nested_model_name(candidate) and lowered != normalized_stem:
                continue
            if _is_meaningful_identifier(lowered) and lowered == normalized_stem:
                return kind, name, "high"
    for name, path in candidates:
        if _is_generic_nested_model_name(name):
            continue
        stem = Path(path).stem
        lowered = stem.lower()
        if _is_meaningful_identifier(lowered) and lowered == normalized_stem:
            return kind, name, "high"
    return None


def _test_stem_without_suffix(stem: str) -> str:
    normalized = "".join(_camel_token_parts(stem))
    for suffix in ("tests", "test", "specs", "spec"):
        if normalized.endswith(suffix) and len(normalized) > len(suffix):
            return normalized[: -len(suffix)]
    return normalized


def _candidate_name_values(name: str) -> list[str]:
    values = [name]
    if "." in name:
        values.append(name.rsplit(".", 1)[0])
    collapsed = "".join(_camel_token_parts(name))
    if collapsed:
        values.append(collapsed)
    return list(dict.fromkeys(values))


def _is_generic_nested_model_name(name: str) -> bool:
    normalized = name.rsplit(".", 1)[-1].lower()
    return normalized in {"action", "state", "request", "response", "result", "results", "entry", "rank", "defaults", "config", "settings"}


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _contains_token(search: _SearchContext, token: str) -> bool:
    normalized = token.strip().lower()
    if not normalized:
        return False
    if re.fullmatch(r"[a-z0-9_]+(?:[-.][a-z0-9_]+)*", normalized):
        return (
            normalized in search.terms
            or normalized.replace("-", "_") in search.terms
            or normalized.replace("_", "-") in search.terms
        )
    return normalized in search.haystack


def _is_meaningful_identifier(token: str) -> bool:
    normalized = token.strip().lower()
    if len(normalized) < 4:
        return False
    if normalized in GENERIC_TEST_MAP_TOKENS:
        return False
    return re.search(r"[a-z]", normalized) is not None


def _is_meaningful_component_identifier(token: str) -> bool:
    normalized = token.strip().lower()
    if not _is_meaningful_identifier(normalized):
        return False
    base = re.sub(r"(?:component|view|page)$", "", normalized)
    base = base.strip("_-.")
    if not base or base in GENERIC_COMPONENT_TEST_TOKENS:
        return False
    return True


def _contains_route_path(search: _SearchContext, path: str) -> bool:
    normalized = path.rstrip("/") or "/"
    if normalized == "/":
        return re.search(r"(?:\b(?:get|post|put|patch|delete)\s+|['\"`])/(?:['\"`\s?#),.;:]|$)", search.haystack) is not None
    if normalized in search.haystack:
        escaped = re.escape(normalized)
        return re.search(rf"(?<![a-z0-9]){escaped}(?:/|['\"`\s?#),.;:]|$)", search.haystack) is not None
    route_pattern = _route_path_match_pattern(normalized)
    return route_pattern is not None and re.search(route_pattern, search.haystack) is not None


def _route_path_match_pattern(path: str) -> str | None:
    if not any(marker in path for marker in ("{", ":", "<")):
        return None
    parts = path.strip("/").split("/")
    pattern_parts: list[str] = []
    for part in parts:
        if not part:
            continue
        if re.fullmatch(r"\{[^}]+\}|:[A-Za-z_]\w*|<[^>]+>", part):
            pattern_parts.append(r"[^/'\"`\s?#),.;:]+")
        else:
            pattern_parts.append(re.escape(part))
    if not pattern_parts:
        return None
    return rf"(?<![a-z0-9])/{'/'.join(pattern_parts)}(?:/|['\"`\s?#),.;:]|$)"
