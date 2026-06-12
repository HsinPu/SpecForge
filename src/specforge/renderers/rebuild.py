from __future__ import annotations

from specforge.models import ProjectFacts
from specforge.renderers.shared import _code_list, _evidence_label


def render_feature_map(facts: ProjectFacts) -> str:
    if not facts.feature_maps:
        return "# Feature Map\n\nNo connected feature map entries were generated.\n"
    sections = ["# Feature Map\n"]
    for feature in facts.feature_maps:
        evidence = ", ".join(_evidence_label(item) for item in feature.evidence[:5]) or "`unknown`"
        sections.append(
            f"## {feature.name}\n\n"
            f"{feature.summary}\n\n"
            f"- Confidence: {feature.confidence}\n"
            f"- Frontend sources: {_code_list(feature.frontend_sources) or '`none`'}\n"
            f"- Frontend routes: {_code_list(feature.frontend_routes) or '`none`'}\n"
            f"- Pages: {_code_list(feature.pages) or '`none`'}\n"
            f"- Components: {_code_list(feature.components) or '`none`'}\n"
            f"- Forms: {_code_list(feature.forms) or '`none`'}\n"
            f"- API calls: {_code_list(feature.api_calls) or '`none`'}\n"
            f"- Backend routes: {_code_list(feature.backend_routes) or '`none`'}\n"
            f"- Contracts: {_code_list(feature.contracts) or '`none`'}\n"
            f"- Services: {_code_list(feature.services) or '`unknown`'}\n"
            f"- Repositories: {_code_list(feature.repositories) or '`unknown`'}\n"
            f"- Data models: {_code_list(feature.data_models) or '`unknown`'}\n"
            f"- Tests: {_code_list(feature.tests) or '`unknown`'}\n"
            f"- Evidence: {evidence}\n"
        )
    return "\n".join(sections)


def render_rebuild_spec(facts: ProjectFacts) -> str:
    sections = [
        "# Rebuild Spec\n",
        "This document reshapes observed facts into rebuild targets. It is still evidence-first: "
        "unknown behavior stays unknown until confirmed.\n",
        "## Rebuild Order\n",
        "1. Recreate runtime/config and dependency assumptions.\n"
        "2. Recreate backend API contracts and data boundaries.\n"
        "3. Recreate frontend pages/components/forms that call those APIs.\n"
        "4. Reconnect tests to each feature target.\n"
        "5. Resolve contract gaps before claiming behavior parity.\n",
    ]
    if not facts.feature_maps:
        sections.append("## Feature Targets\n\nNo feature targets were generated.\n")
    else:
        sections.append("## Feature Targets\n")
        for feature in facts.feature_maps:
            related_gaps = [
                gap
                for gap in facts.contract_gaps
                if gap.contract in set(feature.contracts + feature.api_calls + feature.backend_routes)
            ]
            sections.append(
                f"### {feature.name}\n\n"
                f"- Goal: {feature.summary}\n"
                f"- Frontend: {_code_list(feature.pages + feature.components + feature.forms) or '`unknown`'}\n"
                f"- API: {_code_list(feature.api_calls + feature.backend_routes) or '`unknown`'}\n"
                f"- Data: {_code_list(feature.services + feature.repositories + feature.data_models) or '`unknown`'}\n"
                f"- Tests: {_code_list(feature.tests) or '`unknown`'}\n"
                f"- Contract gaps: {_code_list([gap.gap_type for gap in related_gaps]) or '`none detected`'}\n"
            )

    sections.append(
        "## Global Rebuild Constraints\n\n"
        "- Preserve every route, command, page, component, and data model backed by evidence.\n"
        "- Treat unmatched API calls as external or missing until confirmed.\n"
        "- Treat unmatched backend routes as server-only or unknown consumers until confirmed.\n"
        "- Do not invent request/response schemas where `contract-gaps.md` says unknown.\n"
    )
    return "\n".join(sections)


def render_refactor_plan(facts: ProjectFacts) -> str:
    if not facts.refactor_findings:
        return "# Refactor Plan\n\nNo refactor findings were generated.\n"
    sections = [
        "# Refactor Plan\n",
        "These findings are conservative hints for a human or LLM-assisted refactor. "
        "They are not automatic rewrite instructions.\n",
    ]
    for severity in ("high", "medium", "low"):
        items = [item for item in facts.refactor_findings if item.severity == severity]
        if not items:
            continue
        sections.append(f"## {severity.capitalize()}\n")
        for item in items:
            evidence = ", ".join(_evidence_label(evidence) for evidence in item.evidence[:5]) or "`unknown`"
            sections.append(
                f"### {item.title}\n\n"
                f"- Subject: `{item.subject}`\n"
                f"- Detail: {item.detail}\n"
                f"- Recommendation: {item.recommendation}\n"
                f"- Evidence: {evidence}\n"
            )
    return "\n".join(sections)


def render_module_boundaries(facts: ProjectFacts) -> str:
    if not facts.module_boundaries:
        return "# Module Boundaries\n\nNo module boundaries were generated.\n"
    sections = ["# Module Boundaries\n"]
    for boundary in facts.module_boundaries:
        evidence = ", ".join(_evidence_label(item) for item in boundary.evidence[:5]) or "`unknown`"
        sections.append(
            f"## {boundary.name}\n\n"
            f"- Kind: {boundary.kind}\n"
            f"- Responsibilities: {_code_list(boundary.responsibilities) or '`unknown`'}\n"
            f"- Depends on: {_code_list(boundary.depends_on) or '`none`'}\n"
            f"- Paths: {_code_list(boundary.paths[:30]) or '`none detected`'}\n"
            f"- Evidence: {evidence}\n"
        )
    return "\n".join(sections)


def render_contract_gaps(facts: ProjectFacts) -> str:
    if not facts.contract_gaps:
        return "# Contract Gaps\n\nNo contract gaps were generated.\n"
    rows = [
        "# Contract Gaps\n",
        "| Contract | Gap Type | Detail | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    for gap in facts.contract_gaps:
        evidence = ", ".join(_evidence_label(item) for item in gap.evidence[:3])
        rows.append(f"| `{gap.contract}` | {gap.gap_type} | {gap.detail} | {evidence} |")
    return "\n".join(rows) + "\n"


def render_spec_diff(facts: ProjectFacts, previous_facts: ProjectFacts | None = None) -> str:
    if previous_facts is None:
        return (
            "# Spec Diff\n\n"
            "No previous fact bundle was supplied. This scan is the baseline for future updates.\n"
        )

    sections = [
        "# Spec Diff\n",
        f"Previous schema: `{previous_facts.schema_version}`\n",
        f"Current schema: `{facts.schema_version}`\n",
        "## Count Changes\n",
        "| Surface | Previous | Current | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    count_pairs = [
        ("Files", len(previous_facts.files), len(facts.files)),
        ("Backend routes", len(previous_facts.api_routes), len(facts.api_routes)),
        ("API calls", len(previous_facts.api_calls), len(facts.api_calls)),
        ("API links", len(previous_facts.api_links), len(facts.api_links)),
        ("Components", len(previous_facts.components), len(facts.components)),
        ("Pages", len(previous_facts.pages), len(facts.pages)),
        ("Data models", len(previous_facts.data_models), len(facts.data_models)),
        ("Runtime configs", len(previous_facts.runtime_configs), len(facts.runtime_configs)),
        ("Tests", len(previous_facts.test_files), len(facts.test_files)),
        ("Feature maps", len(previous_facts.feature_maps), len(facts.feature_maps)),
        ("Contract gaps", len(previous_facts.contract_gaps), len(facts.contract_gaps)),
    ]
    for label, previous, current in count_pairs:
        sections.append(f"| {label} | {previous} | {current} | {current - previous:+d} |")

    sections.append("\n## Surface Changes\n")
    sections.append(_diff_section("API routes", _api_route_keys(previous_facts), _api_route_keys(facts)))
    sections.append(_diff_section("API calls", _api_call_keys(previous_facts), _api_call_keys(facts)))
    sections.append(_diff_section("Components", _component_keys(previous_facts), _component_keys(facts)))
    sections.append(_diff_section("Pages", _page_keys(previous_facts), _page_keys(facts)))
    sections.append(_diff_section("Data models", _model_keys(previous_facts), _model_keys(facts)))
    return "\n".join(sections)


def _diff_section(label: str, previous: set[str], current: set[str]) -> str:
    added = sorted(current - previous)
    removed = sorted(previous - current)
    return (
        f"### {label}\n\n"
        f"- Added: {_code_list(added) or '`none`'}\n"
        f"- Removed: {_code_list(removed) or '`none`'}\n"
    )


def _api_route_keys(facts: ProjectFacts) -> set[str]:
    return {f"{route.method} {route.path}" for route in facts.api_routes}


def _api_call_keys(facts: ProjectFacts) -> set[str]:
    return {f"{call.method or 'ANY'} {call.endpoint}" for call in facts.api_calls}


def _component_keys(facts: ProjectFacts) -> set[str]:
    return {component.name for component in facts.components}


def _page_keys(facts: ProjectFacts) -> set[str]:
    return {page.route for page in facts.pages}


def _model_keys(facts: ProjectFacts) -> set[str]:
    return {model.name for model in facts.data_models}
