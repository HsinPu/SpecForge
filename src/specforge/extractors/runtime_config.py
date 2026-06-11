from __future__ import annotations

import json
import re
from pathlib import Path

from specforge.models import Evidence, FileFact, RuntimeConfigFact


def extract_runtime_config_facts(root: Path, files: list[FileFact]) -> list[RuntimeConfigFact]:
    facts: list[RuntimeConfigFact] = []
    for file_fact in files:
        normalized = file_fact.path.replace("\\", "/")
        name = Path(normalized).name
        if file_fact.role == "test":
            continue
        path = root / file_fact.path
        if not path.exists():
            continue
        source = _read(path)

        if name in {".env.example", ".env.sample", ".env.template"}:
            facts.append(_env_fact(file_fact, source))
        elif name == "Dockerfile" or name.startswith("Dockerfile."):
            facts.append(_dockerfile_fact(file_fact, source))
        elif name in {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}:
            facts.append(_compose_fact(file_fact, source))
        elif normalized.startswith(".github/workflows/") and name.endswith((".yml", ".yaml")):
            facts.append(_github_actions_fact(file_fact, source))
        elif name in {"application.yml", "application.yaml", "application.properties"}:
            facts.append(_spring_config_fact(file_fact, source))
        elif name in {"vite.config.js", "vite.config.ts", "vite.config.mjs"}:
            facts.append(_js_config_fact(file_fact, source, "vite-config"))
        elif name in {"next.config.js", "next.config.ts", "next.config.mjs"}:
            facts.append(_js_config_fact(file_fact, source, "next-config"))
        elif name == "package.json":
            package_fact = _package_scripts_fact(file_fact, source)
            if package_fact:
                facts.append(package_fact)

    return _dedupe_facts(facts)


def _env_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    keys = []
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            keys.append(f"env-key:{key}")
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="env-example",
        name=Path(file_fact.path).name,
        values=_dedupe(keys),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _dockerfile_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = []
    values.extend(f"base:{item}" for item in re.findall(r"^\s*FROM\s+([^\s]+)", source, re.MULTILINE | re.IGNORECASE))
    values.extend(f"port:{item}" for item in re.findall(r"^\s*EXPOSE\s+(.+)$", source, re.MULTILINE | re.IGNORECASE))
    values.extend(f"cmd:{item.strip()}" for item in re.findall(r"^\s*CMD\s+(.+)$", source, re.MULTILINE | re.IGNORECASE))
    values.extend(f"entrypoint:{item.strip()}" for item in re.findall(r"^\s*ENTRYPOINT\s+(.+)$", source, re.MULTILINE | re.IGNORECASE))
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="dockerfile",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _compose_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = []
    in_services = False
    for line in source.splitlines():
        if re.match(r"^services:\s*$", line):
            in_services = True
            continue
        if in_services and line and not line.startswith((" ", "\t")):
            in_services = False
        if in_services:
            service_match = re.match(r"^\s{2}([A-Za-z0-9_.-]+):\s*$", line)
            if service_match:
                values.append(f"service:{service_match.group(1)}")
            port_match = re.search(r"['\"]?(\d{2,5}:\d{2,5})['\"]?", line)
            if port_match:
                values.append(f"port:{port_match.group(1)}")
            image_match = re.match(r"^\s+image:\s*([^\s#]+)", line)
            if image_match:
                values.append(f"image:{image_match.group(1)}")
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="docker-compose",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _github_actions_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = []
    values.extend(f"job:{name}" for name in re.findall(r"^\s{2}([A-Za-z0-9_-]+):\s*$", source, re.MULTILINE))
    values.extend(f"run:{command.strip()}" for command in re.findall(r"^\s*run:\s*(.+)$", source, re.MULTILINE))
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="github-actions",
        name=Path(file_fact.path).stem,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _spring_config_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = []
    values.extend(f"port:{item}" for item in re.findall(r"(?:server\.port\s*=\s*|port:\s*)(\d{2,5})", source))
    values.extend(f"profile:{item}" for item in re.findall(r"spring\.profiles\.active\s*=\s*([A-Za-z0-9_,.-]+)", source))
    values.extend(f"config-key:{item}" for item in re.findall(r"^([A-Za-z][A-Za-z0-9_.-]+)\s*=", source, re.MULTILINE)[:50])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="spring-config",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _js_config_fact(file_fact: FileFact, source: str, kind: str) -> RuntimeConfigFact:
    values = []
    values.extend(f"env-prefix:{item}" for item in re.findall(r"envPrefix\s*:\s*['\"]([^'\"]+)['\"]", source))
    values.extend(f"plugin:{item}" for item in re.findall(r"\b([A-Za-z_]\w*)\s*\(", source)[:20])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind=kind,
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _package_scripts_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact | None:
    try:
        data = json.loads(source)
    except json.JSONDecodeError:
        return None
    scripts = data.get("scripts", {})
    if not isinstance(scripts, dict):
        return None
    values = [f"script:{name}" for name in scripts]
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="package-scripts",
        name="package.json",
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _dedupe_facts(facts: list[RuntimeConfigFact]) -> list[RuntimeConfigFact]:
    seen: set[tuple[str, str, str]] = set()
    result: list[RuntimeConfigFact] = []
    for fact in facts:
        key = (fact.path, fact.kind, fact.name)
        if key in seen:
            continue
        seen.add(key)
        result.append(fact)
    return result
