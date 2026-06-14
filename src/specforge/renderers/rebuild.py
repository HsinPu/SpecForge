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
            f"- Commands: {_code_list(feature.commands) or '`none`'}\n"
            f"- Implementation sources: {_limited_code_list(feature.implementation_sources, 12) or '`unknown`'}\n"
            f"- Implementation match reasons: {_limited_code_list(feature.implementation_reasons, 12) or '`unknown`'}\n"
            f"- API calls: {_code_list(feature.api_calls) or '`none`'}\n"
            f"- Backend routes: {_code_list(feature.backend_routes) or '`none`'}\n"
            f"- Contracts: {_code_list(feature.contracts) or '`none`'}\n"
            f"- Services: {_code_list(feature.services) or '`unknown`'}\n"
            f"- Repositories: {_code_list(feature.repositories) or '`unknown`'}\n"
            f"- Data models: {_code_list(feature.data_models) or '`unknown`'}\n"
            f"- Tests: {_limited_code_list(feature.tests, 15) or '`unknown`'}\n"
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
        "2. Recreate CLI entrypoints and command contracts when present.\n"
        "3. Recreate backend API contracts and data boundaries.\n"
        "4. Recreate frontend pages/components/forms that call those APIs.\n"
        "5. Reconnect tests to each feature target.\n"
        "6. Resolve contract gaps before claiming behavior parity.\n",
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
                f"- CLI: {_code_list(feature.commands) or '`unknown`'}\n"
                f"- Implementation: {_limited_code_list(feature.implementation_sources, 10) or '`unknown`'}\n"
                f"- Match reasons: {_limited_code_list(feature.implementation_reasons, 10) or '`unknown`'}\n"
                f"- Frontend: {_code_list(feature.pages + feature.components + feature.forms) or '`unknown`'}\n"
                f"- API: {_code_list(feature.api_calls + feature.backend_routes) or '`unknown`'}\n"
                f"- Data: {_code_list(feature.services + feature.repositories + feature.data_models) or '`unknown`'}\n"
                f"- Tests: {_limited_code_list(feature.tests, 12) or '`unknown`'}\n"
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
    populated_boundaries = [boundary for boundary in facts.module_boundaries if boundary.paths]
    empty_boundaries = [boundary for boundary in facts.module_boundaries if not boundary.paths]
    if not populated_boundaries:
        sections.append("No populated module boundaries were detected from scanned source paths.\n")
    for boundary in populated_boundaries:
        evidence = ", ".join(_evidence_label(item) for item in boundary.evidence[:5]) or "`unknown`"
        sections.append(
            f"## {boundary.name}\n\n"
            f"- Kind: {boundary.kind}\n"
            f"- Responsibilities: {_code_list(boundary.responsibilities) or '`unknown`'}\n"
            f"- Depends on: {_code_list(boundary.depends_on) or '`none`'}\n"
            f"- Paths: {_code_list(boundary.paths[:30]) or '`none detected`'}\n"
            f"- Evidence: {evidence}\n"
        )
    if empty_boundaries:
        sections.append("## Not Detected\n")
        for boundary in empty_boundaries:
            sections.append(f"- {boundary.name} ({boundary.kind})\n")
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


def render_quality_report(facts: ProjectFacts) -> str:
    command_features = [feature for feature in facts.feature_maps if feature.commands]
    command_features_with_impl = [
        feature for feature in command_features if feature.implementation_sources
    ]
    command_features_with_tests = [
        feature for feature in command_features if feature.tests
    ]
    backend_api_links = [link for link in facts.api_links if link.target_kind == "backend-route"]
    matched_api_links = [link for link in backend_api_links if link.matched_route]
    unmatched_api_links = [link for link in backend_api_links if not link.matched_route]
    external_api_links = [link for link in facts.api_links if link.target_kind == "external-api"]
    dynamic_api_links = [link for link in facts.api_links if link.target_kind == "dynamic-endpoint"]
    matched_tests = [item for item in facts.test_maps if item.target_kind != "unmatched"]
    unmatched_tests = [item for item in facts.test_maps if item.target_kind == "unmatched"]
    populated_boundaries = [boundary for boundary in facts.module_boundaries if boundary.paths]
    empty_boundaries = [boundary for boundary in facts.module_boundaries if not boundary.paths]
    low_confidence_features = [
        feature for feature in facts.feature_maps if feature.confidence == "low"
    ]
    unknown_languages = [file_fact for file_fact in facts.files if file_fact.language == "unknown"]
    features_without_evidence = [feature for feature in facts.feature_maps if not feature.evidence]

    sections = [
        "# Quality Report\n",
        "This report summarizes scan completeness and confidence. It is a release-readiness aid, not a claim of complete behavior understanding.\n",
        "## Coverage\n",
        f"- Files scanned: {len(facts.files)}",
        f"- Unknown-language files: {len(unknown_languages)}",
        f"- Commands detected: {len(facts.commands)}",
        f"- Command feature maps: {len(command_features)}",
        f"- Command features with implementation sources: {len(command_features_with_impl)} / {len(command_features)}",
        f"- Command features with tests: {len(command_features_with_tests)} / {len(command_features)}",
        f"- Backend API links matched: {len(matched_api_links)} / {len(backend_api_links)}",
        f"- Backend API links unmatched: {len(unmatched_api_links)}",
        f"- External API calls: {len(external_api_links)}",
        f"- Dynamic API endpoints: {len(dynamic_api_links)}",
        f"- Tests matched: {len(matched_tests)} / {len(facts.test_maps)}",
        f"- Tests unmatched: {len(unmatched_tests)}",
        f"- Populated module boundaries: {len(populated_boundaries)} / {len(facts.module_boundaries)}",
        f"- Empty module boundaries: {len(empty_boundaries)}",
        f"- Low-confidence feature maps: {len(low_confidence_features)}",
        f"- Feature maps without evidence: {len(features_without_evidence)}",
        f"- Contract gaps: {len(facts.contract_gaps)}",
        f"- Refactor findings: {len(facts.refactor_findings)}",
        "",
        "## Readiness Notes\n",
        *_quality_notes(
            command_features,
            command_features_with_impl,
            unmatched_api_links,
            unmatched_tests,
            low_confidence_features,
            unknown_languages,
            features_without_evidence,
        ),
    ]
    return "\n".join(sections)


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


def _quality_notes(
    command_features: list,
    command_features_with_impl: list,
    unmatched_api_links: list,
    unmatched_tests: list,
    low_confidence_features: list,
    unknown_languages: list,
    features_without_evidence: list,
) -> list[str]:
    notes: list[str] = []
    if command_features and len(command_features_with_impl) < len(command_features):
        missing = len(command_features) - len(command_features_with_impl)
        notes.append(f"- {missing} command feature(s) still need implementation-source confirmation.")
    if unmatched_api_links:
        notes.append("- Some frontend API calls are unmatched; keep them as external/missing until confirmed.")
    if unmatched_tests:
        notes.append("- Some tests are unmatched; use `test-map.md` before claiming behavior coverage.")
    if low_confidence_features:
        notes.append("- Some feature maps are low confidence; verify them manually before rebuild work.")
    if unknown_languages:
        notes.append("- Some files have unknown language; extend inventory rules if they matter.")
    if features_without_evidence:
        notes.append("- Some feature maps have no evidence; treat them as defects in the spec bundle.")
    if not notes:
        notes.append("- No obvious first-stage quality blockers were detected.")
    return notes


def _limited_code_list(values: list[str], limit: int) -> str:
    visible = _code_list(values[:limit])
    if not visible:
        return ""
    remaining = len(values) - limit
    if remaining > 0:
        return f"{visible}, `... {remaining} more`"
    return visible
