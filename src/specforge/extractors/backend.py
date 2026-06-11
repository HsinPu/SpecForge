from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from specforge.models import (
    ApiRouteFact,
    BackendSurfaceFact,
    Evidence,
    FileFact,
    FrameworkFact,
    RequestParamFact,
    SymbolFact,
)


EXPRESS_ROUTE_RE = re.compile(
    r"\b(?:app|router|server)\.(?P<method>get|post|put|delete|patch|options|head|all)"
    r"\(\s*['\"`](?P<path>[^'\"`]+)['\"`]\s*(?:,\s*(?P<handler>[A-Za-z_$][\w$.\[\]]+))?",
    re.IGNORECASE,
)
FASTAPI_ROUTE_RE = re.compile(
    r"@(?:app|router)\.(?P<method>get|post|put|delete|patch|options|head)"
    r"\(\s*['\"](?P<path>[^'\"]+)['\"]",
    re.IGNORECASE,
)
FLASK_ROUTE_RE = re.compile(
    r"@(?:app|blueprint|bp)\.route\(\s*['\"](?P<path>[^'\"]+)['\"](?P<args>[^)]*)\)",
    re.IGNORECASE | re.DOTALL,
)
SPRING_ROUTE_RE = re.compile(
    r"@(?P<annotation>GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping)"
    r"(?:\s*\((?P<args>.*?)\))?",
    re.DOTALL,
)
SPRING_METHOD_RE = re.compile(r"RequestMethod\.(?P<method>GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)")
SPRING_PATH_RE = re.compile(r"""["'](?P<path>/[^"']*)["']""")
JAVA_CLASS_RE = re.compile(
    r"\b(?:(?:public|protected|private|abstract|final|static)\s+)*"
    r"(?P<kind>class|interface|enum)\s+"
    r"(?P<name>[A-Za-z_]\w*)"
    r"(?P<rest>[^{;]*)\{",
    re.MULTILINE,
)
JAVA_METHOD_DECL_RE = re.compile(
    r"(?:@\w+(?:\s*\([^)]*\))?\s*)*"
    r"(?:(?:public|protected|private)\s+)?"
    r"(?:(?:static|final|synchronized)\s+)*"
    r"(?P<return>[\w<>, ?\[\].]+?)\s+"
    r"(?P<name>[A-Za-z_]\w*)\s*\(",
    re.MULTILINE,
)
WEB_SERVLET_RE = re.compile(r"@WebServlet(?:\s*\((?P<args>.*?)\))?", re.DOTALL)
QUOTED_PATH_RE = re.compile(r"""["'](?P<path>/[^"']*)["']""")
PY_FUNCTION_AFTER_DECORATOR_RE = re.compile(r"\n\s*(?:async\s+)?def\s+(?P<name>[A-Za-z_]\w*)")


def extract_backend_facts(
    root: Path,
    files: list[FileFact],
    symbols: list[SymbolFact],
    frameworks: list[FrameworkFact],
) -> tuple[list[ApiRouteFact], list[BackendSurfaceFact]]:
    routes: list[ApiRouteFact] = []
    for file_fact in files:
        if file_fact.role == "test":
            continue
        normalized = file_fact.path.replace("\\", "/")
        if file_fact.language in {"typescript", "javascript"}:
            routes.extend(_extract_express_routes(root, file_fact))
            routes.extend(_extract_next_api_routes(root, file_fact, symbols))
        elif file_fact.language == "python":
            routes.extend(_extract_python_backend_routes(root, file_fact))
        elif file_fact.language == "java":
            routes.extend(_extract_spring_routes(root, file_fact))
            routes.extend(_extract_web_servlet_routes(root, file_fact))
        elif file_fact.language == "xml" and normalized.endswith("WEB-INF/web.xml"):
            routes.extend(_extract_web_xml_routes(root, file_fact))

    surfaces = _build_backend_surfaces(routes, symbols, frameworks)
    return routes, surfaces


def _extract_express_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    routes: list[ApiRouteFact] = []
    for match in EXPRESS_ROUTE_RE.finditer(source):
        line = _line_for_offset(source, match.start())
        routes.append(
            ApiRouteFact(
                method=match.group("method").upper(),
                path=match.group("path"),
                handler=match.group("handler"),
                framework="express",
                kind="express-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
            )
        )
    return routes


def _extract_next_api_routes(root: Path, file_fact: FileFact, symbols: list[SymbolFact]) -> list[ApiRouteFact]:
    normalized = file_fact.path.replace("\\", "/")
    if not (
        normalized.startswith("pages/api/")
        or (normalized.startswith("app/api/") and normalized.endswith("/route.ts"))
        or (normalized.startswith("app/api/") and normalized.endswith("/route.js"))
    ):
        return []

    route_path = _next_api_path(normalized)
    file_symbols = [symbol for symbol in symbols if symbol.path == file_fact.path]
    methods = [
        symbol
        for symbol in file_symbols
        if symbol.name.upper() in {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}
    ]
    if not methods:
        return [
            ApiRouteFact(
                method="ANY",
                path=route_path,
                handler=None,
                framework="next",
                kind="next-api-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=1, line_end=1),
            )
        ]
    return [
        ApiRouteFact(
            method=symbol.name.upper(),
            path=route_path,
            handler=symbol.name,
            framework="next",
            kind="next-api-route",
            evidence=symbol.evidence,
        )
        for symbol in methods
    ]


def _extract_python_backend_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    routes: list[ApiRouteFact] = []
    for match in FASTAPI_ROUTE_RE.finditer(source):
        line = _line_for_offset(source, match.start())
        handler = _function_after(source, match.end())
        routes.append(
            ApiRouteFact(
                method=match.group("method").upper(),
                path=match.group("path"),
                handler=handler,
                framework="fastapi",
                kind="fastapi-route",
                evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
            )
        )
    for match in FLASK_ROUTE_RE.finditer(source):
        line = _line_for_offset(source, match.start())
        handler = _function_after(source, match.end())
        methods = _flask_methods(match.group("args"))
        for method in methods:
            routes.append(
                ApiRouteFact(
                    method=method,
                    path=match.group("path"),
                    handler=handler,
                    framework="flask",
                    kind="flask-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                )
            )
    return routes


def _extract_spring_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    routes: list[ApiRouteFact] = []
    for class_match in JAVA_CLASS_RE.finditer(source):
        class_body_start = class_match.end()
        class_body_end = _find_matching_brace(source, class_body_start - 1)
        if class_body_end is None:
            continue
        class_block = _annotation_block_before(source, class_match.start())
        if not _looks_like_spring_controller(class_block, source[class_body_start:class_body_end]):
            continue
        class_prefix = _spring_path_from_annotations(class_block)
        class_body = source[class_body_start:class_body_end]
        for route_match in SPRING_ROUTE_RE.finditer(class_body):
            absolute_start = class_body_start + route_match.start()
            absolute_end = class_body_start + route_match.end()
            args = route_match.group("args") or ""
            method_path = _spring_path_from_args(args)
            full_path = _join_paths(class_prefix, method_path)
            line = _line_for_offset(source, absolute_start)
            method_info = _java_method_after(source, absolute_end, file_fact.path, line)
            methods = _spring_methods(route_match.group("annotation"), args)
            for method in methods:
                routes.append(
                    ApiRouteFact(
                        method=method,
                        path=full_path,
                        handler=method_info["name"],
                        framework="spring",
                        kind="spring-route",
                        evidence=Evidence(
                            file=file_fact.path,
                            kind="backend-route",
                            line_start=line,
                            line_end=line,
                        ),
                        class_prefix=class_prefix or None,
                        parameters=method_info["parameters"],
                        request_body=method_info["request_body"],
                        response_type=method_info["response_type"],
                    )
                )
    return routes


def _extract_web_servlet_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    source = _read(root, file_fact)
    routes: list[ApiRouteFact] = []
    for match in WEB_SERVLET_RE.finditer(source):
        args = match.group("args") or ""
        paths = _dedupe(item.group("path") for item in QUOTED_PATH_RE.finditer(args))
        if not paths:
            continue
        class_match = re.search(r"\bclass\s+([A-Za-z_]\w*)", source[match.end() : match.end() + 500])
        handler = class_match.group(1) if class_match else Path(file_fact.path).stem
        line = _line_for_offset(source, match.start())
        for path in paths:
            routes.append(
                ApiRouteFact(
                    method="ANY",
                    path=path,
                    handler=handler,
                    framework="servlet",
                    kind="webservlet-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                )
            )
    return routes


def _extract_web_xml_routes(root: Path, file_fact: FileFact) -> list[ApiRouteFact]:
    path = root / file_fact.path
    source = path.read_text(encoding="utf-8")
    try:
        document = ET.fromstring(source)
    except ET.ParseError:
        return []
    namespace = _namespace(document.tag)
    classes_by_name: dict[str, str | None] = {}
    for servlet in document.findall(f".//{namespace}servlet"):
        name = _find_text(servlet, namespace, "servlet-name")
        class_name = _find_text(servlet, namespace, "servlet-class")
        if name:
            classes_by_name[name] = class_name

    routes: list[ApiRouteFact] = []
    for mapping in document.findall(f".//{namespace}servlet-mapping"):
        name = _find_text(mapping, namespace, "servlet-name")
        if not name:
            continue
        for pattern in mapping.findall(f"{namespace}url-pattern"):
            if not pattern.text or not pattern.text.strip():
                continue
            route_path = pattern.text.strip()
            line = _line_for_text(source, route_path)
            routes.append(
                ApiRouteFact(
                    method="ANY",
                    path=route_path,
                    handler=classes_by_name.get(name) or name,
                    framework="servlet",
                    kind="web-xml-route",
                    evidence=Evidence(file=file_fact.path, kind="backend-route", line_start=line, line_end=line),
                )
            )
    return routes


def _build_backend_surfaces(
    routes: list[ApiRouteFact],
    symbols: list[SymbolFact],
    frameworks: list[FrameworkFact],
) -> list[BackendSurfaceFact]:
    backend_frameworks = {item.name for item in frameworks if item.category == "backend"}
    backend_frameworks.update(route.framework for route in routes)
    surfaces: list[BackendSurfaceFact] = []
    for framework in sorted(backend_frameworks):
        framework_routes = [route for route in routes if route.framework == framework]
        services = [symbol for symbol in symbols if symbol.name.endswith("Service")]
        models = [
            symbol
            for symbol in symbols
            if symbol.name.endswith(("Model", "Entity", "DTO", "Dto", "Schema"))
        ]
        surfaces.append(
            BackendSurfaceFact(
                framework=framework,
                route_count=len(framework_routes),
                handler_count=len({route.handler for route in framework_routes if route.handler}),
                service_count=len(services),
                model_count=len(models),
                evidence=[route.evidence for route in framework_routes[:10]],
            )
        )
    return surfaces


def _next_api_path(path: str) -> str:
    if path.startswith("pages/api/"):
        stem = path.removeprefix("pages/api/").rsplit(".", 1)[0]
        return "/api/" + _clean_route_path(stem)
    stem = path.removeprefix("app/api/").removesuffix("/route.ts").removesuffix("/route.js")
    return "/api/" + _clean_route_path(stem)


def _clean_route_path(value: str) -> str:
    route = value.replace("/index", "").replace("[", ":").replace("]", "")
    return route.strip("/") or ""


def _function_after(source: str, offset: int) -> str | None:
    match = PY_FUNCTION_AFTER_DECORATOR_RE.search(source[offset : offset + 400])
    return match.group("name") if match else None


def _java_method_after(source: str, offset: int, file_path: str, line: int) -> dict[str, object]:
    window = source[offset : offset + 1600]
    match = JAVA_METHOD_DECL_RE.search(window)
    if not match:
        return {"name": None, "parameters": [], "request_body": None, "response_type": None}
    paren_start = offset + match.end() - 1
    paren_end = _find_matching_paren(source, paren_start)
    params_source = source[paren_start + 1 : paren_end] if paren_end is not None else ""
    parameters = _java_request_params(params_source, file_path, line)
    request_body = next((param.type or param.name for param in parameters if param.source == "body"), None)
    return_type = " ".join(match.group("return").split())
    return_type = re.sub(
        r"^(?:public|protected|private|static|final|synchronized)\s+",
        "",
        return_type,
    )
    return {
        "name": match.group("name"),
        "parameters": parameters,
        "request_body": request_body,
        "response_type": return_type or None,
    }


def _java_request_params(params_source: str, file_path: str, line: int) -> list[RequestParamFact]:
    params: list[RequestParamFact] = []
    for raw_param in _split_java_params(params_source):
        source = _request_param_source(raw_param)
        if source is None:
            continue
        clean = re.sub(r"@\w+(?:\s*\([^)]*\))?", " ", raw_param)
        clean = re.sub(r"\b(final|volatile)\b", " ", clean)
        tokens = [token for token in re.split(r"\s+", clean.strip()) if token]
        if len(tokens) < 2:
            continue
        name = tokens[-1].replace("...", "").strip()
        type_name = " ".join(tokens[:-1]).strip() or None
        explicit_name = _annotation_value(raw_param)
        params.append(
            RequestParamFact(
                name=explicit_name or name,
                source=source,
                type=type_name,
                required=_required_flag(raw_param),
                evidence=Evidence(file=file_path, kind="request-param", line_start=line, line_end=line),
            )
        )
    return params


def _split_java_params(params_source: str) -> list[str]:
    result: list[str] = []
    start = 0
    paren_depth = 0
    angle_depth = 0
    brace_depth = 0
    for index, char in enumerate(params_source):
        if char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth = max(0, paren_depth - 1)
        elif char == "<":
            angle_depth += 1
        elif char == ">":
            angle_depth = max(0, angle_depth - 1)
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth = max(0, brace_depth - 1)
        elif char == "," and not paren_depth and not angle_depth and not brace_depth:
            result.append(params_source[start:index].strip())
            start = index + 1
    tail = params_source[start:].strip()
    if tail:
        result.append(tail)
    return result


def _request_param_source(raw_param: str) -> str | None:
    if "@PathVariable" in raw_param:
        return "path"
    if "@RequestParam" in raw_param:
        return "query"
    if "@RequestBody" in raw_param:
        return "body"
    return None


def _annotation_value(raw_param: str) -> str | None:
    match = re.search(r"@\w+\s*\(\s*(?:value\s*=\s*|name\s*=\s*)?['\"]([^'\"]+)['\"]", raw_param)
    return match.group(1) if match else None


def _required_flag(raw_param: str) -> bool | None:
    if "required" not in raw_param:
        return None
    return not bool(re.search(r"required\s*=\s*false", raw_param))


def _looks_like_spring_controller(annotation_block: str, class_body: str) -> bool:
    return (
        "@RestController" in annotation_block
        or "@Controller" in annotation_block
        or bool(SPRING_ROUTE_RE.search(class_body))
    )


def _annotation_block_before(source: str, offset: int) -> str:
    prefix = source[max(0, offset - 800) : offset]
    lines = prefix.splitlines()
    collected: list[str] = []
    for line in reversed(lines):
        stripped = line.strip()
        if not stripped:
            if collected:
                break
            continue
        if stripped.startswith("@"):
            collected.append(stripped)
            continue
        if collected and (stripped.endswith(")") or stripped.endswith("}")):
            collected.append(stripped)
            continue
        break
    return "\n".join(reversed(collected))


def _spring_path_from_annotations(annotation_block: str) -> str:
    for match in SPRING_ROUTE_RE.finditer(annotation_block):
        if match.group("annotation") == "RequestMapping":
            return _spring_path_from_args(match.group("args") or "")
    return ""


def _spring_path_from_args(args: str) -> str:
    match = SPRING_PATH_RE.search(args)
    return match.group("path") if match else "/"


def _spring_methods(annotation: str, args: str) -> list[str]:
    mapping = {
        "GetMapping": ["GET"],
        "PostMapping": ["POST"],
        "PutMapping": ["PUT"],
        "DeleteMapping": ["DELETE"],
        "PatchMapping": ["PATCH"],
    }
    if annotation in mapping:
        return mapping[annotation]
    methods = [match.group("method") for match in SPRING_METHOD_RE.finditer(args)]
    return methods or ["ANY"]


def _join_paths(prefix: str, path: str) -> str:
    if not prefix or prefix == "/":
        return path if path.startswith("/") else f"/{path}"
    if not path or path == "/":
        return prefix
    return f"{prefix.rstrip('/')}/{path.lstrip('/')}"


def _flask_methods(args: str) -> list[str]:
    found = re.findall(r"['\"](GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)['\"]", args, flags=re.IGNORECASE)
    return [item.upper() for item in found] or ["GET"]


def _namespace(tag: str) -> str:
    match = re.match(r"\{.*\}", tag)
    return match.group(0) if match else ""


def _find_text(element: ET.Element, namespace: str, name: str) -> str | None:
    value = element.findtext(f"{namespace}{name}")
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _find_matching_brace(source: str, open_index: int) -> int | None:
    depth = 0
    for index in range(open_index, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def _find_matching_paren(source: str, open_index: int) -> int | None:
    depth = 0
    for index in range(open_index, len(source)):
        char = source[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _read(root: Path, file_fact: FileFact) -> str:
    return (root / file_fact.path).read_text(encoding="utf-8")


def _line_for_offset(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _line_for_text(source: str, text: str) -> int:
    index = source.find(text)
    return _line_for_offset(source, index) if index >= 0 else 1


def _dedupe(values: object) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(str(value))
    return result
