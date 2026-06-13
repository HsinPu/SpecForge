from __future__ import annotations

from specforge.models import ProjectFacts

def _dominant_language(facts: ProjectFacts) -> str:
    if not facts.languages:
        return "none detected"
    language, count = max(facts.languages.items(), key=lambda item: item[1])
    return f"{language} ({count} file(s))"

def _symbols_by_path(facts: ProjectFacts) -> dict[str, list]:
    grouped: dict[str, list] = {}
    for symbol in facts.symbols:
        grouped.setdefault(symbol.path, []).append(symbol)
    return dict(sorted(grouped.items()))

def _symbol_bullets(symbols: list) -> str:
    lines: list[str] = []
    for symbol in symbols:
        suffix = f"`{symbol.signature}`" if symbol.signature else symbol.kind
        doc = f" - {symbol.docstring}" if symbol.docstring else ""
        lines.append(f"- `{symbol.qualname}` ({symbol.kind}) {suffix}{doc}")
    return "\n".join(lines)

def _param_summary(parameters: list) -> str:
    if not parameters:
        return ""
    return ", ".join(
        f"`{item.source}:{item.name}{':' + item.type if item.type else ''}`"
        for item in parameters
    )

def _code_list(values: list[str]) -> str:
    return ", ".join(f"`{item}`" for item in values)

def _data_model_rows(facts: ProjectFacts) -> str:
    rows = [
        "| Model | Kind | Fields | Annotations | Source |",
        "| --- | --- | --- | --- | --- |",
    ]
    for model in facts.data_models:
        rows.append(
            f"| `{model.name}` | {model.kind} | {_code_list(model.fields)} | "
            f"{_code_list(model.annotations)} | "
            f"{_source_link(model.evidence.file, model.evidence.line_start or 1)} |"
        )
    return "\n".join(rows)

def _repository_rows(facts: ProjectFacts) -> str:
    rows = [
        "| Repository | Entity | Base Interface | Source |",
        "| --- | --- | --- | --- |",
    ]
    for repository in facts.repositories:
        rows.append(
            f"| `{repository.name}` | `{repository.entity or ''}` | "
            f"`{repository.base_interface or ''}` | "
            f"{_source_link(repository.evidence.file, repository.evidence.line_start or 1)} |"
        )
    return "\n".join(rows)

def _service_rows(facts: ProjectFacts) -> str:
    rows = [
        "| Service | Methods | Source |",
        "| --- | --- | --- |",
    ]
    for service in facts.services:
        rows.append(
            f"| `{service.name}` | {_code_list(service.methods)} | "
            f"{_source_link(service.evidence.file, service.evidence.line_start or 1)} |"
        )
    return "\n".join(rows)

def _evidence_label(evidence: object) -> str:
    line = getattr(evidence, "line_start", None)
    file = getattr(evidence, "file", "")
    label = f"`{file}:{line}`" if line else f"`{file}`"
    note = getattr(evidence, "note", None)
    return f"{label} ({note})" if note else label

def _source_link(path: str, line: int) -> str:
    return f"`{path}:{line}`"
