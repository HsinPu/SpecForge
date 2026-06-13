from __future__ import annotations

import re
from pathlib import Path

from specforge.models import ApiContractFact, ApiRouteFact, ContractDetailFact, Evidence, FileFact


PRIMITIVE_TYPES = {
    "str",
    "int",
    "float",
    "bool",
    "bytes",
    "String",
    "Integer",
    "Long",
    "Double",
    "Boolean",
}
HTTP_STATUS_NAME_TO_CODE = {
    "OK": "200",
    "CREATED": "201",
    "ACCEPTED": "202",
    "NO_CONTENT": "204",
    "BAD_REQUEST": "400",
    "UNAUTHORIZED": "401",
    "FORBIDDEN": "403",
    "NOT_FOUND": "404",
    "CONFLICT": "409",
    "UNPROCESSABLE_ENTITY": "422",
    "INTERNAL_SERVER_ERROR": "500",
}


def extract_contract_details(
    root: Path,
    files: list[FileFact],
    routes: list[ApiRouteFact],
) -> list[ContractDetailFact]:
    available = {file_fact.path for file_fact in files}
    source_cache: dict[str, str] = {}
    details: list[ContractDetailFact] = []

    for route in routes:
        if route.evidence.file not in available:
            continue
        source = source_cache.setdefault(route.evidence.file, _read(root, route.evidence.file))
        contract_source = _route_source_window(source, route)
        if route.framework in {"gin", "echo", "chi", "fiber", "go"}:
            contract_source += "\n" + _go_handler_body(files, source_cache, root, route)
        if route.framework in {"axum", "actix-web", "rocket", "warp"}:
            contract_source += "\n" + _rust_handler_body(files, source_cache, root, route)
        if route.framework == "vapor":
            contract_source += "\n" + _swift_handler_body(files, source_cache, root, route)
        if route.framework in {"koa", "hapi", "adonisjs"}:
            contract_source += "\n" + _javascript_handler_body(files, source_cache, root, route)
        if route.framework == "sails":
            contract_source += "\n" + _sails_handler_body(files, source_cache, root, route)
        if route.framework == "feathers":
            contract_source += "\n" + _feathers_handler_body(files, source_cache, root, route)
        if route.framework in {"django", "drf"}:
            contract_source += "\n" + _django_handler_body(files, source_cache, root, route)
        request_hints: list[str] = []
        response_hints: list[str] = []
        status_codes: list[str] = []
        error_hints: list[str] = []

        if route.framework == "express":
            request_hints.extend(_express_request_hints(contract_source))
            response_hints.extend(_express_response_hints(contract_source))
            status_codes.extend(_status_codes(contract_source, r"\bres\.status\(\s*(\d{3})\s*\)"))
            error_hints.extend(_error_hints(contract_source, ["next(", "throw new", ".catch("]))
        elif route.framework == "fastify":
            request_hints.extend(_fastify_request_hints(contract_source))
            response_hints.extend(_fastify_response_hints(contract_source))
            status_codes.extend(_status_codes(contract_source, r"\b(?:reply|res|this)\.(?:code|status)\(\s*(\d{3})\s*\)"))
            status_codes.extend(_status_codes(contract_source, r"(?m)^\s*(\d{3})\s*:"))
            error_hints.extend(_error_hints(contract_source, ["throw ", "httpErrors.", "reply.callNotFound", ".catch("]))
        elif route.framework == "koa":
            request_hints.extend(_koa_request_hints(contract_source))
            response_hints.extend(_koa_response_hints(contract_source))
            status_codes.extend(_koa_status_codes(contract_source))
            error_hints.extend(_error_hints(contract_source, ["ctx.throw", "ctx.assert", "ValidationError", "throw new", ".catch("]))
        elif route.framework == "hapi":
            request_hints.extend(_hapi_route_config_hints(contract_source))
            request_hints.extend(_hapi_request_hints(contract_source))
            response_hints.extend(_hapi_response_config_hints(contract_source))
            response_hints.extend(_hapi_response_hints(contract_source))
            status_codes.extend(_hapi_status_codes(contract_source))
            error_hints.extend(_error_hints(contract_source, ["Boom.", "constructErrorResponse", "throw new", ".catch("]))
        elif route.framework == "hono":
            if route.kind == "hono-openapi-route":
                request_hints.extend(_hono_openapi_route_request_hints(route))
                response_hints.append("response:openapi.responses")
                status_codes.extend(_response_type_status_codes(route.response_type))
            elif route.response_type == "openapi":
                response_hints.append("response:openapi.document")
            else:
                request_hints.extend(_path_param_hints(route.path, "{", "}"))
                request_hints.extend(_hono_request_hints(contract_source))
                response_hints.extend(_hono_response_hints(contract_source))
                status_codes.extend(_hono_status_codes(contract_source, route))
                error_hints.extend(_error_hints(contract_source, ["throw ", "HTTPException", "c.notFound", "notFound"]))
        elif route.framework == "adonisjs":
            request_hints.extend(_adonis_request_hints(contract_source))
            response_hints.extend(_adonis_response_hints(contract_source))
            status_codes.extend(_adonis_status_codes(contract_source))
            error_hints.extend(_error_hints(contract_source, ["throw ", "findByOrFail", "abort", "session.flashMessages.set"]))
        elif route.framework == "sails":
            request_hints.extend(_sails_request_hints(contract_source))
            response_hints.extend(_sails_response_hints(contract_source))
            status_codes.extend(_sails_status_codes(contract_source))
            error_hints.extend(_sails_error_hints(contract_source))
        elif route.framework == "loopback":
            request_hints.extend(_path_param_hints(route.path, "{", "}"))
            request_hints.extend(_loopback_request_hints(contract_source))
            response_hints.extend(_loopback_response_hints(contract_source, route))
            status_codes.extend(_loopback_status_codes(contract_source))
            error_hints.extend(_error_hints(contract_source, ["HttpErrors", "throw new", "reject(", ".catch("]))
        elif route.framework == "feathers":
            request_hints.extend(_feathers_request_hints(contract_source))
            response_hints.extend(_feathers_response_hints(contract_source))
            error_hints.extend(_error_hints(contract_source, ["ferrors.", "errors.", "throw new", ".catch("]))
        elif route.framework == "strapi":
            request_hints.extend(_strapi_request_hints(route, contract_source))
            response_hints.extend(_strapi_response_hints(route, contract_source))
            status_codes.extend(_status_codes(contract_source, r"\bctx\.status\s*=\s*(\d{3})"))
            error_hints.extend(_error_hints(contract_source, ["ctx.throw", "ApplicationError", "ValidationError", "NotFoundError"]))
        elif route.framework == "fastapi":
            request_hints.extend(_path_param_hints(route.path, "{", "}"))
            request_hints.extend(_fastapi_signature_hints(source, route))
            response_hints.extend(_decorator_hints(source, route, "response_model"))
            status_codes.extend(_decorator_status_codes(source, route))
            error_hints.extend(_error_hints(contract_source, ["HTTPException", "raise "]))
        elif route.framework == "flask":
            request_hints.extend(_path_param_hints(route.path, "<", ">"))
            request_hints.extend(_flask_request_hints(contract_source))
            response_hints.extend(_flask_response_hints(contract_source))
            status_codes.extend(_status_codes(contract_source, r"return\b[\s\S]{0,120},\s*(\d{3})\b"))
            error_hints.extend(_error_hints(contract_source, ["abort(", "raise "]))
        elif route.framework == "sinatra":
            request_hints.extend(_path_param_hints(route.path, "{", "}"))
            request_hints.extend(_sinatra_request_hints(contract_source))
            response_hints.extend(_sinatra_response_hints(contract_source))
            status_codes.extend(_sinatra_status_codes(contract_source))
            error_hints.extend(_error_hints(contract_source, ["halt", "raise "]))
        elif route.framework == "grape":
            response_hints.extend(_grape_response_hints(contract_source))
            status_codes.extend(_grape_status_codes(contract_source))
            error_hints.extend(_error_hints(contract_source, ["error!", "raise"]))
        elif route.framework == "spring":
            request_hints.extend(_spring_request_hints(route))
            response_hints.extend(_nonempty([f"return:{route.response_type}" if route.response_type else ""]))
            status_codes.extend(_status_codes(contract_source, r"@ResponseStatus\s*\(\s*(?:HttpStatus\.)?([A-Z_]+|\d{3})"))
            error_hints.extend(_error_hints(contract_source, ["throw new", "@ExceptionHandler"]))
        elif route.framework == "ktor":
            request_hints.extend(_path_param_hints(route.path, "{", "}"))
            request_hints.extend(_ktor_request_hints(contract_source))
            response_hints.extend(_ktor_response_hints(contract_source))
            status_codes.extend(_ktor_status_codes(contract_source))
            error_hints.extend(_error_hints(contract_source, ["throw ", "BadRequestException", "NotFoundException", "StatusPages"]))
        elif route.framework == "next":
            request_hints.extend(_next_request_hints(contract_source))
            response_hints.extend(_next_response_hints(contract_source))
            status_codes.extend(_status_codes(contract_source, r"status\s*[:=]\s*(\d{3})"))
            error_hints.extend(_error_hints(contract_source, ["throw new", "NextResponse.error", "Response.error"]))
        elif route.framework in {"react-router", "remix"}:
            request_hints.extend(_react_router_request_hints(route, contract_source))
            response_hints.extend(_react_router_response_hints(contract_source))
            status_codes.extend(_react_router_status_codes(contract_source))
            error_hints.extend(_error_hints(contract_source, ["throw new Response", "invariant("]))
        elif route.framework == "nestjs":
            request_hints.extend(_nestjs_request_hints(route, contract_source))
            response_hints.extend(_nestjs_response_hints(route, contract_source))
            status_codes.extend(_nestjs_status_codes(route, contract_source))
            error_hints.extend(_error_hints(contract_source, ["throw new", "HttpException", "NotFoundException", "BadRequestException"]))
        elif route.framework in {"gin", "echo", "chi", "fiber", "go"}:
            request_hints.extend(_go_request_hints(contract_source))
            response_hints.extend(_go_response_hints(contract_source))
            status_codes.extend(_go_status_codes(contract_source))
            error_hints.extend(_error_hints(contract_source, ["Abort(", "AbortWithError(", "panic(", "NewError("]))
        elif route.framework == "axum":
            request_hints.extend(_axum_request_hints(contract_source))
            response_hints.extend(_axum_response_hints(contract_source))
            status_codes.extend(_axum_status_codes(contract_source))
            error_hints.extend(_error_hints(contract_source, ["Error::", "anyhow::", "ok_or(", "bail!("]))
        elif route.framework == "actix-web":
            request_hints.extend(_actix_request_hints(contract_source))
            response_hints.extend(_actix_response_hints(contract_source))
            status_codes.extend(_actix_status_codes(contract_source))
            error_hints.extend(_error_hints(contract_source, ["Error::", "ResponseError", "error_response()", ".from_err()"]))
        elif route.framework == "rocket":
            request_hints.extend(_rocket_request_hints(contract_source, route))
            response_hints.extend(_rocket_response_hints(contract_source))
            status_codes.extend(_rocket_status_codes(contract_source))
            error_hints.extend(_error_hints(contract_source, ["Errors::", "Status::", "?"]))
        elif route.framework == "warp":
            request_hints.extend(_warp_request_hints(contract_source, route))
            response_hints.extend(_warp_response_hints(contract_source))
            status_codes.extend(_warp_status_codes(contract_source))
            error_hints.extend(_error_hints(contract_source, ["ErrorResponse", "StatusCode::", "?"]))
        elif route.framework == "vapor":
            request_hints.extend(_vapor_request_hints(route, contract_source))
            response_hints.extend(_vapor_response_hints(contract_source))
            status_codes.extend(_vapor_status_codes(contract_source))
            error_hints.extend(_error_hints(contract_source, ["Abort", "fatalError", "throw ", "ValidationError"]))
        elif route.framework in {"django", "drf"}:
            request_hints.extend(_path_param_hints(route.path, "<", ">"))
            request_hints.extend(_django_regex_path_hints(route.path))
            request_hints.extend(_django_request_hints(contract_source))
            response_hints.extend(_django_response_hints(contract_source))
            status_codes.extend(_django_status_codes(contract_source))
            error_hints.extend(_error_hints(contract_source, ["Http404", "PermissionDenied", "ValidationError", "raise "]))

        details.append(
            ContractDetailFact(
                method=route.method,
                path=route.path,
                framework=route.framework,
                request_hints=_dedupe(request_hints),
                response_hints=_dedupe(response_hints),
                status_codes=_dedupe(status_codes),
                error_hints=_dedupe(error_hints),
                evidence=route.evidence,
            )
        )

    return details


def build_api_contracts(
    routes: list[ApiRouteFact],
    contract_details: list[ContractDetailFact] | None = None,
) -> list[ApiContractFact]:
    details_by_key = {
        (detail.method, detail.path, detail.framework): detail
        for detail in contract_details or []
    }
    contracts: list[ApiContractFact] = []
    for route in routes:
        detail = details_by_key.get((route.method, route.path, route.framework))
        request_hints = _route_request_hints(route)
        response_hints = _nonempty([f"return:{route.response_type}" if route.response_type else ""])
        status_codes: list[str] = _response_type_status_codes(route.response_type)
        error_hints: list[str] = []
        if detail:
            request_hints.extend(detail.request_hints)
            response_hints.extend(detail.response_hints)
            status_codes.extend(detail.status_codes)
            error_hints.extend(detail.error_hints)
        contracts.append(
            ApiContractFact(
                method=route.method,
                path=route.path,
                handler=route.handler,
                framework=route.framework,
                parameters=route.parameters,
                request_body=route.request_body,
                response_type=route.response_type,
                evidence=route.evidence,
                request_hints=_dedupe(request_hints),
                response_hints=_dedupe(response_hints),
                status_codes=_dedupe(status_codes),
                error_hints=_dedupe(error_hints),
            )
        )
    return contracts


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8", errors="ignore")


def _route_source_window(source: str, route: ApiRouteFact) -> str:
    line = route.evidence.line_start or 1
    lines = source.splitlines()
    start_offset = _offset_for_line(source, line)
    line_end = source.find("\n", start_offset)
    search_offset = start_offset + 1 if line_end < 0 else line_end + 1
    next_marker = _next_route_marker(source, search_offset, route.framework)
    if next_marker is not None:
        nearby = source[start_offset:next_marker]
    else:
        fallback_lines = 8 if route.framework in {"axum", "warp"} else 80
        nearby = "\n".join(lines[max(0, line - 1) : min(len(lines), line + fallback_lines)])
    handler_body = "" if route.framework == "hono" else _handler_body(source, route.handler)
    return nearby + "\n" + handler_body


def _offset_for_line(source: str, line: int) -> int:
    if line <= 1:
        return 0
    offset = 0
    for _ in range(line - 1):
        next_newline = source.find("\n", offset)
        if next_newline < 0:
            return len(source)
        offset = next_newline + 1
    return offset


def _next_route_marker(source: str, offset: int, framework: str) -> int | None:
    if framework == "express":
        pattern = r"\b(?:app|router|server)\.(?:get|post|put|delete|patch|options|head|all)\("
    elif framework == "fastify":
        pattern = r"\b(?:fastify|server|app)\.(?:route|get|post|put|delete|patch|options|head|all)\("
    elif framework in {"fastapi", "flask"}:
        pattern = r"\n\s*@(?:app|router|blueprint|bp)\.(?:get|post|put|delete|patch|options|head|route)\("
    elif framework == "sinatra":
        pattern = r"\n\s*(?:get|post|put|patch|delete|options|head)\s+['\"](?:/|\*)"
    elif framework == "grape":
        pattern = r"\n\s*(?:get|post|put|patch|delete|options|head)(?:\s+[^#\n]+?)?\s+do\b"
    elif framework == "spring":
        pattern = r"\n\s*@(?:GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping)\b"
    elif framework == "ktor":
        pattern = r"\n\s*(?:route|get|post|put|delete|patch|options|head|webSocket)\s*(?:<[^>{}()]+>)?\s*(?:\(|\{)"
    elif framework == "nestjs":
        pattern = r"\n\s*@(?:Get|Post|Put|Delete|Patch|Options|Head)\s*\("
    elif framework == "axum":
        pattern = r"\n\s*\.route\("
    elif framework == "rocket":
        pattern = r"\n\s*#\[\s*(?:get|post|put|delete|patch|head|options)\("
    elif framework == "warp":
        pattern = r"\n\s*\.or\(warp::path!\("
    elif framework == "hapi":
        pattern = r"\n\s*\{\s*\n\s*method\s*:\s*['\"`](?:GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD|ANY)['\"`]"
    elif framework == "hono":
        pattern = r"\n\s*(?:[A-Za-z_$][\w$]*\.)?\.?(?:get|post|put|delete|patch|all|on|doc)\(\s*['\"`]"
    elif framework == "adonisjs":
        pattern = r"\n\s*Route\.(?:get|post|put|patch|delete|options|head|any|resource)\("
    elif framework == "sails":
        pattern = r"\n\s*['\"](?:GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD|ALL)?\s*/"
    elif framework == "loopback":
        pattern = r"\n\s*@(?:get|post|put|patch|del|delete|head|options)\s*\("
    elif framework == "feathers":
        pattern = r"\n\s*app\.use\(\s*['\"`]/"
    elif framework == "strapi":
        pattern = r"\n\s*(?:module\.exports\s*=|createCoreRouter\(|\{\s*method\s*:)"
    elif framework in {"react-router", "remix"}:
        pattern = r"\n\s*export\s+(?:const|async\s+function|function)\s+(?:loader|action)\b"
    else:
        return None
    match = re.search(pattern, source[offset:], re.IGNORECASE)
    return offset + match.start() if match else None


def _handler_body(source: str, handler: str | None) -> str:
    if not handler:
        return ""
    simple = _simple_handler_name(handler)
    go_pattern = re.compile(rf"\bfunc\s+(?:\([^)]*\)\s*)?{re.escape(simple)}\s*\([^)]*\)\s*[^\{{\n]*\{{")
    go_match = go_pattern.search(source)
    if go_match:
        brace = source.find("{", go_match.start())
        end = _find_matching_brace(source, brace)
        start = _leading_comment_start(source, go_match.start())
        return source[start : end + 1] if end is not None else source[start : go_match.start() + 2200]
    rust_match = re.search(
        rf"\b(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+{re.escape(simple)}\b",
        source,
    )
    if rust_match:
        brace = source.find("{", rust_match.end())
        end = _find_matching_brace(source, brace)
        start = _leading_comment_start(source, rust_match.start())
        return source[start : end + 1] if end is not None else source[start : rust_match.start() + 2200]
    swift_body = _swift_function_body(source, simple)
    if swift_body:
        return swift_body
    js_patterns = [
        rf"\b(?:async\s+)?function\s+{re.escape(simple)}\s*\([^)]*\)\s*[^\{{\n]*\{{",
        rf"\bconst\s+{re.escape(simple)}\s*=\s*(?:async\s*)?\([^)]*\)\s*=>\s*[^\{{\n]*\{{",
        rf"\b(?:public|private|protected)?\s*(?:async\s+)?{re.escape(simple)}\s*\([^)]*\)\s*[^\{{\n]*\{{",
    ]
    for pattern in js_patterns:
        match = re.search(pattern, source)
        if match:
            brace = source.rfind("{", match.start(), match.end())
            end = _find_matching_brace(source, brace)
            return source[match.start() : end + 1] if end is not None else source[match.start() : match.start() + 2200]
    python_match = re.search(
        rf"\b(?:async\s+)?def\s+{re.escape(simple)}\s*\([^)]*\)\s*(?:->\s*[^:]+)?\s*:",
        source,
    )
    if python_match:
        return _python_top_level_block(source, python_match.start())
    return ""


def _swift_function_body(source: str, name: str) -> str:
    match = re.search(
        rf"\bfunc\s+{re.escape(name)}\s*\([^)]*\)\s*(?:async\s*)?(?:throws\s*)?(?:->\s*[^\{{\n]+)?\{{",
        source,
    )
    if not match:
        return ""
    brace = source.find("{", match.start())
    end = _find_matching_brace(source, brace)
    start = _leading_comment_start(source, match.start())
    return source[start : end + 1] if end is not None else source[start : match.start() + 2200]


def _simple_handler_name(handler: str) -> str:
    simple = handler.strip().split(".")[-1]
    simple = simple.split("::")[-1]
    return simple.strip()


def _leading_comment_start(source: str, offset: int) -> int:
    line_start = source.rfind("\n", 0, offset) + 1
    cursor = line_start
    while cursor > 0:
        previous_end = cursor - 1
        previous_start = source.rfind("\n", 0, previous_end) + 1
        line = source[previous_start:previous_end].strip()
        if not line.startswith("//") and line:
            break
        if not line:
            break
        cursor = previous_start
    return cursor


def _find_matching_brace(source: str, open_index: int) -> int | None:
    if open_index < 0 or open_index >= len(source):
        return None
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


def _find_matching_delimiter(source: str, open_index: int, open_char: str, close_char: str) -> int | None:
    if open_index < 0 or open_index >= len(source):
        return None
    depth = 0
    for index in range(open_index, len(source)):
        char = source[index]
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return index
    return None


def _go_handler_body(
    files: list[FileFact],
    source_cache: dict[str, str],
    root: Path,
    route: ApiRouteFact,
) -> str:
    if not route.handler or route.handler == "func":
        return ""
    for file_fact in files:
        if file_fact.language != "go" or file_fact.role in {"test", "sample", "generated"}:
            continue
        source = source_cache.setdefault(file_fact.path, _read(root, file_fact.path))
        body = _handler_body(source, route.handler)
        if body:
            return body
    return ""


def _rust_handler_body(
    files: list[FileFact],
    source_cache: dict[str, str],
    root: Path,
    route: ApiRouteFact,
) -> str:
    if not route.handler:
        return ""
    candidates = sorted(
        (
            file_fact
            for file_fact in files
            if file_fact.language == "rust" and file_fact.role not in {"test", "sample", "generated"}
        ),
        key=lambda item: _rust_handler_candidate_score(route.handler or "", item.path),
    )
    for file_fact in candidates:
        source = source_cache.setdefault(file_fact.path, _read(root, file_fact.path))
        body = _handler_body(source, route.handler)
        if body:
            return body
    return ""


def _rust_handler_candidate_score(handler: str, path: str) -> tuple[int, int, str]:
    modules = [part.lower() for part in handler.split("::")[:-1] if part]
    normalized = path.replace("\\", "/").lower()
    if not modules:
        return (10, len(normalized), normalized)
    module_path = "/".join(modules)
    if normalized.endswith(f"{module_path}.rs"):
        return (0, len(normalized), normalized)
    if f"/{module_path}/" in normalized:
        return (1, len(normalized), normalized)
    matched = sum(1 for module in modules if f"/{module}" in normalized or normalized.endswith(f"{module}.rs"))
    return (5 - matched, len(normalized), normalized)


def _swift_handler_body(
    files: list[FileFact],
    source_cache: dict[str, str],
    root: Path,
    route: ApiRouteFact,
) -> str:
    if not route.handler:
        return ""
    candidates = sorted(
        (
            file_fact
            for file_fact in files
            if file_fact.language == "swift" and file_fact.role not in {"test", "sample", "generated"}
        ),
        key=lambda item: _swift_handler_candidate_score(route.handler or "", item.path),
    )
    for file_fact in candidates:
        source = source_cache.setdefault(file_fact.path, _read(root, file_fact.path))
        body = _handler_body(source, route.handler)
        if body:
            return body
    return ""


def _swift_handler_candidate_score(handler: str, path: str) -> tuple[int, int, str]:
    normalized = path.replace("\\", "/").lower()
    owner = handler.split(".", 1)[0].lower() if "." in handler else ""
    score = 20
    if "/controller/" in f"/{normalized}" or "/controllers/" in f"/{normalized}":
        score -= 6
    if owner and owner in normalized:
        score -= 8
    return (score, len(normalized), normalized)


def _javascript_handler_body(
    files: list[FileFact],
    source_cache: dict[str, str],
    root: Path,
    route: ApiRouteFact,
) -> str:
    if not route.handler:
        return ""
    candidates = sorted(
        (
            file_fact
            for file_fact in files
            if file_fact.language in {"javascript", "typescript"} and file_fact.role not in {"test", "sample", "generated"}
        ),
        key=lambda item: _javascript_handler_candidate_score(route, item.path),
    )
    for file_fact in candidates:
        source = source_cache.setdefault(file_fact.path, _read(root, file_fact.path))
        body = _handler_body(source, route.handler)
        if body:
            return body
    return ""


def _javascript_handler_candidate_score(route: ApiRouteFact, path: str) -> tuple[int, int, str]:
    normalized = path.replace("\\", "/").lower()
    evidence = route.evidence.file.replace("\\", "/").lower()
    score = 20
    if "/controllers/" in f"/{normalized}":
        score -= 4
    if normalized.endswith("/handlers.js") or normalized.endswith("/handlers.ts"):
        score -= 4
    evidence_parent = Path(evidence).parent.as_posix()
    if evidence_parent and normalized.startswith(f"{evidence_parent}/"):
        score -= 6
    parent_name = Path(evidence).parent.name.lower()
    if parent_name and f"/{parent_name}/" in f"/{normalized}/":
        score -= 3
    route_stem = Path(evidence).stem.replace("-router", "").replace(".router", "")
    if route_stem and route_stem in normalized:
        score -= 5
    for segment in (route.handler or "").lower().split("."):
        if segment and segment not in {"ctrl", "controller", "handlers"} and segment in normalized:
            score -= 7
    return (score, len(normalized), normalized)


def _sails_handler_body(
    files: list[FileFact],
    source_cache: dict[str, str],
    root: Path,
    route: ApiRouteFact,
) -> str:
    if not route.handler or route.handler == "inline" or route.handler.startswith("view:"):
        return ""
    action_path = f"api/controllers/{route.handler}.js".replace("\\", "/").lower()
    candidates = sorted(
        (
            file_fact
            for file_fact in files
            if file_fact.language == "javascript" and file_fact.role not in {"test", "sample", "generated"}
        ),
        key=lambda item: (0 if item.path.replace("\\", "/").lower().endswith(action_path) else 1, len(item.path)),
    )
    for file_fact in candidates:
        normalized = file_fact.path.replace("\\", "/").lower()
        if not normalized.endswith(action_path):
            continue
        return source_cache.setdefault(file_fact.path, _read(root, file_fact.path))
    return ""


def _feathers_handler_body(
    files: list[FileFact],
    source_cache: dict[str, str],
    root: Path,
    route: ApiRouteFact,
) -> str:
    method = _simple_handler_name(route.handler)
    if not method:
        return ""
    service_source = source_cache.setdefault(route.evidence.file, _read(root, route.evidence.file))
    class_path = _feathers_class_path(root, route.evidence.file, service_source)
    if not class_path:
        return ""
    relative = class_path.relative_to(root).as_posix()
    source = source_cache.setdefault(relative, _read(root, relative))
    body = _handler_body(source, method)
    for helper in re.findall(r"\bthis\.([A-Za-z_$][\w$]*)\s*\(", body):
        if helper == method:
            continue
        helper_body = _handler_body(source, helper)
        if helper_body and helper_body not in body:
            body += "\n" + helper_body
    return body


def _feathers_class_path(root: Path, service_file: str, source: str) -> Path | None:
    match = re.search(r"require\(\s*['\"](?P<path>[^'\"]+\.class(?:\.js|\.ts)?)['\"]\s*\)", source)
    if not match:
        return None
    candidate = (root / Path(service_file).parent / match.group("path")).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate if candidate.exists() else None


def _django_handler_body(
    files: list[FileFact],
    source_cache: dict[str, str],
    root: Path,
    route: ApiRouteFact,
) -> str:
    if not route.handler or route.handler == "include":
        return ""
    handler_name = _django_handler_name(route.handler)
    if not handler_name:
        return ""
    route_file = _django_handler_route_file(route)
    candidates = sorted(
        (
            file_fact
            for file_fact in files
            if file_fact.language == "python" and file_fact.role not in {"test", "sample", "generated"}
        ),
        key=lambda item: _django_handler_candidate_score(route_file, item.path),
    )
    for file_fact in candidates:
        source = source_cache.setdefault(file_fact.path, _read(root, file_fact.path))
        body = _python_handler_or_class_body(source, handler_name)
        if body:
            return body
    return ""


def _django_handler_name(handler: str) -> str | None:
    cleaned = handler.replace(".as_view", "")
    parts = [part for part in cleaned.split(".") if part]
    if not parts:
        return None
    return parts[-1]


def _django_handler_route_file(route: ApiRouteFact) -> str:
    note = route.evidence.note or ""
    child = re.search(r"child=(?P<file>[^:;]+):\d+", note)
    return child.group("file") if child else route.evidence.file


def _django_handler_candidate_score(route_file: str, candidate: str) -> tuple[int, str]:
    route_dir = str(Path(route_file).parent).replace("\\", "/")
    candidate_dir = str(Path(candidate).parent).replace("\\", "/")
    if candidate_dir == route_dir and Path(candidate).name == "views.py":
        return (0, candidate)
    if candidate_dir == route_dir:
        return (1, candidate)
    if Path(candidate).name == "views.py":
        return (2, candidate)
    return (3, candidate)


def _python_handler_or_class_body(source: str, name: str) -> str:
    function_match = re.search(rf"\b(?:async\s+)?def\s+{re.escape(name)}\s*\([^)]*\)\s*(?:->\s*[^:]+)?\s*:", source)
    if function_match:
        return _python_top_level_block(source, function_match.start())
    class_match = re.search(rf"\bclass\s+{re.escape(name)}\b[\s\S]{{0,120}}?:", source)
    if class_match:
        return _python_top_level_block(source, class_match.start())
    return ""


def _python_top_level_block(source: str, start: int, max_chars: int = 2400) -> str:
    window = source[start : start + max_chars]
    next_match = re.search(r"(?m)\n(?=^(?:@|(?:async\s+)?def\s+|class\s+))", window[1:])
    if not next_match:
        return window
    return window[: next_match.start() + 1]


def _express_request_hints(source: str) -> list[str]:
    hints: list[str] = []
    hints.extend(f"path:req.params.{name}" for name in re.findall(r"\breq\.params\.([A-Za-z_$][\w$]*)", source))
    hints.extend(f"query:req.query.{name}" for name in re.findall(r"\breq\.query\.([A-Za-z_$][\w$]*)", source))
    body_props = re.findall(r"\breq\.body\.([A-Za-z_$][\w$]*)", source)
    hints.extend(f"body:req.body.{name}" for name in body_props)
    if "req.body" in source and not body_props:
        hints.append("body:req.body")
    return hints


def _express_response_hints(source: str) -> list[str]:
    hints: list[str] = []
    if "res.json" in source or re.search(r"\bres\.status\([^)]*\)\.json\b", source):
        hints.append("response:res.json")
    if "res.send" in source or re.search(r"\bres\.status\([^)]*\)\.send\b", source):
        hints.append("response:res.send")
    if "res.render" in source:
        hints.append("response:res.render")
    return hints


def _fastify_request_hints(source: str) -> list[str]:
    hints: list[str] = []
    for receiver in ("req", "request"):
        hints.extend(f"path:{receiver}.params.{name}" for name in re.findall(rf"\b{receiver}\.params\.([A-Za-z_$][\w$]*)", source))
        hints.extend(f"path:{receiver}.params.{name}" for name in re.findall(rf"\b{receiver}\.params\[['\"]([^'\"]+)['\"]\]", source))
        hints.extend(f"query:{receiver}.query.{name}" for name in re.findall(rf"\b{receiver}\.query\.([A-Za-z_$][\w$]*)", source))
        hints.extend(f"body:{receiver}.body.{name}" for name in re.findall(rf"\b{receiver}\.body\.([A-Za-z_$][\w$]*)", source))
        if f"{receiver}.body" in source and not any(hint.startswith(f"body:{receiver}.body.") for hint in hints):
            hints.append(f"body:{receiver}.body")
    return hints


def _fastify_response_hints(source: str) -> list[str]:
    hints: list[str] = []
    for receiver in ("reply", "res", "this"):
        for method in ("send", "sendFile", "json", "redirect", "type", "header"):
            if re.search(rf"\b{receiver}\.{method}\s*\(", source) or re.search(
                rf"\b{receiver}\.(?:code|status)\([^)]*\)\.{method}\s*\(",
                source,
            ):
                hints.append(f"response:{receiver}.{method}")
    if re.search(r"\breturn\s+\{", source):
        hints.append("response:return-object")
    return hints


def _koa_request_hints(source: str) -> list[str]:
    hints: list[str] = []
    hints.extend(f"path:ctx.params.{name}" for name in re.findall(r"\bctx\.params\.([A-Za-z_]\w*)", source))
    for destructured in re.findall(r"\b(?:const|let|var)\s*\{([^}]+)\}\s*=\s*ctx\.params\b", source):
        hints.extend(f"path:ctx.params.{name}" for name in _js_destructured_names(destructured))
    hints.extend(f"query:ctx.query.{name}" for name in re.findall(r"\bctx\.query\.([A-Za-z_]\w*)", source))
    for destructured in re.findall(r"\b(?:const|let|var)\s*\{([^}]+)\}\s*=\s*ctx\.query\b", source):
        hints.extend(f"query:ctx.query.{name}" for name in _js_destructured_names(destructured))
    if "ctx.request.body" in source or re.search(r"\b(?:const|let|var)\s*\{\s*body\s*\}\s*=\s*ctx\.request\b", source):
        hints.append("body:ctx.request.body")
    hints.extend(f"body:body.{name}" for name in re.findall(r"\bbody\.([A-Za-z_]\w*)", source))
    if "ctx.state.user" in source or re.search(r"\b(?:const|let|var)\s*\{\s*user\s*\}\s*=\s*ctx\.state\b", source):
        hints.append("auth:ctx.state.user")
    return hints


def _koa_response_hints(source: str) -> list[str]:
    hints: list[str] = []
    if re.search(r"\bctx\.body\s*=", source):
        hints.append("response:ctx.body")
    if re.search(r"\bctx\.redirect\s*\(", source):
        hints.append("response:ctx.redirect")
    return hints


def _koa_status_codes(source: str) -> list[str]:
    codes: list[str] = []
    codes.extend(_status_codes(source, r"\bctx\.status\s*=\s*(\d{3})\b"))
    codes.extend(_status_codes(source, r"\bctx\.assert\([^,\n]+,\s*(\d{3})\b"))
    codes.extend(_status_codes(source, r"\bctx\.assert\([\s\S]{0,180}?,\s*(\d{3})\b"))
    codes.extend(_status_codes(source, r"\bctx\.throw\(\s*(\d{3})\b"))
    return codes


def _hono_request_hints(source: str) -> list[str]:
    hints: list[str] = []
    hints.extend(f"path:c.req.param.{name}" for name in re.findall(r"\bc\.req\.param\(\s*['\"`]([^'\"`]+)['\"`]\s*\)", source))
    hints.extend(f"query:c.req.query.{name}" for name in re.findall(r"\bc\.req\.query\(\s*['\"`]([^'\"`]+)['\"`]\s*\)", source))
    if re.search(r"\bc\.req\.json(?:\s*<[^>]+>)?\s*\(", source):
        hints.append("body:c.req.json")
    for target, hint in {
        "param": "path:c.req.valid.param",
        "query": "query:c.req.valid.query",
        "json": "body:c.req.valid.json",
        "form": "body:c.req.valid.form",
    }.items():
        if re.search(rf"\bc\.req\.valid\(\s*['\"`]{target}['\"`]\s*\)", source):
            hints.append(hint)
    if re.search(r"\brequest\s*:\s*\{[\s\S]{0,1200}?\bbody\s*:", source):
        hints.append("body:openapi.request.body")
    if re.search(r"\brequest\s*:\s*\{[\s\S]{0,1200}?\bparams\s*:", source):
        hints.append("path:openapi.request.params")
    if re.search(r"\brequest\s*:\s*\{[\s\S]{0,1200}?\bquery\s*:", source):
        hints.append("query:openapi.request.query")
    return hints


def _hono_openapi_route_request_hints(route: ApiRouteFact) -> list[str]:
    hints: list[str] = []
    if route.parameters:
        hints.append("path:openapi.request.params")
    if route.request_body:
        hints.append("body:openapi.request.body")
    return hints


def _hono_response_hints(source: str) -> list[str]:
    hints: list[str] = []
    if re.search(r"\bc\.json\s*\(", source):
        hints.append("response:c.json")
    if re.search(r"\bc\.text\s*\(", source):
        hints.append("response:c.text")
    if re.search(r"\bScalar\s*\(", source):
        hints.append("response:scalar-api-reference")
    if re.search(r"\bresponses\s*:", source):
        hints.append("response:openapi.responses")
    return hints


def _hono_status_codes(source: str, route: ApiRouteFact) -> list[str]:
    codes: list[str] = []
    codes.extend(_response_type_status_codes(route.response_type))
    if codes:
        return _dedupe(codes)
    codes.extend(_status_codes(source, r"\bc\.status\(\s*(\d{3})\s*\)"))
    codes.extend(_status_codes(source, r"\bc\.(?:json|text)\([^)]*,\s*(\d{3})\s*\)"))
    codes.extend(_named_http_status_codes(source))
    codes.extend(re.findall(r"(?:^|[\s,{\[])([1-5]\d\d)\s*[]}]?\s*:", source))
    return _dedupe(codes)


def _hapi_route_config_hints(source: str) -> list[str]:
    hints: list[str] = []
    for auth in re.findall(r"\bauth\s*:\s*['\"`]([^'\"`]+)['\"`]", source):
        hints.append(f"auth:{auth}")
    for validate in re.findall(r"\bvalidate\s*:\s*([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)", source):
        hints.append(f"validate:{validate}")
    return hints


def _hapi_response_config_hints(source: str) -> list[str]:
    hints: list[str] = []
    for response in re.findall(r"\bresponse\s*:\s*([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)", source):
        hints.append(f"response-schema:{response}")
    return hints


def _hapi_request_hints(source: str) -> list[str]:
    hints: list[str] = []
    hints.extend(f"path:request.params.{name}" for name in re.findall(r"\brequest\.params\.([A-Za-z_]\w*)", source))
    for destructured in re.findall(r"\b(?:const|let|var)\s*\{([^}]+)\}\s*=\s*request\.params\b", source):
        hints.extend(f"path:request.params.{name}" for name in _js_destructured_names(destructured))
    hints.extend(f"query:request.query.{name}" for name in re.findall(r"\brequest\.query\.([A-Za-z_]\w*)", source))
    for destructured in re.findall(r"\b(?:const|let|var)\s*\{([^}]+)\}\s*=\s*request\.query\b", source):
        hints.extend(f"query:request.query.{name}" for name in _js_destructured_names(destructured))
    if "request.payload" in source:
        hints.append("body:request.payload")
    hints.extend(f"body:payload.{name}" for name in re.findall(r"\bpayload\.([A-Za-z_]\w*)", source))
    if "request.auth.credentials" in source:
        hints.append("auth:request.auth.credentials")
    return hints


def _hapi_response_hints(source: str) -> list[str]:
    hints: list[str] = []
    if re.search(r"\breply\s*\(", source):
        hints.append("response:reply")
    if re.search(r"\breply\s*\([^)]*\)\.code\s*\(", source, re.DOTALL):
        hints.append("response:reply.code")
    return hints


def _hapi_status_codes(source: str) -> list[str]:
    return _status_codes(source, r"\breply\s*\([^)]*\)\.code\(\s*(\d{3})\s*\)")


def _adonis_request_hints(source: str) -> list[str]:
    hints: list[str] = []
    hints.extend(f"path:request.param.{name}" for name in re.findall(r"\brequest\.param\(\s*['\"`]([^'\"`]+)['\"`]", source))
    hints.extend(f"body:request.input.{name}" for name in re.findall(r"\brequest\.input\(\s*['\"`]([^'\"`]+)['\"`]", source))
    hints.extend(f"body:request.only.{name}" for names in re.findall(r"\brequest\.only\(\s*\[([^\]]+)\]", source) for name in _quoted_items(names))
    for validator in re.findall(r"\brequest\.validate\(\s*([A-Za-z_$][\w$]*)", source):
        hints.append(f"validate:{validator}")
    if re.search(r"\brequest\.qs\(\s*\)", source):
        hints.append("query:request.qs")
    if "auth.user" in source:
        hints.append("auth:auth.user")
    return hints


def _adonis_response_hints(source: str) -> list[str]:
    hints: list[str] = []
    for view in re.findall(r"\bview\.render\(\s*['\"`]([^'\"`]+)['\"`]", source):
        hints.append(f"view:{view}")
    if re.search(r"\bresponse\.redirect\(\)", source):
        hints.append("response:redirect")
    for target in re.findall(r"\btoRoute\(\s*['\"`]([^'\"`]+)['\"`]", source):
        hints.append(f"redirect-route:{target}")
    for target in re.findall(r"\btoPath\(\s*['\"`]([^'\"`]+)['\"`]", source):
        hints.append(f"redirect-path:{target}")
    if re.search(r"\bresponse\.(?:send|json)\s*\(", source):
        hints.append("response:body")
    return hints


def _adonis_status_codes(source: str) -> list[str]:
    codes: list[str] = []
    codes.extend(_status_codes(source, r"\bresponse\.status\(\s*(\d{3})\s*\)"))
    status_map = {
        "created": "201",
        "noContent": "204",
        "badRequest": "400",
        "unauthorized": "401",
        "forbidden": "403",
        "notFound": "404",
    }
    for method in re.findall(r"\bresponse\.(created|noContent|badRequest|unauthorized|forbidden|notFound)\b", source):
        codes.append(status_map[method])
    return codes


def _sails_request_hints(source: str) -> list[str]:
    hints: list[str] = []
    hints.extend(_sails_input_hints(source))
    hints.extend(f"body:inputs.{name}" for name in re.findall(r"\binputs\.([A-Za-z_$][\w$]*)", source))
    hints.extend(f"path:req.param.{name}" for name in re.findall(r"\breq\.param\(\s*['\"`]([^'\"`]+)['\"`]", source))
    hints.extend(f"query:req.query.{name}" for name in re.findall(r"\breq\.query\.([A-Za-z_$][\w$]*)", source))
    if "req.allParams()" in source:
        hints.append("request:req.allParams")
    if "req.body" in source:
        hints.append("body:req.body")
    if re.search(r"\b(?:req|this\.req)\.me\b", source):
        hints.append("auth:req.me")
    return hints


def _sails_response_hints(source: str) -> list[str]:
    hints: list[str] = []
    for view in re.findall(r"\b(?:res|response)\.view\(\s*['\"`]([^'\"`]+)['\"`]", source):
        hints.append(f"view:{view}")
    if "exits.success" in source:
        hints.append("response:exits.success")
    hints.extend(f"response-exit:{name}" for name in re.findall(r"\bexits\.([A-Za-z_$][\w$]*)", source) if name != "success")
    hints.extend(f"response-type:{name}" for name in re.findall(r"\bresponseType\s*:\s*['\"`]([^'\"`]+)['\"`]", source))
    if re.search(r"\bres\.json\s*\(", source):
        hints.append("response:res.json")
    if re.search(r"\bres\.send\s*\(", source):
        hints.append("response:res.send")
    return hints


def _sails_status_codes(source: str) -> list[str]:
    return _status_codes(source, r"\bres\.status\(\s*(\d{3})\s*\)")


def _sails_error_hints(source: str) -> list[str]:
    hints = _error_hints(source, ["throw ", ".intercept(", "exits.error", "badEntity"])
    for exit_name in re.findall(r"\bexits\.([A-Za-z_$][\w$]*)", source):
        if exit_name != "success":
            hints.append(f"error-exit:{exit_name}")
    for exit_name in _sails_configured_exit_names(source):
        if exit_name not in {"success", "error"}:
            hints.append(f"error-exit:{exit_name}")
    return hints


def _sails_configured_exit_names(source: str) -> list[str]:
    open_match = re.search(r"\bexits\s*:\s*\{", source)
    if not open_match:
        return []
    open_index = source.find("{", open_match.start())
    close_index = _find_matching_brace(source, open_index)
    if close_index is None:
        return []
    body = source[open_index + 1 : close_index]
    names: list[str] = []
    for item in _split_js_top_level_commas(body):
        if ":" not in item:
            continue
        name = item.split(":", 1)[0].strip().strip("'\"`")
        if re.fullmatch(r"[A-Za-z_$][\w$]*", name):
            names.append(name)
    return names


def _sails_input_hints(source: str) -> list[str]:
    open_match = re.search(r"\binputs\s*:\s*\{", source)
    if not open_match:
        return []
    open_index = source.find("{", open_match.start())
    close_index = _find_matching_brace(source, open_index)
    if close_index is None:
        return []
    body = source[open_index + 1 : close_index]
    hints: list[str] = []
    for item in _split_js_top_level_commas(body):
        if ":" not in item:
            continue
        name, config = item.split(":", 1)
        input_name = name.strip().strip("'\"`")
        if not re.fullmatch(r"[A-Za-z_$][\w$]*", input_name):
            continue
        type_match = re.search(r"\btype\s*:\s*['\"`]([^'\"`]+)['\"`]", config)
        required = " required" if re.search(r"\brequired\s*:\s*true\b", config) else ""
        type_hint = f":{type_match.group(1)}" if type_match else ""
        hints.append(f"body:input.{input_name}{type_hint}{required}")
    return hints


def _loopback_request_hints(source: str) -> list[str]:
    hints: list[str] = []
    for scope, decorator in [
        ("path", "path"),
        ("query", "query"),
        ("header", "header"),
        ("cookie", "cookie"),
        ("body", "body"),
    ]:
        pattern = rf"@param\.{decorator}(?:\.(?P<type>[A-Za-z_$][\w$]*))?\(\s*['\"`](?P<name>[^'\"`]+)['\"`]"
        for match in re.finditer(pattern, source):
            type_hint = f":{match.group('type')}" if match.group("type") else ""
            hints.append(f"{scope}:{match.group('name')}{type_hint}")
    if "@requestBody" in source:
        hints.append("body:requestBody")
    for model in re.findall(r"\bgetModelSchemaRef\(\s*(?P<model>[A-Za-z_$][\w$]*)", source):
        if "@requestBody" in source:
            hints.append(f"body-schema:{model}")
    for model in re.findall(r"\bgetFilterSchemaFor\(\s*(?P<model>[A-Za-z_$][\w$]*)", source):
        hints.append(f"query-filter:{model}")
    for model in re.findall(r"\bgetWhereSchemaFor\(\s*(?P<model>[A-Za-z_$][\w$]*)", source):
        hints.append(f"query-where:{model}")
    for strategy in re.findall(r"@authenticate\(\s*['\"`]([^'\"`]+)['\"`]", source):
        hints.append(f"auth:{strategy}")
    roles = re.search(r"allowedRoles\s*:\s*\[(?P<roles>[^\]]+)\]", source)
    if roles:
        for role in re.findall(r"['\"`]([^'\"`]+)['\"`]", roles.group("roles")):
            hints.append(f"authz-role:{role}")
    return hints


def _loopback_response_hints(source: str, route: ApiRouteFact) -> list[str]:
    hints: list[str] = []
    if route.response_type:
        hints.append(f"return:{route.response_type}")
    for model in re.findall(r"\bgetModelSchemaRef\(\s*(?P<model>[A-Za-z_$][\w$]*)", source):
        hints.append(f"response-schema:{model}")
    if "CountSchema" in source:
        hints.append("response-schema:CountSchema")
    for repository, method in re.findall(r"\bthis\.([A-Za-z_$][\w$]*Repository)\.([A-Za-z_$][\w$]*)\s*\(", source):
        hints.append(f"repository:{repository}.{method}")
    if re.search(r"\breturn\s+\{", source):
        hints.append("response:return-object")
    return hints


def _loopback_status_codes(source: str) -> list[str]:
    return _dedupe(re.findall(r"['\"]?(?P<code>[1-5]\d\d)['\"]?\s*:", source))


def _feathers_request_hints(source: str) -> list[str]:
    hints: list[str] = []
    for receiver in ("params", "context.params"):
        hints.extend(f"query:{receiver}.query.{name}" for name in re.findall(rf"\b{re.escape(receiver)}\.query\.([A-Za-z_$][\w$]*)", source))
        hints.extend(f"path:{receiver}.route.{name}" for name in re.findall(rf"\b{re.escape(receiver)}\.route\.([A-Za-z_$][\w$]*)", source))
        hints.extend(f"auth:{receiver}.user" for _ in re.findall(rf"\b{re.escape(receiver)}\.user\b", source))
    hints.extend(f"body:data.{name}" for name in re.findall(r"\bdata\.([A-Za-z_$][\w$]*)", source))
    if re.search(r"\basync\s+(?:create|update|patch)\s*\(\s*data\b", source):
        hints.append("body:data")
    if "context.data" in source:
        hints.append("body:context.data")
    return hints


def _feathers_response_hints(source: str) -> list[str]:
    hints: list[str] = []
    for service, method in re.findall(r"\b(?:this\.)?app\.service\(\s*['\"`]([^'\"`]+)['\"`]\s*\)\.([A-Za-z_$][\w$]*)\s*\(", source):
        hints.append(f"service-call:{service}.{method}")
    if re.search(r"\breturn\s+\{", source):
        hints.append("response:return-object")
    if re.search(r"\breturn\s+(?:await\s+)?(?:this\.)?app\.service", source):
        hints.append("response:service-call")
    return hints


def _strapi_request_hints(route: ApiRouteFact, source: str) -> list[str]:
    hints: list[str] = []
    if route.method == "GET":
        hints.extend(["query:filters", "query:sort", "query:pagination", "query:populate"])
        if "i18n" in source or "locale" in source:
            hints.append("query:locale")
        if "draftAndPublish" in source or "publicationState" in source:
            hints.append("query:publicationState")
    if route.request_body:
        hints.append(f"body:{route.request_body}")
    for name in re.findall(r"\bctx\.params\.([A-Za-z_$][\w$]*)", source):
        hints.append(f"path:{name}")
    for name in re.findall(r"\bctx\.query\.([A-Za-z_$][\w$]*)", source):
        hints.append(f"query:{name}")
    for name in re.findall(r"\bctx\.request\.body\.([A-Za-z_$][\w$]*)", source):
        hints.append(f"body:{name}")
    return hints


def _strapi_response_hints(route: ApiRouteFact, source: str) -> list[str]:
    hints: list[str] = []
    if route.response_type:
        hints.append(f"return:{route.response_type}")
    if "createCoreRouter" in source:
        hints.append("response:strapi-core-entity")
    for service, method in re.findall(r"\bstrapi\.service\(\s*['\"`]([^'\"`]+)['\"`]\s*\)\.([A-Za-z_$][\w$]*)\s*\(", source):
        hints.append(f"service-call:{service}.{method}")
    for action, uid in re.findall(r"\bstrapi\.entityService\.([A-Za-z_$][\w$]*)\s*\(\s*['\"`]([^'\"`]+)['\"`]", source):
        hints.append(f"entity-service:{action}:{uid}")
    if re.search(r"\bctx\.body\s*=", source):
        hints.append("response:ctx.body")
    return hints


def _js_destructured_names(source: str) -> list[str]:
    names: list[str] = []
    for item in source.split(","):
        name = item.strip().split(":", 1)[0].strip()
        if re.fullmatch(r"[A-Za-z_$][\w$]*", name):
            names.append(name)
    return names


def _quoted_items(source: str) -> list[str]:
    return re.findall(r"['\"`]([^'\"`]+)['\"`]", source)


def _split_js_top_level_commas(source: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depths = {"{": 0, "[": 0, "(": 0}
    closing = {"}": "{", "]": "[", ")": "("}
    quote: str | None = None
    escaped = False
    for index, char in enumerate(source):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"', "`"}:
            quote = char
            continue
        if char in depths:
            depths[char] += 1
        elif char in closing:
            depths[closing[char]] = max(0, depths[closing[char]] - 1)
        elif char == "," and not any(depths.values()):
            part = source[start:index].strip()
            if part:
                parts.append(part)
            start = index + 1
    tail = source[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def _fastapi_signature_hints(source: str, route: ApiRouteFact) -> list[str]:
    if not route.handler:
        return []
    pattern = re.compile(rf"(?:async\s+)?def\s+{re.escape(route.handler)}\s*\((?P<params>[^)]*)\)")
    match = pattern.search(source)
    if not match:
        return []
    path_params = set(_path_param_names(route.path, "{", "}"))
    hints: list[str] = []
    for raw in _split_params(match.group("params")):
        clean = raw.strip()
        if not clean or clean in {"self", "request"}:
            continue
        name = clean.split(":", 1)[0].split("=", 1)[0].strip()
        annotation = clean.split(":", 1)[1].split("=", 1)[0].strip() if ":" in clean else ""
        if name in path_params:
            hints.append(f"path:{name}{':' + annotation if annotation else ''}")
        elif _looks_like_body_annotation(annotation):
            hints.append(f"body:{name}:{annotation}")
        else:
            hints.append(f"query:{name}{':' + annotation if annotation else ''}")
    return hints


def _looks_like_body_annotation(annotation: str) -> bool:
    if not annotation:
        return False
    if "Body(" in annotation:
        return True
    clean = annotation.replace("None", "").replace("Optional", "").replace("[", " ").replace("]", " ")
    tokens = [token.strip() for token in re.split(r"[|,\s]+", clean) if token.strip()]
    if not tokens:
        return False
    if all(token in PRIMITIVE_TYPES for token in tokens):
        return False
    return any(token[:1].isupper() and token not in PRIMITIVE_TYPES for token in tokens)


def _decorator_hints(source: str, route: ApiRouteFact, keyword: str) -> list[str]:
    decorator = _matching_python_route_decorator(source, route)
    if not decorator:
        return []
    match = re.search(rf"\b{keyword}\s*=\s*([A-Za-z_][\w.]*)", decorator)
    return [f"{keyword}:{match.group(1)}"] if match else []


def _decorator_status_codes(source: str, route: ApiRouteFact) -> list[str]:
    decorator = _matching_python_route_decorator(source, route)
    if not decorator:
        return []
    return _status_codes(decorator, r"\bstatus_code\s*=\s*(\d{3}|status\.HTTP_\d{3}_[A-Z_]+)")


def _matching_python_route_decorator(source: str, route: ApiRouteFact) -> str | None:
    method = route.method.lower()
    pattern = re.compile(
        rf"@(?:app|router|[A-Za-z_]\w*)\.{re.escape(method)}\(\s*['\"]{re.escape(route.path)}['\"](?P<args>[^)]*)\)",
        re.DOTALL,
    )
    match = pattern.search(source)
    if match:
        return match.group(0)
    if not route.handler:
        return None
    return _python_handler_decorator_block(source, route.handler, method)


def _python_handler_decorator_block(source: str, handler: str, method: str) -> str | None:
    function_match = re.search(rf"(?m)^\s*(?:async\s+)?def\s+{re.escape(handler)}\s*\(", source)
    if not function_match:
        return None
    prefix = source[: function_match.start()]
    decorator_start = prefix.rfind("@")
    if decorator_start < 0:
        return None
    block = prefix[decorator_start:].strip()
    if re.search(rf"@\s*(?:app|router|[A-Za-z_]\w*)\.{re.escape(method)}\s*\(", block, re.IGNORECASE):
        return block
    return None


def _flask_request_hints(source: str) -> list[str]:
    hints: list[str] = []
    hints.extend(f"query:request.args.{name}" for name in re.findall(r"\brequest\.args\.get\(\s*['\"]([^'\"]+)['\"]", source))
    if "request.args" in source and not hints:
        hints.append("query:request.args")
    if "request.json" in source:
        hints.append("body:request.json")
    if "request.get_json" in source:
        hints.append("body:request.get_json")
    return hints


def _flask_response_hints(source: str) -> list[str]:
    hints: list[str] = []
    if "jsonify(" in source:
        hints.append("response:jsonify")
    if re.search(r"\breturn\s+render_template\(", source):
        hints.append("response:render_template")
    return hints


def _sinatra_request_hints(source: str) -> list[str]:
    hints: list[str] = []
    hints.extend(f"param:params.{name}" for name in re.findall(r"\bparams\[\s*['\"]([^'\"]+)['\"]\s*\]", source))
    hints.extend(f"param:params.{name}" for name in re.findall(r"\bparams\[\s*:([A-Za-z_]\w*)\s*\]", source))
    if re.search(r"\bparams\b", source) and not hints:
        hints.append("param:params")
    return hints


def _sinatra_response_hints(source: str) -> list[str]:
    hints: list[str] = []
    if ".to_json" in source:
        hints.append("return:json")
    if re.search(r"\bcontent_type\s+:json\b", source):
        hints.append("content-type:json")
    if re.search(r"\bcontent_type\s+:html\b", source):
        hints.append("content-type:html")
    if re.search(r"\bsend_file\s+", source):
        hints.append("response:send_file")
    return hints


def _sinatra_status_codes(source: str) -> list[str]:
    codes: list[str] = []
    codes.extend(re.findall(r"\bhalt\s+(\d{3})\b", source))
    codes.extend(re.findall(r"\bstatus\s+(\d{3})\b", source))
    return codes


def _grape_response_hints(source: str) -> list[str]:
    hints: list[str] = []
    if re.search(r"\bpresent\b", source):
        hints.append("response:present")
    if re.search(r"\bheader\s+['\"]", source):
        hints.append("response:header")
    if re.search(r"\bcontent_type\s+", source):
        hints.append("response:content_type")
    if "env['api.format'] = :binary" in source or 'env["api.format"] = :binary' in source:
        hints.append("return:binary")
    return hints


def _grape_status_codes(source: str) -> list[str]:
    codes: list[str] = []
    codes.extend(re.findall(r"\bstatus\s+(\d{3})\b", source))
    codes.extend(re.findall(r"\berror!\s*\([^,\n]+,\s*(\d{3})\b", source))
    codes.extend(re.findall(r"\bRack::Response\.new\([\s\S]{0,160}?,\s*(\d{3})\b", source))
    return codes


def _spring_request_hints(route: ApiRouteFact) -> list[str]:
    hints = [f"{param.source}:{param.name}{':' + param.type if param.type else ''}" for param in route.parameters]
    if route.request_body:
        hints.append(f"body:{route.request_body}")
    return hints


def _ktor_request_hints(source: str) -> list[str]:
    hints: list[str] = []
    hints.extend(f"body:{name}" for name in re.findall(r"\bcall\.receive\s*<\s*([A-Za-z_][\w.<>, ?]*)\s*>", source))
    if "call.receiveMultipart(" in source:
        hints.append("body:multipart")
    if "call.receiveParameters(" in source:
        hints.append("form:Parameters")
    if "call.receiveText(" in source:
        hints.append("body:text")
    hints.extend(f"query:{name}" for name in re.findall(r"\bcall\.request\.queryParameters\[\s*['\"]([^'\"]+)['\"]\s*\]", source))
    hints.extend(f"query:{name}" for name in re.findall(r"\bcall\.request\.queryParameters\.get\(\s*['\"]([^'\"]+)['\"]", source))
    hints.extend(f"path:{name}" for name in re.findall(r"\bcall\.parameters\[\s*['\"]([^'\"]+)['\"]\s*\]", source))
    hints.extend(f"path:{name}" for name in re.findall(r"\bcall\.parameters\.get\(\s*['\"]([^'\"]+)['\"]", source))
    return hints


def _ktor_response_hints(source: str) -> list[str]:
    hints: list[str] = []
    hints.extend(f"response:{name}" for name in re.findall(r"\bcall\.respond\s*<\s*([A-Za-z_][\w.<>, ?]*)\s*>", source))
    for method, label in [
        ("respondHtml", "html"),
        ("respondText", "text"),
        ("respondRedirect", "redirect"),
        ("respondFile", "file"),
        ("respondBytes", "bytes"),
    ]:
        if f"call.{method}" in source:
            hints.append(f"response:{label}")
    if "call.respond(" in source:
        hints.append("response:respond")
    return hints


def _ktor_status_codes(source: str) -> list[str]:
    codes = re.findall(r"\bHttpStatusCode\.([A-Za-z_][A-Za-z0-9_]*)", source)
    codes.extend(re.findall(r"\bstatus\s*=\s*HttpStatusCode\.([A-Za-z_][A-Za-z0-9_]*)", source))
    return codes


def _next_request_hints(source: str) -> list[str]:
    hints: list[str] = []
    if ".json()" in source or "request.json" in source:
        hints.append("body:request.json")
    hints.extend(f"query:req.query.{name}" for name in re.findall(r"\breq\.query\.([A-Za-z_$][\w$]*)", source))
    if "searchParams" in source:
        hints.append("query:searchParams")
    return hints


def _next_response_hints(source: str) -> list[str]:
    hints: list[str] = []
    if "NextResponse.json" in source:
        hints.append("response:NextResponse.json")
    if "Response.json" in source:
        hints.append("response:Response.json")
    if "res.json" in source:
        hints.append("response:res.json")
    return hints


def _react_router_request_hints(route: ApiRouteFact, source: str) -> list[str]:
    hints = [f"{param.source}:{param.name}{':' + param.type if param.type else ''}" for param in route.parameters]
    if route.request_body:
        hints.append(f"body:{route.request_body}")
    hints.extend(f"path:{name}" for name in re.findall(r"\bparams\.([A-Za-z_$][\w$]*)", source))
    if "request.formData" in source:
        hints.append("body:formData")
    hints.extend(f"form:{name}" for name in re.findall(r"\bformData\.get\(\s*['\"`]([^'\"`]+)['\"`]", source))
    hints.extend(f"query:{name}" for name in re.findall(r"\bsearchParams\.get\(\s*['\"`]([^'\"`]+)['\"`]", source))
    if "requireUserId(request)" in source:
        hints.append("auth:requireUserId")
    if "getUserId(request)" in source:
        hints.append("auth:getUserId")
    return hints


def _react_router_response_hints(source: str) -> list[str]:
    hints: list[str] = []
    if re.search(r"\bjson\s*\(", source):
        hints.append("response:json")
    if re.search(r"\bredirect\s*\(", source):
        hints.append("response:redirect")
    if re.search(r"\bnew\s+Response\s*\(", source):
        hints.append("response:Response")
    for name in _model_import_names(source):
        if re.search(rf"\b{re.escape(name)}\s*\(", source):
            hints.append(f"model-call:{name}")
    for name in _server_call_names(source):
        prefix = "model-call" if re.match(r"^(?:get|find|create|update|delete|remove)[A-Z]", name) else "server-call"
        hints.append(f"{prefix}:{name}")
    return hints


def _react_router_status_codes(source: str) -> list[str]:
    codes: list[str] = []
    codes.extend(_status_codes(source, r"\bstatus\s*:\s*(\d{3})"))
    codes.extend(_status_codes(source, r"\bnew\s+Response\([^)]*\{[^}]*status\s*:\s*(\d{3})"))
    if re.search(r"\bredirect\s*\(", source):
        codes.append("302")
    return _dedupe(codes)


def _model_import_names(source: str) -> list[str]:
    names: list[str] = []
    for match in re.finditer(r"import\s+\{(?P<names>[^}]+)\}\s+from\s+['\"]~?/models/[^'\"]+['\"]", source):
        for raw_name in match.group("names").split(","):
            name = raw_name.strip().split(" as ", 1)[0].strip()
            if re.fullmatch(r"[A-Za-z_$][\w$]*", name):
                names.append(name)
    return _dedupe(names)


def _server_call_names(source: str) -> list[str]:
    ignored = {
        "json",
        "redirect",
        "invariant",
        "requireUserId",
        "getUserId",
        "Response",
        "URL",
        "get",
    }
    names: list[str] = []
    for name in re.findall(r"(?<!\.)\b([a-z][A-Za-z0-9_]*)\s*\(", source):
        if name in ignored or name.startswith(("use", "set")):
            continue
        if re.match(r"^(?:get|find|create|update|delete|remove|logout|login|register|validate)[A-Z]?", name):
            names.append(name)
    return _dedupe(names)


def _nestjs_request_hints(route: ApiRouteFact, source: str) -> list[str]:
    hints = [f"{param.source}:{param.name}{':' + param.type if param.type else ''}" for param in route.parameters]
    if route.request_body:
        hints.append(f"body:{route.request_body}")
    if "@UseGuards" in source:
        hints.append("auth:@UseGuards")
    return hints


def _nestjs_response_hints(route: ApiRouteFact, source: str) -> list[str]:
    hints: list[str] = []
    if route.response_type:
        hints.append(f"return:{route.response_type}")
    for service, method in re.findall(r"\bthis\.([A-Za-z_$][\w$]*Service)\.([A-Za-z_$][\w$]*)\s*\(", source):
        hints.append(f"service-call:{service}.{method}")
    if re.search(r"\breturn\s+this\.[A-Za-z_$][\w$]*Service\.", source):
        hints.append("response:service-call")
    return hints


def _nestjs_status_codes(route: ApiRouteFact, source: str) -> list[str]:
    codes = _status_codes(source, r"@HttpCode\(\s*(\d{3})\s*\)")
    response_map = {
        "ApiOkResponse": "200",
        "ApiCreatedResponse": "201",
        "ApiAcceptedResponse": "202",
        "ApiNoContentResponse": "204",
        "ApiBadRequestResponse": "400",
        "ApiUnauthorizedResponse": "401",
        "ApiForbiddenResponse": "403",
        "ApiNotFoundResponse": "404",
        "ApiConflictResponse": "409",
    }
    for decorator, code in response_map.items():
        if f"@{decorator}" in source:
            codes.append(code)
    if not codes:
        if route.method == "POST":
            codes.append("201")
        elif route.method != "ANY":
            codes.append("200")
    return _dedupe(codes)


def _go_request_hints(source: str) -> list[str]:
    hints: list[str] = []
    for match in re.finditer(r"//\s*@Param\s+(?P<name>\w+)\s+(?P<source>path|query|body|formData|header)\s+(?P<type>[^\s]+)", source):
        hints.append(f"{match.group('source')}:{match.group('name')}:{match.group('type')}")
    hints.extend(f"path:{name}" for name in re.findall(r"\bc\.Param\(\s*['\"]([^'\"]+)['\"]", source))
    hints.extend(f"query:{name}" for name in re.findall(r"\bc\.(?:Query|DefaultQuery)\(\s*['\"]([^'\"]+)['\"]", source))
    for match in re.finditer(r"\bc\.(?:ShouldBindJSON|BindJSON|ShouldBind|Bind)\(\s*&?(?P<name>[A-Za-z_]\w*)", source):
        hints.append(f"body:{match.group('name')}")
    for match in re.finditer(r"\bc\.BodyParser\(\s*&?(?P<name>[A-Za-z_]\w*)", source):
        hints.append(f"body:{match.group('name')}")
    for match in re.finditer(r"\b(?P<name>[A-Za-z_]\w*)\.Bind\(\s*c\s*\)", source):
        hints.append(f"body:{match.group('name')}.Bind(c)")
    for match in re.finditer(r"\b(?P<name>[A-Za-z_]\w*)\.bind\(\s*c\b", source):
        hints.append(f"body:{match.group('name')}.bind(c)")
    if "common.Bind(c" in source:
        hints.append("body:common.Bind(c)")
    return hints


def _go_response_hints(source: str) -> list[str]:
    hints: list[str] = []
    for method in ("JSON", "XML", "String", "Data", "File", "HTML"):
        if re.search(rf"\bc\.{method}\s*\(", source) or re.search(rf"\bc\.Status\([^)]*\)\.{method}\s*\(", source):
            hints.append(f"response:c.{method}")
    hints.extend(f"response-key:{name}" for name in re.findall(r"gin\.H\s*\{[^}]*['\"]([^'\"]+)['\"]\s*:", source))
    hints.extend(
        f"swagger-success:{code}:{schema}"
        for code, schema in re.findall(r"//\s*@Success\s+(\d{3})\s+\{[^}]+\}\s+([A-Za-z0-9_.\[\]{}]+)", source)
    )
    return hints


def _go_status_codes(source: str) -> list[str]:
    codes: list[str] = []
    codes.extend(re.findall(r"\bhttp\.(Status[A-Za-z0-9_]+)", source))
    codes.extend(re.findall(r"\bc\.(?:JSON|XML|String|Data|HTML|AbortWithStatus|AbortWithError)\(\s*(\d{3})\b", source))
    codes.extend(re.findall(r"//\s*@(?:Success|Failure)\s+(\d{3})\b", source))
    return codes


def _axum_request_hints(source: str) -> list[str]:
    hints: list[str] = []
    params = _rust_function_params(source) or source
    path_extractors = re.findall(r"\bPath\(\s*\(([^)]*)\)\s*\)\s*:\s*Path<([^>\n]+)>", params)
    path_extractors.extend(re.findall(r"\bPath\((?!\s*\()([^)]*)\)\s*:\s*Path<([^>\n]+)>", params))
    for binding, type_name in path_extractors:
        names = _rust_binding_names(binding)
        types = _split_rust_type_tuple(type_name)
        for index, name in enumerate(names):
            type_hint = types[index] if index < len(types) else type_name.strip()
            hints.append(f"path:{name}:{type_hint}")
    for type_name in _rust_generic_arguments(params, "Query"):
        hints.append(f"query:{_clean_rust_type(type_name)}")
    for type_name in _rust_generic_arguments(params, "Json"):
        hints.append(f"body:Json<{_clean_rust_type(type_name)}>")
    for type_name in _rust_generic_arguments(params, "Extension"):
        hints.append(f"context:Extension<{_clean_rust_type(type_name)}>")
    for type_name in _rust_generic_arguments(params, "State"):
        hints.append(f"context:State<{_clean_rust_type(type_name)}>")
    for auth in ("AuthUser", "MaybeAuthUser"):
        if re.search(rf"\b{auth}\b", params):
            hints.append(f"auth:{auth}")
    return hints


def _axum_response_hints(source: str) -> list[str]:
    hints: list[str] = []
    return_type = _rust_function_return_type(source)
    if return_type:
        hints.append(f"return:{return_type}")
        hints.extend(f"response:Json<{_clean_rust_type(type_name)}>" for type_name in _rust_generic_arguments(return_type, "Json"))
    if re.search(r"\bOk\(\s*Json\(", source):
        hints.append("response:Ok(Json)")
    if "IntoResponse" in source or ".into_response()" in source:
        hints.append("response:IntoResponse")
    if re.search(r"\bResult<\s*\(\s*\)>", source):
        hints.append("response:unit")
    return hints


def _axum_status_codes(source: str) -> list[str]:
    codes: list[str] = []
    codes.extend(re.findall(r"\bStatusCode::([A-Z_]+)", source))
    return codes


def _actix_request_hints(source: str) -> list[str]:
    hints: list[str] = []
    params = _rust_function_params(source) or source
    for type_name in _rust_generic_arguments(params, "Path"):
        hints.append(f"path-model:{_clean_rust_type(type_name)}")
    for type_name in _rust_generic_arguments(params, "Json"):
        hints.append(f"body:Json<{_clean_rust_type(type_name)}>")
    for type_name in _rust_generic_arguments(params, "Query"):
        hints.append(f"query:{_clean_rust_type(type_name)}")
    for type_name in _rust_generic_arguments(params, "Data"):
        hints.append(f"context:Data<{_clean_rust_type(type_name)}>")
    if re.search(r"\bHttpRequest\b", params):
        hints.append("request:HttpRequest")
    return hints


def _actix_response_hints(source: str) -> list[str]:
    hints: list[str] = []
    return_type = _rust_function_return_type(source)
    if return_type:
        hints.append(f"return:{return_type}")
    for name in re.findall(r"\bHttpResponse::([A-Za-z0-9_]+)\s*\(", source):
        hints.append(f"response:HttpResponse::{name}")
    if re.search(r"\bHttpResponse::[A-Za-z0-9_]+\(\)\.json\s*\(", source) or re.search(r"\.json\s*\(", source):
        hints.append("response:json")
    if re.search(r"\.finish\s*\(", source):
        hints.append("response:finish")
    if re.search(r"\.body\s*\(", source):
        hints.append("response:body")
    return hints


def _actix_status_codes(source: str) -> list[str]:
    status_map = {
        "Ok": "200",
        "Created": "201",
        "Accepted": "202",
        "NoContent": "204",
        "BadRequest": "400",
        "Unauthorized": "401",
        "Forbidden": "403",
        "NotFound": "404",
        "Conflict": "409",
        "InternalServerError": "500",
    }
    codes: list[str] = []
    for name in re.findall(r"\bHttpResponse::([A-Za-z0-9_]+)\s*\(", source):
        codes.append(status_map.get(name, name))
    return codes


def _rocket_request_hints(source: str, route: ApiRouteFact) -> list[str]:
    hints: list[str] = []
    params = _rust_function_params(source) or source
    typed_params = _rust_typed_params(params)
    for param in route.parameters:
        type_name = typed_params.get(param.name)
        if param.source == "path" and type_name:
            hints.append(f"path:{param.name}:{type_name}")
        elif param.source == "query" and type_name:
            hints.append(f"query-model:{type_name}")
    for type_name in _rust_generic_arguments(params, "Json"):
        hints.append(f"body:Json<{_clean_rust_type(type_name)}>")
    for type_name in _rust_generic_arguments(params, "State"):
        hints.append(f"context:State<{_clean_rust_type(type_name)}>")
    if re.search(r"\bAuth\b", params):
        hints.append("auth:Auth")
    if re.search(r"\bdb\s*:\s*Db\b|\bDb\b", params):
        hints.append("context:Db")
    return hints


def _rocket_response_hints(source: str) -> list[str]:
    hints: list[str] = []
    return_type = _rust_function_return_type(source)
    if return_type:
        hints.append(f"return:{return_type}")
    if "json!(" in source or "Value" in return_type or "Json<" in return_type:
        hints.append("response:json")
    if return_type.startswith("Option<"):
        hints.append("response:optional")
    if return_type.startswith("Result<"):
        hints.append("response:result")
    if return_type in {"()", ""}:
        hints.append("response:unit")
    return hints


def _rocket_status_codes(source: str) -> list[str]:
    return re.findall(r"\bStatus::([A-Za-z0-9_]+)", source)


def _warp_request_hints(source: str, route: ApiRouteFact) -> list[str]:
    hints: list[str] = []
    params = _rust_ordered_typed_params(_rust_function_params(source) or source)
    path_param_count = sum(1 for param in route.parameters if param.source == "path")
    path_candidates = [
        (name, type_name)
        for name, type_name in params
        if name != "state"
        and not _rust_auth_param(name, type_name)
        and type_name in {"String", "str", "u64", "u32", "i64", "i32", "usize"}
    ]
    used_names: set[str] = set()
    for name, type_name in path_candidates[:path_param_count]:
        hints.append(f"path:{name}:{type_name}")
        used_names.add(name)
    if any(param.source == "query" for param in route.parameters):
        for name, type_name in params:
            if name not in used_names and name != "state" and not _rust_auth_param(name, type_name):
                hints.append(f"query-model:{type_name}")
                used_names.add(name)
                break
    if route.request_body:
        for name, type_name in params:
            if (
                name not in used_names
                and name != "state"
                and not _rust_auth_param(name, type_name)
                and type_name not in {"String", "str", "u64", "u32", "i64", "i32", "usize"}
            ):
                hints.append(f"body-model:{type_name}")
                used_names.add(name)
                break
    for name, type_name in params:
        if name == "state" or type_name.endswith("AppState"):
            hints.append(f"context:{type_name}")
        if _rust_auth_param(name, type_name):
            hints.append("auth:Authorization")
    return hints


def _rust_auth_param(name: str, type_name: str) -> bool:
    return name in {"token", "auth"} or type_name in {"Auth", "Option<Auth>", "&Auth"}


def _warp_response_hints(source: str) -> list[str]:
    hints: list[str] = []
    return_type = _rust_function_return_type(source)
    if return_type:
        hints.append(f"return:{return_type}")
    if "warp::reply::json" in source:
        hints.append("response:json")
    if "StatusCode::" in source:
        hints.append("response:status-code")
    if "impl warp::reply::Reply" in return_type:
        hints.append("response:impl Reply")
    return hints


def _warp_status_codes(source: str) -> list[str]:
    return re.findall(r"\bStatusCode::([A-Za-z0-9_]+)", source)


def _vapor_request_hints(route: ApiRouteFact, source: str) -> list[str]:
    hints: list[str] = []
    hints.extend(f"path:{param.name}" for param in route.parameters if param.source == "path")
    for type_name, name in re.findall(r"\brequest\.query\[\s*([A-Za-z_][\w.]*)\.self\s*,\s*at\s*:\s*['\"]([^'\"]+)['\"]\s*\]", source):
        hints.append(f"query:{name}:{type_name}")
    for name in re.findall(r"\brequest\.parameters\.get\(\s*['\"]([^'\"]+)['\"]", source):
        hints.append(f"path:{name}")
    for type_name in re.findall(r"\brequest\.content\.decode\(\s*([A-Za-z_][\w.]*)\.self", source):
        hints.append(f"body:{type_name}")
    if "request.storage[" in source:
        hints.append("context:request.storage")
    if re.search(r"\b(?:Bearer|Token|Authenticator|auth)\b", source, re.IGNORECASE):
        hints.append("auth:possible")
    return hints


def _vapor_response_hints(source: str) -> list[str]:
    hints: list[str] = []
    return_type = _swift_function_return_type(source)
    if return_type:
        hints.append(f"return:{return_type}")
    if re.search(r"\bResponse\s*\(", source):
        hints.append("response:Response")
    if "JSONEncoder" in source or "content.encode" in source:
        hints.append("response:json")
    return hints


def _vapor_status_codes(source: str) -> list[str]:
    status_map = {
        "ok": "200",
        "created": "201",
        "accepted": "202",
        "noContent": "204",
        "badRequest": "400",
        "unauthorized": "401",
        "forbidden": "403",
        "notFound": "404",
        "conflict": "409",
        "internalServerError": "500",
    }
    codes: list[str] = []
    for name in re.findall(r"\b(?:status|HTTPResponseStatus)\s*[:=]\s*\.([A-Za-z_]\w*)", source):
        codes.append(status_map.get(name, name))
    return codes


def _swift_function_return_type(source: str) -> str:
    match = re.search(r"\bfunc\s+[A-Za-z_]\w*\s*\([^)]*\)\s*(?:async\s*)?(?:throws\s*)?->\s*(?P<return>[^{\n]+)", source)
    return " ".join(match.group("return").strip().split()) if match else ""


def _rust_function_params(source: str) -> str:
    fn_match = re.search(r"\bfn\s+[A-Za-z_]\w*\b", source)
    if not fn_match:
        return ""
    open_index = source.find("(", fn_match.end())
    close_index = _find_matching_delimiter(source, open_index, "(", ")")
    if close_index is None:
        return ""
    return source[open_index + 1 : close_index]


def _rust_function_return_type(source: str) -> str:
    fn_match = re.search(r"\bfn\s+[A-Za-z_]\w*\b", source)
    if not fn_match:
        return ""
    open_index = source.find("(", fn_match.end())
    close_index = _find_matching_delimiter(source, open_index, "(", ")")
    if close_index is None:
        return ""
    brace_index = source.find("{", close_index)
    header_tail = source[close_index + 1 : brace_index if brace_index >= 0 else len(source)]
    return_match = re.search(r"->\s*(?P<return>.+)", header_tail, re.DOTALL)
    return _clean_rust_type(return_match.group("return")) if return_match else ""


def _rust_generic_arguments(source: str, generic: str) -> list[str]:
    args: list[str] = []
    pattern = re.compile(rf"\b{re.escape(generic)}\s*<")
    for match in pattern.finditer(source):
        open_index = source.find("<", match.start())
        close_index = _find_matching_delimiter(source, open_index, "<", ">")
        if close_index is None:
            continue
        args.append(source[open_index + 1 : close_index])
    return args


def _rust_typed_params(source: str) -> dict[str, str]:
    params: dict[str, str] = {}
    for name, type_name in _rust_ordered_typed_params(source):
        params[name] = type_name
    return params


def _rust_ordered_typed_params(source: str) -> list[tuple[str, str]]:
    params: list[tuple[str, str]] = []
    pattern = re.compile(
        r"\b(?P<name>[a-z_][A-Za-z0-9_]*)\s*:\s*(?P<type>&?\s*[A-Za-z_][A-Za-z0-9_:]*(?:<[^,\n\)]+>)?)"
    )
    for match in pattern.finditer(source):
        params.append((match.group("name"), _clean_rust_type(match.group("type"))))
    return params


def _rust_binding_names(binding: str) -> list[str]:
    cleaned = binding.replace("mut ", "")
    return [
        name
        for name in re.findall(r"\b([a-z_][A-Za-z0-9_]*)\b", cleaned)
        if name not in {"mut", "_"}
    ]


def _split_rust_type_tuple(type_name: str) -> list[str]:
    cleaned = type_name.strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = cleaned[1:-1]
    parts = [part.strip() for part in cleaned.split(",") if part.strip()]
    return [_clean_rust_type(part) for part in parts]


def _clean_rust_type(type_name: str) -> str:
    return " ".join(type_name.strip().split())


def _django_regex_path_hints(path: str) -> list[str]:
    return [f"path:{name}" for name in re.findall(r"\?P<([A-Za-z_]\w*)>", path)]


def _django_request_hints(source: str) -> list[str]:
    hints: list[str] = []
    for prefix, label in [
        ("GET", "query"),
        ("query_params", "query"),
        ("POST", "form"),
        ("data", "body"),
        ("FILES", "file"),
    ]:
        hints.extend(
            f"{label}:request.{prefix}.{name}"
            for name in re.findall(rf"\brequest\.{re.escape(prefix)}\.get\(\s*['\"]([^'\"]+)['\"]", source)
        )
        hints.extend(
            f"{label}:request.{prefix}.{name}"
            for name in re.findall(rf"\brequest\.{re.escape(prefix)}\[\s*['\"]([^'\"]+)['\"]\s*\]", source)
        )
    if "request.body" in source:
        hints.append("body:request.body")
    if "request.data" in source and not any(hint.startswith("body:request.data.") for hint in hints):
        hints.append("body:request.data")
    if "request.POST" in source and not any(hint.startswith("form:request.POST.") for hint in hints):
        hints.append("form:request.POST")
    hints.extend(f"path:kwargs.{name}" for name in re.findall(r"\bkwargs\.get\(\s*['\"]([^'\"]+)['\"]", source))
    return hints


def _django_response_hints(source: str) -> list[str]:
    hints: list[str] = []
    for name in ["JsonResponse", "Response", "HttpResponse", "StreamingHttpResponse", "FileResponse"]:
        if re.search(rf"\b{name}\s*\(", source):
            hints.append(f"response:{name}")
    if re.search(r"\brender\s*\(", source):
        hints.append("response:render")
    if re.search(r"\bredirect\s*\(", source):
        hints.append("response:redirect")
    return hints


def _django_status_codes(source: str) -> list[str]:
    codes: list[str] = []
    codes.extend(re.findall(r"\bstatus\s*=\s*(\d{3})\b", source))
    codes.extend(re.findall(r"\bstatus\.HTTP_(\d{3}_[A-Z_]+)", source))
    return codes


def _path_param_hints(path: str, open_char: str, close_char: str) -> list[str]:
    return [f"path:{name}" for name in _path_param_names(path, open_char, close_char)]


def _path_param_names(path: str, open_char: str, close_char: str) -> list[str]:
    pattern = re.escape(open_char) + r"([^" + re.escape(close_char) + r"]+)" + re.escape(close_char)
    names: list[str] = []
    for match in re.finditer(pattern, path):
        value = match.group(1)
        if open_char == "<" and ":" in value:
            names.append(value.split(":", 1)[1])
        elif open_char == "{" and ":" in value:
            names.append(value.split(":", 1)[0])
        else:
            names.append(value.lstrip(":"))
    return names


def _route_request_hints(route: ApiRouteFact) -> list[str]:
    hints = [f"{param.source}:{param.name}{':' + param.type if param.type else ''}" for param in route.parameters]
    if route.request_body:
        hints.append(f"body:{route.request_body}")
    if not route.parameters:
        if "{" in route.path:
            hints.extend(_path_param_hints(route.path, "{", "}"))
        if ":" in route.path and "<" not in route.path:
            hints.extend(f"path:{name}" for name in re.findall(r":([A-Za-z_]\w*)", route.path))
        if "<" in route.path:
            hints.extend(_path_param_hints(route.path, "<", ">"))
    return hints


def _status_codes(source: str, pattern: str) -> list[str]:
    return [match.group(1) for match in re.finditer(pattern, source)]


def _response_type_status_codes(response_type: str | None) -> list[str]:
    if not response_type:
        return []
    if response_type.startswith("responses:"):
        return [
            value.strip()
            for value in response_type.removeprefix("responses:").split(",")
            if re.fullmatch(r"[1-5]\d\d", value.strip())
        ]
    return []


def _named_http_status_codes(source: str) -> list[str]:
    return [
        HTTP_STATUS_NAME_TO_CODE.get(name, name)
        for name in re.findall(r"\bHttpStatusCodes\.([A-Z][A-Z0-9_]*)", source)
    ]


def _error_hints(source: str, needles: list[str]) -> list[str]:
    hints: list[str] = []
    for needle in needles:
        if needle in source:
            hints.append(f"error:{needle.rstrip('(')}")
    if re.search(r"\b(?:4\d\d|5\d\d)\b", source):
        hints.append("error:4xx-or-5xx-status")
    return hints


def _split_params(source: str) -> list[str]:
    result: list[str] = []
    start = 0
    depth = 0
    for index, char in enumerate(source):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            result.append(source[start:index])
            start = index + 1
    tail = source[start:]
    if tail:
        result.append(tail)
    return result


def _nonempty(values: list[str]) -> list[str]:
    return [value for value in values if value]


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
