from __future__ import annotations

import re
from pathlib import Path

from specforge.models import Evidence, FileFact, ServiceFact


REDWOOD_SERVICE_EXPORT_RE = re.compile(
    r"^\s*export\s+(?:const\s+(?P<const>[A-Za-z_$][\w$]*)\s*=|(?:async\s+)?function\s+(?P<function>[A-Za-z_$][\w$]*)\s*\()",
    re.MULTILINE,
)


def extract_redwood_service_facts(root: Path, files: list[FileFact]) -> list[ServiceFact]:
    services: list[ServiceFact] = []
    for file_fact in files:
        normalized = file_fact.path.replace("\\", "/")
        if file_fact.role in {"test", "sample", "generated"}:
            continue
        if "/api/src/services/" not in f"/{normalized}" or file_fact.language not in {"javascript", "typescript"}:
            continue
        path = root / file_fact.path
        if not path.exists():
            continue
        source = path.read_text(encoding="utf-8-sig", errors="ignore")
        methods: list[str] = []
        first_line = 1
        for match in REDWOOD_SERVICE_EXPORT_RE.finditer(source):
            name = match.group("const") or match.group("function")
            if not name:
                continue
            if not methods:
                first_line = _line_for_offset(source, match.start())
            methods.append(name)
        if not methods:
            continue
        services.append(
            ServiceFact(
                name=_redwood_service_name(normalized),
                path=file_fact.path,
                methods=_dedupe(methods),
                evidence=Evidence(file=file_fact.path, kind="service", line_start=first_line, line_end=first_line),
            )
        )
    return services


def _redwood_service_name(path: str) -> str:
    parts = path.split("/")
    if "services" in parts:
        index = parts.index("services")
        if index + 1 < len(parts):
            return parts[index + 1]
    return Path(path).stem


def _line_for_offset(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
