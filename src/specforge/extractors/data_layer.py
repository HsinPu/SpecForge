from __future__ import annotations

import re
from pathlib import Path

from specforge.models import DataLayerFact, DataModelFact, Evidence, FileFact, RepositoryFact, ServiceFact


def extract_data_layer_facts(
    root: Path,
    files: list[FileFact],
    data_models: list[DataModelFact],
    repositories: list[RepositoryFact],
    services: list[ServiceFact],
) -> list[DataLayerFact]:
    facts: list[DataLayerFact] = []

    for file_fact in files:
        if file_fact.role in {"test", "sample"}:
            continue
        normalized = file_fact.path.replace("\\", "/")
        path = root / file_fact.path
        if not path.exists():
            continue
        source = _read(path)

        if normalized.endswith(".sql"):
            facts.append(_sql_fact(file_fact, source))
        elif normalized.endswith("schema.prisma"):
            facts.append(_prisma_fact(file_fact, source))
        elif normalized.endswith(".xml") and ("<mapper" in source or normalized.endswith("Mapper.xml")):
            facts.append(_mybatis_xml_fact(file_fact, source))
        elif file_fact.language == "java":
            facts.extend(_java_data_facts(file_fact, source))
        elif file_fact.language in {"typescript", "javascript"} and "drizzle" in source.lower():
            facts.append(_drizzle_fact(file_fact, source))
        elif file_fact.language == "python":
            facts.extend(_python_data_facts(file_fact, source))

    facts.extend(_existing_data_model_facts(data_models))
    facts.extend(_repository_link_facts(repositories))
    facts.extend(_service_link_facts(services, repositories, data_models))
    return _dedupe_facts(facts)


def _sql_fact(file_fact: FileFact, source: str) -> DataLayerFact:
    kind = "sql-migration" if _looks_like_migration(file_fact.path) else "sql"
    details = []
    details.extend(f"table:{name}" for name in re.findall(r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"]?([A-Za-z_][\w.]*)", source, re.IGNORECASE))
    details.extend(f"index:{name}" for name in re.findall(r"\bCREATE\s+INDEX\s+[`\"]?([A-Za-z_]\w*)", source, re.IGNORECASE))
    details.extend(f"alter:{name}" for name in re.findall(r"\bALTER\s+TABLE\s+[`\"]?([A-Za-z_][\w.]*)", source, re.IGNORECASE))
    return DataLayerFact(
        path=file_fact.path,
        kind=kind,
        name=Path(file_fact.path).name,
        details=_dedupe(details),
        evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=1, line_end=1),
    )


def _prisma_fact(file_fact: FileFact, source: str) -> DataLayerFact:
    details = []
    details.extend(f"model:{name}" for name in re.findall(r"^\s*model\s+([A-Za-z_]\w*)", source, re.MULTILINE))
    details.extend(f"datasource:{name}" for name in re.findall(r"^\s*datasource\s+([A-Za-z_]\w*)", source, re.MULTILINE))
    details.extend(f"generator:{name}" for name in re.findall(r"^\s*generator\s+([A-Za-z_]\w*)", source, re.MULTILINE))
    return DataLayerFact(
        path=file_fact.path,
        kind="prisma-schema",
        name="schema.prisma",
        details=_dedupe(details),
        evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=1, line_end=1),
    )


def _mybatis_xml_fact(file_fact: FileFact, source: str) -> DataLayerFact:
    namespace = _first_match(source, r"<mapper\b[^>]*namespace=['\"]([^'\"]+)['\"]")
    details = []
    details.extend(f"namespace:{namespace}" for namespace in [namespace] if namespace)
    details.extend(f"statement:{name}" for name in re.findall(r"<(?:select|insert|update|delete)\b[^>]*id=['\"]([^'\"]+)['\"]", source))
    return DataLayerFact(
        path=file_fact.path,
        kind="mybatis-mapper",
        name=namespace or Path(file_fact.path).stem,
        details=_dedupe(details),
        evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=_line_for_text(source, "<mapper"), line_end=_line_for_text(source, "<mapper")),
    )


def _java_data_facts(file_fact: FileFact, source: str) -> list[DataLayerFact]:
    facts: list[DataLayerFact] = []
    class_name = _first_match(source, r"\b(?:class|interface)\s+([A-Za-z_]\w*)")
    if "@Mapper" in source:
        facts.append(
            DataLayerFact(
                path=file_fact.path,
                kind="mybatis-mapper",
                name=class_name or Path(file_fact.path).stem,
                details=["annotation:@Mapper"],
                evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=_line_for_text(source, "@Mapper"), line_end=_line_for_text(source, "@Mapper")),
            )
        )
    if "@Entity" in source:
        details = []
        table = _first_match(source, r"@Table\s*\(\s*name\s*=\s*['\"]([^'\"]+)['\"]")
        if table:
            details.append(f"table:{table}")
        details.extend(f"relation:{annotation}" for annotation in re.findall(r"@(OneToOne|OneToMany|ManyToOne|ManyToMany)\b", source))
        facts.append(
            DataLayerFact(
                path=file_fact.path,
                kind="jpa-entity",
                name=class_name or Path(file_fact.path).stem,
                details=_dedupe(details or ["annotation:@Entity"]),
                evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=_line_for_text(source, "@Entity"), line_end=_line_for_text(source, "@Entity")),
            )
        )
    return facts


def _drizzle_fact(file_fact: FileFact, source: str) -> DataLayerFact:
    details = []
    details.extend(f"table:{name}" for name in re.findall(r"\b(?:pgTable|mysqlTable|sqliteTable)\(\s*['\"]([^'\"]+)['\"]", source))
    details.extend(f"import:{module}" for module in re.findall(r"from\s+['\"]([^'\"]*drizzle[^'\"]*)['\"]", source))
    return DataLayerFact(
        path=file_fact.path,
        kind="drizzle",
        name=Path(file_fact.path).stem,
        details=_dedupe(details),
        evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=_line_for_text(source, "drizzle"), line_end=_line_for_text(source, "drizzle")),
    )


def _python_data_facts(file_fact: FileFact, source: str) -> list[DataLayerFact]:
    facts: list[DataLayerFact] = []
    if "sqlalchemy" in source.lower() or "Column(" in source or "mapped_column(" in source:
        classes = re.findall(r"^\s*class\s+([A-Za-z_]\w*)\s*\([^)]*(?:Base|DeclarativeBase|db\.Model)[^)]*\)", source, re.MULTILINE)
        details = [f"model:{name}" for name in classes]
        details.extend(f"table:{name}" for name in re.findall(r"__tablename__\s*=\s*['\"]([^'\"]+)['\"]", source))
        facts.append(
            DataLayerFact(
                path=file_fact.path,
                kind="sqlalchemy",
                name=Path(file_fact.path).stem,
                details=_dedupe(details),
                evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=_line_for_text(source, "sqlalchemy") or _line_for_text(source, "Column("), line_end=_line_for_text(source, "sqlalchemy") or _line_for_text(source, "Column(")),
            )
        )
    if _looks_like_django_migration(file_fact.path, source):
        operations = re.findall(r"\bmigrations\.(CreateModel|AddField|AlterField|RemoveField|RunPython|RunSQL)\b", source)
        facts.append(
            DataLayerFact(
                path=file_fact.path,
                kind="django-migration",
                name=Path(file_fact.path).stem,
                details=_dedupe([f"operation:{name}" for name in operations] or ["migration"]),
                evidence=Evidence(
                    file=file_fact.path,
                    kind="data-layer",
                    line_start=_line_for_text(source, "migrations.Migration"),
                    line_end=_line_for_text(source, "migrations.Migration"),
                ),
            )
        )
    if "models.Model" in source:
        classes = re.findall(r"^\s*class\s+([A-Za-z_]\w*)\s*\([^)]*models\.Model[^)]*\)", source, re.MULTILINE)
        if not classes:
            return facts
        facts.append(
            DataLayerFact(
                path=file_fact.path,
                kind="django-model",
                name=Path(file_fact.path).stem,
                details=[f"model:{name}" for name in classes],
                evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=_line_for_text(source, "models.Model") or _line_for_text(source, "django.db"), line_end=_line_for_text(source, "models.Model") or _line_for_text(source, "django.db")),
            )
        )
    return facts


def _looks_like_django_migration(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return "/migrations/" in f"/{normalized}" and "migrations.Migration" in source


def _existing_data_model_facts(data_models: list[DataModelFact]) -> list[DataLayerFact]:
    return [
        DataLayerFact(
            path=model.path,
            kind=f"code-model:{model.kind}",
            name=model.name,
            details=[*model.fields, *model.annotations],
            evidence=model.evidence,
        )
        for model in data_models
    ]


def _repository_link_facts(repositories: list[RepositoryFact]) -> list[DataLayerFact]:
    return [
        DataLayerFact(
            path=repository.path,
            kind="repository",
            name=repository.name,
            details=_dedupe([
                f"entity:{repository.entity}" if repository.entity else "",
                f"base:{repository.base_interface}" if repository.base_interface else "",
            ]),
            evidence=repository.evidence,
        )
        for repository in repositories
    ]


def _service_link_facts(
    services: list[ServiceFact],
    repositories: list[RepositoryFact],
    data_models: list[DataModelFact],
) -> list[DataLayerFact]:
    repository_names = {repository.name for repository in repositories}
    model_names = {model.name for model in data_models}
    facts: list[DataLayerFact] = []
    for service in services:
        details = []
        details.extend(f"repository-name-match:{name}" for name in repository_names if name.removesuffix("Repository") in service.name)
        details.extend(f"model-name-match:{name}" for name in model_names if name.removesuffix("Entity") in service.name)
        if not details:
            continue
        facts.append(
            DataLayerFact(
                path=service.path,
                kind="service-data-link",
                name=service.name,
                details=_dedupe(details),
                evidence=service.evidence,
            )
        )
    return facts


def _looks_like_migration(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return "/migration" in normalized or "/migrations" in normalized or bool(re.search(r"\bV\d+__", Path(path).name))


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _first_match(source: str, pattern: str) -> str | None:
    match = re.search(pattern, source)
    return match.group(1) if match else None


def _line_for_text(source: str, text: str) -> int:
    index = source.find(text)
    return source.count("\n", 0, index) + 1 if index >= 0 else 1


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _dedupe_facts(facts: list[DataLayerFact]) -> list[DataLayerFact]:
    seen: set[tuple[str, str, str]] = set()
    result: list[DataLayerFact] = []
    for fact in facts:
        key = (fact.path, fact.kind, fact.name)
        if key in seen:
            continue
        seen.add(key)
        result.append(fact)
    return result
