from __future__ import annotations

import re
from pathlib import Path

from specforge.models import ApiRouteFact, CommandFact, ComponentFact, DataModelFact, Evidence, FileFact, RepositoryFact, ServiceFact, TestMapFact


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
        source = _read(root / test_file.path)
        haystack = f"{test_file.path}\n{source}".lower()
        match = (
            _match_api_route(haystack, api_routes)
            or _match_component(haystack, components)
            or _match_command(haystack, commands)
            or _match_named_fact(haystack, "service", [(item.name, item.path) for item in services])
            or _match_named_fact(haystack, "repository", [(item.name, item.path) for item in repositories])
            or _match_named_fact(haystack, "data-model", [(item.name, item.path) for item in data_models])
        )
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


def _match_api_route(
    haystack: str,
    api_routes: list[ApiRouteFact],
) -> tuple[str, str, str] | None:
    for route in api_routes:
        path = route.path.lower()
        if path in haystack:
            return "api-route", f"{route.method} {route.path}", "high"
        tokens = [token for token in re.split(r"[/{}:<>\[\]-]+", path) if token and not token.startswith(":")]
        if tokens and all(token in haystack for token in tokens[:3]):
            return "api-route", f"{route.method} {route.path}", "medium"
    return None


def _match_component(
    haystack: str,
    components: list[ComponentFact],
) -> tuple[str, str, str] | None:
    for component in components:
        name = component.name.lower()
        if name and name in haystack:
            return "component", component.name, "high"
        stem = Path(component.path).stem.lower()
        if stem and stem in haystack:
            return "component", component.name, "medium"
    return None


def _match_command(
    haystack: str,
    commands: list[CommandFact],
) -> tuple[str, str, str] | None:
    for command in commands:
        name = command.name.lower()
        if name and name in haystack:
            return "cli-command", command.name, "medium"
    return None


def _match_named_fact(
    haystack: str,
    kind: str,
    candidates: list[tuple[str, str]],
) -> tuple[str, str, str] | None:
    for name, path in candidates:
        lowered = name.lower()
        if lowered and lowered in haystack:
            return kind, name, "medium"
        stem = Path(path).stem.lower()
        if stem and stem in haystack:
            return kind, name, "medium"
    return None


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")
