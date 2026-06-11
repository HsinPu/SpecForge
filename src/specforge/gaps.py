from __future__ import annotations

from specforge.models import Evidence, Gap, ProjectFacts


def detect_gaps(facts: ProjectFacts) -> list[Gap]:
    gaps: list[Gap] = []

    if not facts.entrypoints:
        gaps.append(
            Gap(
                gap_id="GAP-001",
                title="No runtime entrypoint detected",
                detail=(
                    "SpecForge did not find a supported manifest entrypoint or conventional "
                    "entrypoint file. The project may still have entrypoints that require a "
                    "language-specific extractor."
                ),
                severity="medium",
                evidence=[Evidence(file=".", kind="directory", note=facts.root)],
            )
        )

    if not facts.test_files:
        gaps.append(
            Gap(
                gap_id="GAP-002",
                title="No test files detected",
                detail=(
                    "No test files were detected with the current file-pattern scanner. "
                    "Behavior parity may need manual test discovery or new extractor rules."
                ),
                severity="medium",
                evidence=[Evidence(file=".", kind="directory", note=facts.root)],
            )
        )

    if not facts.dependencies:
        gaps.append(
            Gap(
                gap_id="GAP-003",
                title="No declared runtime dependencies detected",
                detail=(
                    "No dependencies were found in supported manifest files. This can mean the "
                    "project intentionally uses only the standard library, or that dependency "
                    "data lives in a manifest format SpecForge does not yet support."
                ),
                severity="low",
                evidence=[Evidence(file=".", kind="directory", note=facts.root)],
            )
        )

    for index, issue in enumerate(facts.extraction_issues, start=1):
        gaps.append(
            Gap(
                gap_id=f"GAP-AST-{index:03d}",
                title=f"{issue.extractor} extraction issue in {issue.path}",
                detail=issue.message,
                severity="high",
                evidence=[issue.evidence],
            )
        )

    if facts.api_routes:
        gaps.append(
            Gap(
                gap_id="GAP-006",
                title="API side effects are not inferred",
                detail=(
                    "SpecForge detected backend route skeletons, but it does not yet infer "
                    "database writes, external service calls, transaction boundaries, or "
                    "business side effects."
                ),
                severity="low",
                evidence=[route.evidence for route in facts.api_routes[:10]],
            )
        )
        gaps.append(
            Gap(
                gap_id="GAP-007",
                title="Authentication and authorization are not inferred",
                detail=(
                    "SpecForge does not yet analyze Spring Security, filters, interceptors, "
                    "middleware, guards, or route-level authorization rules."
                ),
                severity="medium",
                evidence=[route.evidence for route in facts.api_routes[:10]],
            )
        )

    unmatched_api_links = [link for link in facts.api_links if link.matched_route is None]
    if unmatched_api_links:
        gaps.append(
            Gap(
                gap_id="GAP-012",
                title="Some frontend API calls did not match backend routes",
                detail=(
                    f"{len(unmatched_api_links)} frontend API call(s) were detected without a "
                    "matched backend route. Reimplementation should treat these as missing "
                    "backend contracts or external API calls until confirmed."
                ),
                severity="medium",
                evidence=[
                    evidence
                    for link in unmatched_api_links[:10]
                    for evidence in link.evidence[:1]
                ],
            )
        )

    if facts.api_routes and facts.api_links:
        matched_routes = {
            (link.matched_method, link.matched_route)
            for link in facts.api_links
            if link.matched_route
        }
        unmatched_routes = [
            route
            for route in facts.api_routes
            if (route.method, route.path) not in matched_routes
            and ("ANY", route.path) not in matched_routes
        ]
        if unmatched_routes:
            gaps.append(
                Gap(
                    gap_id="GAP-013",
                    title="Some backend routes are not linked from detected frontend calls",
                    detail=(
                        f"{len(unmatched_routes)} backend route(s) were not linked from a "
                        "detected frontend API call. They may be server-only, externally used, "
                        "or missed by the frontend extractor."
                    ),
                    severity="low",
                    evidence=[route.evidence for route in unmatched_routes[:10]],
                )
            )

    unknown_contracts = [
        contract
        for contract in facts.api_contracts
        if not contract.request_hints
        or not contract.response_hints
        or not contract.status_codes
    ]
    if unknown_contracts:
        gaps.append(
            Gap(
                gap_id="GAP-014",
                title="Some API contract fields are unknown",
                detail=(
                    f"{len(unknown_contracts)} API contract(s) have unknown request, response, "
                    "or status-code hints. DTO fields, response schema, and error behavior "
                    "must not be invented without deeper evidence."
                ),
                severity="medium",
                evidence=[contract.evidence for contract in unknown_contracts[:10]],
            )
        )

    unmatched_tests = [item for item in facts.test_maps if item.target_kind == "unmatched"]
    if unmatched_tests:
        gaps.append(
            Gap(
                gap_id="GAP-015",
                title="Some tests could not be mapped to implementation targets",
                detail=(
                    f"{len(unmatched_tests)} test file(s) could not be confidently mapped to "
                    "an API route, component, command, service, repository, or data model."
                ),
                severity="low",
                evidence=[item.evidence for item in unmatched_tests[:10]],
            )
        )

    models_without_fields = [model for model in facts.data_models if not model.fields]
    if models_without_fields:
        gaps.append(
            Gap(
                gap_id="GAP-008",
                title="Some data model fields are not confirmed",
                detail=(
                    f"{len(models_without_fields)} data model(s) were detected without field "
                    "evidence. Constructor-only, Lombok-heavy, generated, or inherited fields "
                    "may need manual confirmation."
                ),
                severity="low",
                evidence=[model.evidence for model in models_without_fields[:10]],
            )
        )

    if facts.pages or facts.frontend_routes or facts.forms:
        gaps.append(
            Gap(
                gap_id="GAP-009",
                title="Frontend user flows are not inferred",
                detail=(
                    "SpecForge detected frontend pages, routes, and forms, but it does not yet "
                    "infer complete navigation flows, validation behavior, runtime-generated DOM, "
                    "or end-to-end user journeys."
                ),
                severity="low",
                evidence=[
                    *[page.evidence for page in facts.pages[:5]],
                    *[form.evidence for form in facts.forms[:5]],
                    *[route.evidence for route in facts.frontend_routes[:5]],
                ],
            )
        )

    if facts.styles:
        gaps.append(
            Gap(
                gap_id="GAP-010",
                title="CSS cascade and visual behavior are not inferred",
                detail=(
                    "Style selectors, variables, imports, and asset URLs were detected, but "
                    "SpecForge does not yet resolve cascade precedence, responsive breakpoints, "
                    "computed styles, or visual layout behavior."
                ),
                severity="low",
                evidence=[style.evidence for style in facts.styles[:10]],
            )
        )

    if facts.state_usages:
        gaps.append(
            Gap(
                gap_id="GAP-011",
                title="Frontend state data flow is not inferred",
                detail=(
                    "State hooks and store usages were detected, but SpecForge does not yet "
                    "infer state schemas, mutations, selectors, subscriptions, or cross-component "
                    "data flow."
                ),
                severity="low",
                evidence=[state.evidence for state in facts.state_usages[:10]],
            )
        )

    unknown_files = [file_fact for file_fact in facts.files if file_fact.language == "unknown"]
    if unknown_files:
        gaps.append(
            Gap(
                gap_id="GAP-004",
                title="Some files have unknown language",
                detail=(
                    f"{len(unknown_files)} file(s) use extensions not mapped by the current "
                    "language detector."
                ),
                severity="low",
                evidence=[file_fact.evidence for file_fact in unknown_files[:10]],
            )
        )

    source_files = [
        file_fact
        for file_fact in facts.files
        if file_fact.role
        in {
            "source",
            "api",
            "asset",
            "data-model",
            "entrypoint",
            "frontend-page",
            "repository",
            "service",
            "style",
            "webapp",
        }
    ]
    if not source_files:
        gaps.append(
            Gap(
                gap_id="GAP-005",
                title="No source files detected",
                detail=(
                    "The scan did not classify any files as implementation source. "
                    "The target may be empty, documentation-only, or unsupported."
                ),
                severity="high",
                evidence=[Evidence(file=".", kind="directory", note=facts.root)],
            )
        )

    return gaps
