from __future__ import annotations

from specforge.models import Gap, ProjectFacts, TraceClaim
from specforge.renderers.shared import _code_list, _evidence_label, _source_link

def render_entrypoints(facts: ProjectFacts) -> str:
    if not facts.entrypoints:
        return "# Entrypoints\n\nNo entrypoints were detected from supported manifests or conventions.\n"
    rows = [
        "| Command | Target | Kind | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    for entrypoint in facts.entrypoints:
        rows.append(
            "| "
            f"{entrypoint.command or ''} | `{entrypoint.path}` | {entrypoint.kind} | "
            f"`{entrypoint.evidence.file}` |"
        )
    return "# Entrypoints\n\n" + "\n".join(rows) + "\n"

def render_commands(facts: ProjectFacts) -> str:
    if not facts.commands:
        return "# Commands\n\nNo CLI commands were detected by the current extractors.\n"
    rows = [
        "| Command | Description | Arguments | Options | Source |",
        "| --- | --- | --- | --- | --- |",
    ]
    for command in facts.commands:
        arguments = ", ".join(f"`{item}`" for item in command.arguments) or ""
        options = ", ".join(f"`{item}`" for item in command.options) or ""
        description = command.description or ""
        source = _source_link(command.path, command.evidence.line_start or 1)
        rows.append(
            f"| `{command.name}` | {description} | {arguments} | {options} | {source} |"
        )
    return "# Commands\n\n" + "\n".join(rows) + "\n"

def render_tests(facts: ProjectFacts) -> str:
    if not facts.test_files:
        return "# Tests\n\nNo test files were detected with the current scanner rules.\n"
    rows = [
        "| Path | Language | Size |",
        "| --- | --- | ---: |",
    ]
    for test_file in facts.test_files:
        rows.append(f"| `{test_file.path}` | {test_file.language} | {test_file.size_bytes} |")
    return "# Tests\n\n" + "\n".join(rows) + "\n"

def render_runtime_config(facts: ProjectFacts) -> str:
    if not facts.runtime_configs:
        return "# Runtime Config\n\nNo runtime config facts were detected.\n"
    rows = [
        "| Path | Kind | Name | Values | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for config in facts.runtime_configs:
        rows.append(
            f"| `{config.path}` | {config.kind} | `{config.name}` | "
            f"{_code_list(config.values) or '`unknown`'} | "
            f"{_source_link(config.evidence.file, config.evidence.line_start or 1)} |"
        )
    return "# Runtime Config\n\n" + "\n".join(rows) + "\n"

def render_test_map(facts: ProjectFacts) -> str:
    if not facts.test_maps:
        return "# Test Map\n\nNo test map entries were generated.\n"
    rows = [
        "| Test | Target Kind | Target | Confidence | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in facts.test_maps:
        rows.append(
            f"| `{item.test_path}` | {item.target_kind} | "
            f"`{item.target or 'unmatched'}` | {item.confidence} | "
            f"{_source_link(item.evidence.file, item.evidence.line_start or 1)} |"
        )
    return "# Test Map\n\n" + "\n".join(rows) + "\n"

def render_gaps(gaps: list[Gap]) -> str:
    if not gaps:
        return "# Gaps and Questions\n\nNo deterministic gaps were detected by the current scanner.\n"
    sections = ["# Gaps and Questions\n"]
    for gap in gaps:
        evidence = "\n".join(f"- {_evidence_label(item)} ({item.kind})" for item in gap.evidence)
        sections.append(
            f"## {gap.gap_id}: {gap.title}\n\n"
            f"Severity: `{gap.severity}`\n\n"
            f"{gap.detail}\n\n"
            f"Evidence:\n{evidence or '- none'}\n"
        )
    return "\n".join(sections)

def render_evidence(claims: list[TraceClaim]) -> str:
    if not claims:
        return "# Evidence\n\nNo traceability claims were generated.\n"
    sections = ["# Evidence\n"]
    for claim in claims:
        evidence = "\n".join(
            f"- {_evidence_label(item)} ({item.kind})"
            + (f": {item.note}" if item.note else "")
            for item in claim.evidence
        )
        sections.append(
            f"## {claim.claim_id}\n\n"
            f"- Type: `{claim.claim_type}`\n"
            f"- Status: `{claim.status}`\n"
            f"- Confidence: `{claim.confidence}`\n"
            f"- Claim: {claim.claim}\n\n"
            f"Evidence:\n{evidence or '- none'}\n"
        )
    return "\n".join(sections)
