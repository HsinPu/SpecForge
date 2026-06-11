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
        request_hints: list[str] = []
        response_hints: list[str] = []
        status_codes: list[str] = []
        error_hints: list[str] = []

        if route.framework == "express":
            request_hints.extend(_express_request_hints(contract_source))
            response_hints.extend(_express_response_hints(contract_source))
            status_codes.extend(_status_codes(contract_source, r"\bres\.status\(\s*(\d{3})\s*\)"))
            error_hints.extend(_error_hints(contract_source, ["next(", "throw new", ".catch("]))
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
        elif route.framework == "spring":
            request_hints.extend(_spring_request_hints(route))
            response_hints.extend(_nonempty([f"return:{route.response_type}" if route.response_type else ""]))
            status_codes.extend(_status_codes(contract_source, r"@ResponseStatus\s*\(\s*(?:HttpStatus\.)?([A-Z_]+|\d{3})"))
            error_hints.extend(_error_hints(contract_source, ["throw new", "@ExceptionHandler"]))
        elif route.framework == "next":
            request_hints.extend(_next_request_hints(contract_source))
            response_hints.extend(_next_response_hints(contract_source))
            status_codes.extend(_status_codes(contract_source, r"status\s*[:=]\s*(\d{3})"))
            error_hints.extend(_error_hints(contract_source, ["throw new", "NextResponse.error", "Response.error"]))

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
        status_codes: list[str] = []
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
    return (root / relative).read_text(encoding="utf-8")


def _route_source_window(source: str, route: ApiRouteFact) -> str:
    line = route.evidence.line_start or 1
    lines = source.splitlines()
    start_offset = _offset_for_line(source, line)
    next_marker = _next_route_marker(source, start_offset + 1, route.framework)
    if next_marker is not None:
        nearby = source[start_offset:next_marker]
    else:
        nearby = "\n".join(lines[max(0, line - 1) : min(len(lines), line + 80)])
    handler_body = _handler_body(source, route.handler)
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
    elif framework in {"fastapi", "flask"}:
        pattern = r"\n\s*@(?:app|router|blueprint|bp)\.(?:get|post|put|delete|patch|options|head|route)\("
    elif framework == "spring":
        pattern = r"\n\s*@(?:GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping)\b"
    else:
        return None
    match = re.search(pattern, source[offset:], re.IGNORECASE)
    return offset + match.start() if match else None


def _handler_body(source: str, handler: str | None) -> str:
    if not handler:
        return ""
    simple = handler.split(".")[-1].strip()
    patterns = [
        rf"\bfunction\s+{re.escape(simple)}\s*\([^)]*\)\s*\{{",
        rf"\bconst\s+{re.escape(simple)}\s*=\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{{",
        rf"\b(?:async\s+)?def\s+{re.escape(simple)}\s*\([^)]*\)\s*:",
    ]
    for pattern in patterns:
        match = re.search(pattern, source)
        if match:
            return source[match.start() : match.start() + 2200]
    return ""


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
        rf"@(?:app|router)\.{re.escape(method)}\(\s*['\"]{re.escape(route.path)}['\"](?P<args>[^)]*)\)",
        re.DOTALL,
    )
    match = pattern.search(source)
    return match.group(0) if match else None


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


def _spring_request_hints(route: ApiRouteFact) -> list[str]:
    hints = [f"{param.source}:{param.name}{':' + param.type if param.type else ''}" for param in route.parameters]
    if route.request_body:
        hints.append(f"body:{route.request_body}")
    return hints


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


def _path_param_hints(path: str, open_char: str, close_char: str) -> list[str]:
    return [f"path:{name}" for name in _path_param_names(path, open_char, close_char)]


def _path_param_names(path: str, open_char: str, close_char: str) -> list[str]:
    pattern = re.escape(open_char) + r"([^" + re.escape(close_char) + r":]+)(?::[^" + re.escape(close_char) + r"]+)?" + re.escape(close_char)
    return [match.group(1) for match in re.finditer(pattern, path)]


def _route_request_hints(route: ApiRouteFact) -> list[str]:
    hints = [f"{param.source}:{param.name}{':' + param.type if param.type else ''}" for param in route.parameters]
    if route.request_body:
        hints.append(f"body:{route.request_body}")
    if not route.parameters:
        if "{" in route.path:
            hints.extend(_path_param_hints(route.path, "{", "}"))
        if ":" in route.path:
            hints.extend(f"path:{name}" for name in re.findall(r":([A-Za-z_]\w*)", route.path))
        if "<" in route.path:
            hints.extend(_path_param_hints(route.path, "<", ">"))
    return hints


def _status_codes(source: str, pattern: str) -> list[str]:
    return [match.group(1) for match in re.finditer(pattern, source)]


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
