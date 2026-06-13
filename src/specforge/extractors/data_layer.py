from __future__ import annotations

import json
import re
from pathlib import Path

from specforge.models import DataLayerFact, DataModelFact, Evidence, FileFact, RepositoryFact, ServiceFact


TYPEORM_ENTITY_CLASS_RE = re.compile(
    r"@\s*Entity(?:\s*\((?P<args>[^)]*)\))?"
    r"[\s\S]{0,600}?\b(?:export\s+)?(?:abstract\s+)?class\s+(?P<name>[A-Za-z_$][\w$]*)",
    re.MULTILINE,
)
TS_DATA_PROPERTY_RE = re.compile(
    r"^\s*(?:public|private|protected)?\s*(?:readonly\s+)?(?P<name>[A-Za-z_$][\w$]*)[?!]?\s*:\s*(?P<type>[^=;]+)",
    re.MULTILINE,
)
SWIFT_FLUENT_MODEL_RE = re.compile(
    r"^\s*(?:public\s+|internal\s+|private\s+|fileprivate\s+)?(?:final\s+)?class\s+"
    r"(?P<name>[A-Za-z_]\w*)\s*:\s*(?P<bases>[^{\n]+)\s*\{",
    re.MULTILINE,
)
SWIFT_FLUENT_PROPERTY_RE = re.compile(
    r"@(?P<wrapper>ID|Field|OptionalField|Parent|Children|Siblings|Timestamp)\s*(?:\((?P<args>[^)]*)\))?"
    r"\s*(?:\r?\n\s*)+(?:public\s+|internal\s+|private\s+|fileprivate\s+)?var\s+"
    r"(?P<name>[A-Za-z_]\w*)\s*:\s*(?P<type>[^=\n{]+)",
    re.MULTILINE,
)


def extract_data_layer_facts(
    root: Path,
    files: list[FileFact],
    data_models: list[DataModelFact],
    repositories: list[RepositoryFact],
    services: list[ServiceFact],
) -> list[DataLayerFact]:
    facts: list[DataLayerFact] = []

    for file_fact in files:
        if file_fact.role in {"test", "sample", "generated"} or _is_sample_data_path(file_fact.path):
            continue
        normalized = file_fact.path.replace("\\", "/")
        path = root / file_fact.path
        if not path.exists():
            continue
        source = _read(path)

        if normalized.endswith(".sql"):
            if _looks_like_dbt_macro(file_fact.path, source):
                facts.append(_dbt_macro_fact(file_fact, source))
            elif _looks_like_dbt_model(file_fact.path, source):
                facts.append(_dbt_model_fact(file_fact, source))
            else:
                facts.append(_sql_fact(file_fact, source))
        elif Path(normalized).name in {"dbt_project.yml", "dbt_project.yaml"}:
            facts.append(_dbt_project_fact(file_fact, source))
        elif normalized.endswith((".yml", ".yaml")):
            drupal_fact = _drupal_yaml_fact(file_fact, source)
            if drupal_fact:
                facts.append(drupal_fact)
            elif _looks_like_dbt_yaml(file_fact.path, source):
                facts.append(_dbt_yaml_fact(file_fact, source))
        elif normalized.endswith(".ipynb"):
            facts.append(_notebook_fact(file_fact, source))
        elif normalized.endswith("schema.prisma"):
            facts.append(_prisma_fact(file_fact, source))
        elif normalized.endswith("schema.json") and _looks_like_strapi_schema_path(normalized):
            strapi_fact = _strapi_schema_fact(file_fact, source)
            if strapi_fact:
                facts.append(strapi_fact)
        elif normalized.endswith(".xml") and ("<mapper" in source or normalized.endswith("Mapper.xml")):
            facts.append(_mybatis_xml_fact(file_fact, source))
        elif file_fact.language in {"java", "groovy"}:
            facts.extend(_java_data_facts(file_fact, source))
        elif file_fact.language == "kotlin":
            facts.extend(_kotlin_data_facts(file_fact, source))
        elif file_fact.language == "scala":
            facts.extend(_scala_data_facts(file_fact, source))
        elif file_fact.language == "php":
            facts.extend(_php_data_facts(file_fact, source))
        elif file_fact.language == "ruby":
            facts.extend(_ruby_data_facts(file_fact, source))
        elif file_fact.language == "elixir":
            facts.extend(_elixir_data_facts(file_fact, source))
        elif file_fact.language == "clojure":
            facts.extend(_clojure_data_facts(file_fact, source))
        elif file_fact.language == "csharp":
            facts.extend(_csharp_data_facts(file_fact, source))
        elif file_fact.language == "go":
            facts.extend(_go_data_facts(file_fact, source))
        elif file_fact.language == "swift":
            facts.extend(_swift_data_facts(file_fact, source))
        elif file_fact.language in {"typescript", "javascript"}:
            facts.extend(_typescript_data_facts(file_fact, source))
        elif file_fact.language == "python":
            facts.extend(_python_data_facts(file_fact, source))

    facts.extend(_existing_data_model_facts(data_models))
    facts.extend(_repository_link_facts(repositories))
    facts.extend(_service_link_facts(services, repositories, data_models))
    return _dedupe_facts(facts)


def _is_sample_data_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return any(marker in f"/{normalized}" for marker in ("/extra/sample", "/sample_plugin/", "/samples/", "/.semgrep/"))


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


def _looks_like_dbt_model(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return "/models/" in f"/{normalized}" or "{{" in source and ("ref(" in source or "source(" in source or "config(" in source)


def _looks_like_dbt_macro(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return normalized.endswith(".sql") and ("/macros/" in f"/{normalized}" or re.search(r"{%\s*macro\s+", source) is not None)


def _dbt_macro_fact(file_fact: FileFact, source: str) -> DataLayerFact:
    details = [f"macro:{name}" for name in re.findall(r"{%\s*macro\s+([A-Za-z_]\w*)\s*\(", source)]
    return DataLayerFact(
        path=file_fact.path,
        kind="dbt-macro",
        name=Path(file_fact.path).stem,
        details=_dedupe(details or ["macro:unknown"]),
        evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=_line_for_text(source, "{% macro"), line_end=_line_for_text(source, "{% macro")),
    )


def _dbt_model_fact(file_fact: FileFact, source: str) -> DataLayerFact:
    details = [f"model:{Path(file_fact.path).stem}"]
    details.extend(f"ref:{name}" for name in re.findall(r"\bref\(\s*['\"]([^'\"]+)['\"]", source))
    details.extend(f"source:{source_name}.{table}" for source_name, table in re.findall(r"\bsource\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]", source))
    materialized = _first_match(source, r"materialized\s*=\s*['\"]([^'\"]+)['\"]")
    if materialized:
        details.append(f"materialized:{materialized}")
    details.extend(f"macro:{name}" for name in re.findall(r"\{\{\s*([A-Za-z_]\w*)\s*\(", source) if name not in {"ref", "source", "config"})
    return DataLayerFact(
        path=file_fact.path,
        kind="dbt-model",
        name=Path(file_fact.path).stem,
        details=_dedupe(details),
        evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=1, line_end=1),
    )


def _looks_like_dbt_yaml(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    name = Path(normalized).name
    return (
        name in {"schema.yml", "schema.yaml", "sources.yml", "sources.yaml", "exposures.yml", "exposures.yaml", "metrics.yml", "metrics.yaml"}
        or "/models/" in f"/{normalized}" and any(marker in source for marker in ("models:", "sources:", "semantic_models:", "metrics:", "exposures:"))
    )


def _dbt_yaml_fact(file_fact: FileFact, source: str) -> DataLayerFact:
    details = _dbt_yaml_details(source)
    return DataLayerFact(
        path=file_fact.path,
        kind="dbt-yaml",
        name=Path(file_fact.path).name,
        details=_dedupe(details),
        evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=1, line_end=1),
    )


def _dbt_yaml_details(source: str) -> list[str]:
    details: list[str] = []
    section: str | None = None
    current_source: str | None = None
    source_tables_indent: int | None = None
    tests_indent: int | None = None
    section_prefixes = {
        "models": "model",
        "seeds": "seed",
        "snapshots": "snapshot",
        "semantic_models": "semantic-model",
        "metrics": "metric",
        "exposures": "exposure",
    }

    for line in source.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        top_level = re.match(r"^([A-Za-z_][\w.-]*):\s*(?:#.*)?$", line)
        if top_level:
            candidate = top_level.group(1)
            section = candidate if candidate in {*section_prefixes, "sources"} else None
            current_source = None
            source_tables_indent = None
            tests_indent = None
            if section:
                details.append(f"section:{section}")
            continue

        if not section:
            continue

        if tests_indent is not None and indent <= tests_indent:
            tests_indent = None
        if source_tables_indent is not None and indent <= source_tables_indent and stripped != "tables:":
            source_tables_indent = None

        if re.match(r"^(?:tests|data_tests):\s*(?:#.*)?$", stripped):
            tests_indent = indent
            continue
        if section == "sources" and re.match(r"^tables:\s*(?:#.*)?$", stripped):
            source_tables_indent = indent
            continue

        item = re.match(r"^-\s+name:\s*(.+?)\s*$", stripped)
        if item:
            name = _clean_yaml_value(item.group(1))
            if not name:
                continue
            if tests_indent is not None and indent > tests_indent:
                continue
            if section == "sources":
                if indent == 2:
                    current_source = name
                    details.append(f"source:{name}")
                elif source_tables_indent is not None and indent == source_tables_indent + 2 and current_source:
                    details.append(f"source-table:{current_source}.{name}")
            elif indent == 2:
                details.append(f"{section_prefixes[section]}:{name}")
            continue

        if tests_indent is not None and indent > tests_indent:
            test = re.match(r"^-\s+([A-Za-z_][\w.-]*):?\s*(?:#.*)?$", stripped)
            if test:
                details.append(f"test:{test.group(1)}")

    return _dedupe(details[:120])


def _clean_yaml_value(value: str) -> str:
    return value.split("#", 1)[0].strip().strip("\"'")


def _dbt_project_fact(file_fact: FileFact, source: str) -> DataLayerFact:
    details = []
    for key in ("name", "profile", "model-paths", "seed-paths", "macro-paths", "snapshot-paths"):
        value = _first_match(source, rf"^\s*{re.escape(key)}:\s*(.+)$")
        if value:
            cleaned = value.strip().strip("\"'")
            details.append(f"{key}:{cleaned}")
    return DataLayerFact(
        path=file_fact.path,
        kind="dbt-project",
        name=_first_match(source, r"^\s*name:\s*['\"]?([^'\"\n#]+)") or "dbt_project",
        details=_dedupe(details),
        evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=1, line_end=1),
    )


def _notebook_fact(file_fact: FileFact, source: str) -> DataLayerFact:
    code = _notebook_code(source)
    details = []
    try:
        data = json.loads(source)
    except json.JSONDecodeError:
        data = {}
    if isinstance(data, dict):
        cells = data.get("cells")
        if isinstance(cells, list):
            details.append(f"cells:{len(cells)}")
        kernelspec = data.get("metadata", {}).get("kernelspec", {}) if isinstance(data.get("metadata"), dict) else {}
        if isinstance(kernelspec, dict) and kernelspec.get("name"):
            details.append(f"kernel:{kernelspec['name']}")
    details.extend(_python_data_io_details(code))
    details.extend(_python_ml_details(code))
    details.extend(f"import:{name}" for name in _python_import_names(code)[:30])
    return DataLayerFact(
        path=file_fact.path,
        kind="notebook",
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


def _looks_like_strapi_schema_path(normalized_path: str) -> bool:
    return "/content-types/" in f"/{normalized_path}" or "/components/" in f"/{normalized_path}"


def _strapi_schema_fact(file_fact: FileFact, source: str) -> DataLayerFact | None:
    try:
        schema = json.loads(source)
    except json.JSONDecodeError:
        return None
    if not isinstance(schema, dict) or not isinstance(schema.get("attributes"), dict):
        return None
    info = schema.get("info") if isinstance(schema.get("info"), dict) else {}
    name = _string_value(info.get("singularName")) or _string_value(info.get("displayName")) or Path(file_fact.path).parent.name
    details: list[str] = []
    kind = _string_value(schema.get("kind"))
    collection = _string_value(schema.get("collectionName"))
    if kind:
        details.append(f"kind:{kind}")
    if collection:
        details.append(f"collection:{collection}")
    attributes = schema.get("attributes")
    if isinstance(attributes, dict):
        for field_name, raw_config in attributes.items():
            if not isinstance(field_name, str) or not isinstance(raw_config, dict):
                continue
            attr_type = _string_value(raw_config.get("type")) or "unknown"
            details.append(f"attribute:{field_name}:{attr_type}")
            if attr_type == "relation":
                relation = _string_value(raw_config.get("relation")) or "relation"
                target = _string_value(raw_config.get("target")) or "unknown"
                details.append(f"relation:{field_name}:{relation}:{target}")
            if attr_type == "component":
                component = _string_value(raw_config.get("component")) or "unknown"
                details.append(f"component:{field_name}:{component}")
            if attr_type == "dynamiczone":
                components = raw_config.get("components") if isinstance(raw_config.get("components"), list) else []
                if components:
                    details.append(f"dynamiczone:{field_name}:{'|'.join(str(item) for item in components)}")
    return DataLayerFact(
        path=file_fact.path,
        kind="strapi-schema",
        name=name,
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


def _typescript_data_facts(file_fact: FileFact, source: str) -> list[DataLayerFact]:
    facts: list[DataLayerFact] = []
    if _looks_like_adonis_migration(source):
        facts.append(_adonis_migration_fact(file_fact, source))
    if _looks_like_sequelize_source(source):
        facts.extend(_sequelize_facts(file_fact, source))
    if "drizzle" in source.lower():
        facts.append(_drizzle_fact(file_fact, source))
    if _looks_like_knex_source(source):
        facts.append(_knex_fact(file_fact, source))
    if _looks_like_typeorm_source(source):
        facts.extend(_typeorm_facts(file_fact, source))
    if _looks_like_loopback_repository_source(source):
        facts.append(_loopback_repository_fact(file_fact, source))
    if _looks_like_loopback_datasource_source(source):
        facts.append(_loopback_datasource_fact(file_fact, source))
    return facts


def _looks_like_sequelize_source(source: str) -> bool:
    return (
        "queryInterface.createTable" in source
        or "queryInterface.addColumn" in source
        or "queryInterface.addIndex" in source
        or "new Sequelize" in source
        or "sequelize.define" in source
    )


def _sequelize_facts(file_fact: FileFact, source: str) -> list[DataLayerFact]:
    facts: list[DataLayerFact] = []
    for match in re.finditer(r"\bqueryInterface\.createTable\(\s*['\"`](?P<table>[^'\"`]+)['\"`]\s*,\s*\{", source):
        fields_open = source.rfind("{", 0, match.end())
        fields_close = _find_matching_delimiter(source, fields_open, "{", "}") if fields_open >= 0 else None
        if fields_close is None:
            continue
        details = [f"table:{match.group('table')}"]
        details.extend(_sequelize_columns(source[fields_open + 1 : fields_close]))
        line = _line_for_offset(source, match.start())
        facts.append(
            DataLayerFact(
                path=file_fact.path,
                kind="sequelize-migration",
                name=Path(file_fact.path).stem,
                details=_dedupe(details),
                evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=line, line_end=line),
            )
        )
    config_details: list[str] = []
    if "new Sequelize" in source:
        config_details.append("connection:new Sequelize")
    config_details.extend(f"env-key:{key}" for key in re.findall(r"process\.env\.([A-Z0-9_]+)", source))
    if config_details:
        facts.append(
            DataLayerFact(
                path=file_fact.path,
                kind="sequelize-config",
                name=Path(file_fact.path).stem,
                details=_dedupe(config_details),
                evidence=Evidence(
                    file=file_fact.path,
                    kind="data-layer",
                    line_start=_line_for_first_text(source, ("new Sequelize", "process.env.")),
                    line_end=_line_for_first_text(source, ("new Sequelize", "process.env.")),
                ),
            )
        )
    return facts


def _sequelize_columns(source: str) -> list[str]:
    columns: list[str] = []
    for item in _split_js_top_level_commas(source):
        if ":" not in item:
            continue
        name, value = item.split(":", 1)
        column = name.strip().strip("'\"`")
        if not re.fullmatch(r"[A-Za-z_][\w$]*", column):
            continue
        columns.append(f"column:{column}:{_sequelize_type(value)}")
    return columns


def _sequelize_type(value: str) -> str:
    match = re.search(r"\bSequelize\.(?P<type>[A-Za-z_$][\w$]*)", value)
    if match:
        return match.group("type")
    return "unknown"


def _split_js_top_level_commas(source: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depths = {"{": 0, "[": 0, "(": 0}
    closing = {"}": "{", "]": "[", ")": "("}
    quote: str | None = None
    escaped = False
    for index, char in enumerate(source):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"', "`"}:
            quote = char
            continue
        if char in depths:
            depths[char] += 1
        elif char in closing:
            opener = closing[char]
            depths[opener] = max(0, depths[opener] - 1)
        elif char == "," and not any(depths.values()):
            part = source[start:index].strip()
            if part:
                parts.append(part)
            start = index + 1
    tail = source[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def _looks_like_knex_source(source: str) -> bool:
    lower = source.lower()
    if "knex" in lower and any(marker in source for marker in ("knex.schema", ".knex(", "knex(", "knexConnection(")):
        return True
    return "MetaTable." in source


def _knex_fact(file_fact: FileFact, source: str) -> DataLayerFact:
    details: list[str] = []
    if re.search(r"from\s+['\"]knex['\"]|require\(\s*['\"]knex['\"]\s*\)", source):
        details.append("import:knex")
    details.extend(f"knex-schema:{operation}" for operation in re.findall(r"\bknex\.schema\.([A-Za-z_]\w*)", source))
    details.extend(f"query-builder:{name}" for name in re.findall(r"\b(knexConnection|knex)\s*\(", source))
    details.extend(f"query-builder:{name}" for name in re.findall(r"\.(knexConnection|knex)\s*\(", source))
    details.extend(f"table:{table}" for table in re.findall(r"\b(?:knex|knexConnection)\(\s*['\"]([^'\"]+)['\"]", source))
    details.extend(f"table:{table}" for table in re.findall(r"\.(?:knex|knexConnection)\(\s*['\"]([^'\"]+)['\"]", source))
    details.extend(f"meta-table:{name}" for name in re.findall(r"\bMetaTable\.([A-Z][A-Z0-9_]*)", source))
    if "BaseModelSql" in source:
        details.append("base-model-sql")
    if "IBaseModelSqlV2" in source:
        details.append("base-model-sql-interface")
    return DataLayerFact(
        path=file_fact.path,
        kind="knex-query-builder",
        name=Path(file_fact.path).stem,
        details=_dedupe(details)[:80],
        evidence=Evidence(
            file=file_fact.path,
            kind="data-layer",
            line_start=_line_for_first_text(source, ("knex.schema", "knexConnection(", ".knex(", "MetaTable.", "BaseModelSql", "from 'knex'", 'from "knex"')),
            line_end=_line_for_first_text(source, ("knex.schema", "knexConnection(", ".knex(", "MetaTable.", "BaseModelSql", "from 'knex'", 'from "knex"')),
        ),
    )


def _looks_like_adonis_migration(source: str) -> bool:
    return "BaseSchema" in source and "this.schema." in source


def _adonis_migration_fact(file_fact: FileFact, source: str) -> DataLayerFact:
    table = _first_match(source, r"\btableName\s*=\s*['\"]([^'\"]+)['\"]")
    details: list[str] = []
    if table:
        details.append(f"table:{table}")
    details.extend(
        f"create-table:{name}"
        for name in re.findall(r"\bcreateTable\(\s*['\"]([^'\"]+)['\"]", source)
    )
    if "createTable(this.tableName" in source and table:
        details.append(f"create-table:{table}")
    details.extend(
        f"alter-table:{name}"
        for name in re.findall(r"\bthis\.schema\.table\(\s*['\"]([^'\"]+)['\"]", source)
    )
    if "this.schema.table(this.tableName" in source and table:
        details.append(f"alter-table:{table}")
    details.extend(
        f"drop-table:{name}"
        for name in re.findall(r"\bdropTable\(\s*['\"]([^'\"]+)['\"]", source)
    )
    if "dropTable(this.tableName" in source and table:
        details.append(f"drop-table:{table}")
    for column_type, column_name in re.findall(r"\btable\.([A-Za-z_]\w*)\(\s*['\"]([^'\"]+)['\"]", source):
        details.append(f"column:{column_name}:{column_type}")
    for reference in re.findall(r"\.references\(\s*['\"]([^'\"]+)['\"]", source):
        details.append(f"references:{reference}")
    return DataLayerFact(
        path=file_fact.path,
        kind="adonis-migration",
        name=Path(file_fact.path).stem,
        details=_dedupe(details),
        evidence=Evidence(
            file=file_fact.path,
            kind="data-layer",
            line_start=_line_for_first_text(source, ("BaseSchema", "this.schema.")),
            line_end=_line_for_first_text(source, ("BaseSchema", "this.schema.")),
        ),
    )


def _looks_like_loopback_repository_source(source: str) -> bool:
    return "DefaultCrudRepository" in source and "@loopback/repository" in source


def _loopback_repository_fact(file_fact: FileFact, source: str) -> DataLayerFact:
    class_name = _first_match(source, r"\bclass\s+([A-Za-z_$][\w$]*)\s+extends\s+DefaultCrudRepository")
    generic = _first_match(source, r"DefaultCrudRepository\s*<\s*([A-Za-z_$][\w$]*)")
    datasource = _first_match(source, r"@inject\(\s*['\"]datasources\.([^'\"]+)['\"]")
    super_model = _first_match(source, r"\bsuper\(\s*([A-Za-z_$][\w$]*)\s*,")
    details = _dedupe([
        f"model:{generic}" if generic else "",
        f"super-model:{super_model}" if super_model else "",
        f"datasource:{datasource}" if datasource else "",
        "base:DefaultCrudRepository",
    ])
    return DataLayerFact(
        path=file_fact.path,
        kind="loopback-repository",
        name=class_name or Path(file_fact.path).stem,
        details=details,
        evidence=Evidence(
            file=file_fact.path,
            kind="data-layer",
            line_start=_line_for_first_text(source, ("DefaultCrudRepository", "@loopback/repository")),
            line_end=_line_for_first_text(source, ("DefaultCrudRepository", "@loopback/repository")),
        ),
    )


def _looks_like_loopback_datasource_source(source: str) -> bool:
    return re.search(r"\bclass\s+[A-Za-z_$][\w$]*\s+extends\s+juggler\.DataSource\b", source) is not None and "@loopback/repository" in source


def _loopback_datasource_fact(file_fact: FileFact, source: str) -> DataLayerFact:
    class_name = _first_match(source, r"\bclass\s+([A-Za-z_$][\w$]*)\s+extends\s+juggler\.DataSource")
    name = _first_match(source, r"\bname\s*:\s*['\"]([^'\"]+)['\"]") or _first_match(source, r"dataSourceName\s*=\s*['\"]([^'\"]+)['\"]")
    connector = _first_match(source, r"\bconnector\s*:\s*['\"]([^'\"]+)['\"]")
    details = _dedupe([
        f"datasource:{name}" if name else "",
        f"connector:{connector}" if connector else "",
        "base:juggler.DataSource",
    ])
    return DataLayerFact(
        path=file_fact.path,
        kind="loopback-datasource",
        name=class_name or name or Path(file_fact.path).stem,
        details=details,
        evidence=Evidence(
            file=file_fact.path,
            kind="data-layer",
            line_start=_line_for_first_text(source, ("juggler.DataSource", "dataSourceName", "connector")),
            line_end=_line_for_first_text(source, ("juggler.DataSource", "dataSourceName", "connector")),
        ),
    )


def _looks_like_typeorm_source(source: str) -> bool:
    return (
        "from 'typeorm'" in source
        or 'from "typeorm"' in source
        or "require('typeorm')" in source
        or 'require("typeorm")' in source
        or "@Entity" in source
        or "TypeOrmModule" in source
        or "new DataSource" in source and "typeorm" in source.lower()
    )


def _typeorm_facts(file_fact: FileFact, source: str) -> list[DataLayerFact]:
    facts: list[DataLayerFact] = []
    for match in TYPEORM_ENTITY_CLASS_RE.finditer(source):
        name = match.group("name")
        table = _typeorm_entity_table(match.group("args") or "")
        open_brace = source.find("{", match.end() - 1)
        close_brace = _find_matching_delimiter(source, open_brace, "{", "}") if open_brace >= 0 else None
        class_body = source[open_brace + 1 : close_brace] if close_brace is not None else source[match.end() : _next_typescript_class_offset(source, match.end())]
        details = [f"table:{table}" if table else "", f"entity:{name}"]
        details.extend(_typeorm_entity_details(class_body))
        facts.append(
            DataLayerFact(
                path=file_fact.path,
                kind="typeorm-entity",
                name=name,
                details=_dedupe(details),
                evidence=Evidence(
                    file=file_fact.path,
                    kind="data-layer",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.start()),
                ),
            )
        )
    if "TypeOrmModule.forRoot" in source or "TypeOrmModule.forFeature" in source:
        details = []
        details.extend("module:forRoot" for _ in re.finditer(r"TypeOrmModule\.forRoot\b", source))
        for feature in re.findall(r"TypeOrmModule\.forFeature\(\s*\[([^\]]+)\]", source, re.DOTALL):
            details.extend(f"entity:{item}" for item in re.findall(r"\b([A-Za-z_]\w*)\b", feature))
        facts.append(
            DataLayerFact(
                path=file_fact.path,
                kind="typeorm-module",
                name=Path(file_fact.path).stem,
                details=_dedupe(details),
                evidence=Evidence(
                    file=file_fact.path,
                    kind="data-layer",
                    line_start=_line_for_first_text(source, ("TypeOrmModule.forRoot", "TypeOrmModule.forFeature")),
                    line_end=_line_for_first_text(source, ("TypeOrmModule.forRoot", "TypeOrmModule.forFeature")),
                ),
            )
        )
    if "new DataSource" in source or "DataSource(" in source:
        facts.append(
            DataLayerFact(
                path=file_fact.path,
                kind="typeorm-data-source",
                name=Path(file_fact.path).stem,
                details=_dedupe(re.findall(r"\btype\s*:\s*['\"]([^'\"]+)['\"]", source) or ["DataSource"]),
                evidence=Evidence(
                    file=file_fact.path,
                    kind="data-layer",
                    line_start=_line_for_first_text(source, ("new DataSource", "DataSource(")),
                    line_end=_line_for_first_text(source, ("new DataSource", "DataSource(")),
                ),
            )
        )
    return facts


def _typeorm_entity_table(args: str) -> str | None:
    direct = re.match(r"\s*['\"]([^'\"]+)['\"]", args)
    if direct:
        return direct.group(1)
    named = re.search(r"\b(?:name|tableName)\s*:\s*['\"]([^'\"]+)['\"]", args)
    return named.group(1) if named else None


def _typeorm_entity_details(class_body: str) -> list[str]:
    details: list[str] = []
    decorators: list[str] = []
    lines = class_body.splitlines()
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("@"):
            decorator_lines = [stripped]
            paren_depth = stripped.count("(") - stripped.count(")")
            index += 1
            while paren_depth > 0 and index < len(lines):
                continuation = lines[index].strip()
                decorator_lines.append(continuation)
                paren_depth += continuation.count("(") - continuation.count(")")
                index += 1
            decorators.append(" ".join(decorator_lines))
            continue
        property_match = TS_DATA_PROPERTY_RE.match(lines[index])
        if property_match:
            field_name = property_match.group("name")
            joined = " ".join(decorators)
            if re.search(r"@\s*(?:Column|PrimaryGeneratedColumn|PrimaryColumn|EntityId|Money)\b", joined):
                details.append(f"column:{field_name}")
            for relation in re.findall(r"@\s*(OneToOne|OneToMany|ManyToOne|ManyToMany)\b", joined):
                target = _typeorm_relation_target(joined) or "unknown"
                details.append(f"relation:{relation}:{field_name}:{target}")
            if "@JoinTable" in joined:
                details.append(f"join-table:{field_name}")
            if re.search(r"\bprimary\s*:\s*true\b", joined) or re.search(r"@\s*(?:PrimaryGeneratedColumn|PrimaryColumn)\b", joined):
                details.append(f"primary-key:{field_name}")
            if re.search(r"\bnullable\s*:\s*true\b", joined):
                details.append(f"nullable:{field_name}")
            decorators = []
        elif stripped and not stripped.startswith("//"):
            decorators = []
        index += 1
    return details


def _typeorm_relation_target(source: str) -> str | None:
    match = re.search(r"(?:type\s*=>|\(\s*\)\s*=>)\s*([A-Za-z_$][\w$]*)", source)
    return match.group(1) if match else None


def _next_typescript_class_offset(source: str, offset: int) -> int:
    match = re.search(r"\n\s*(?:export\s+)?class\s+[A-Za-z_]\w*", source[offset:])
    return offset + match.start() if match else len(source)


def _kotlin_data_facts(file_fact: FileFact, source: str) -> list[DataLayerFact]:
    facts: list[DataLayerFact] = []
    class_name = _first_match(source, r"\b(?:data\s+)?class\s+([A-Za-z_]\w*)") or _first_match(source, r"\binterface\s+([A-Za-z_]\w*)")
    if "@Entity" in source:
        table = _first_match(source, r"tableName\s*=\s*['\"]([^'\"]+)['\"]")
        details = _dedupe([f"table:{table}" if table else "", "annotation:@Entity"])
        facts.append(
            DataLayerFact(
                path=file_fact.path,
                kind="room-entity",
                name=class_name or Path(file_fact.path).stem,
                details=details,
                evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=_line_for_text(source, "@Entity"), line_end=_line_for_text(source, "@Entity")),
            )
        )
    if "@Dao" in source:
        queries = re.findall(r"@Query\(\s*['\"]([^'\"]+)['\"]", source)
        facts.append(
            DataLayerFact(
                path=file_fact.path,
                kind="room-dao",
                name=class_name or Path(file_fact.path).stem,
                details=_dedupe([f"query:{query}" for query in queries[:20]] or ["annotation:@Dao"]),
                evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=_line_for_text(source, "@Dao"), line_end=_line_for_text(source, "@Dao")),
            )
        )
    if "RoomDatabase" in source or "@Database" in source:
        facts.append(
            DataLayerFact(
                path=file_fact.path,
                kind="room-database",
                name=class_name or Path(file_fact.path).stem,
                details=_dedupe(re.findall(r"entities\s*=\s*\[([^\]]+)\]", source) or ["RoomDatabase"]),
                evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=_line_for_text(source, "@Database") or _line_for_text(source, "RoomDatabase"), line_end=_line_for_text(source, "@Database") or _line_for_text(source, "RoomDatabase")),
            )
        )
    if _looks_like_exposed_source(source):
        facts.append(_exposed_fact(file_fact, source))
    return facts


def _looks_like_exposed_source(source: str) -> bool:
    return (
        "org.jetbrains.exposed." in source
        or "SchemaUtils." in source
        or "transaction {" in source
        or re.search(r"\bobject\s+[A-Za-z_]\w*\s*:\s*(?:IntIdTable|LongIdTable|UUIDTable|Table)\b", source) is not None
    )


def _exposed_fact(file_fact: FileFact, source: str) -> DataLayerFact:
    details = ["library:exposed"]
    details.extend(
        f"table:{table or name}"
        for name, table in re.findall(
            r"\bobject\s+([A-Za-z_]\w*)\s*:\s*(?:IntIdTable|LongIdTable|UUIDTable|Table)\s*(?:\(\s*['\"]([^'\"]+)['\"]\s*\))?",
            source,
        )
    )
    details.extend(f"column:{name}" for name in re.findall(r"\b(?:varchar|integer|long|text|bool|datetime|date|uuid)\(\s*['\"]([^'\"]+)['\"]", source))
    for block in re.findall(r"\bSchemaUtils\.create(?:MissingTablesAndColumns)?\(\s*([^)]*)\)", source, re.DOTALL):
        details.extend(f"schema-create:{name}" for name in re.findall(r"\b([A-Z][A-Za-z0-9_]*)\b", block))
    if "transaction {" in source or re.search(r"\btransaction\s*\(", source):
        details.append("transaction")
    return DataLayerFact(
        path=file_fact.path,
        kind="exposed-data",
        name=Path(file_fact.path).stem,
        details=_dedupe(details),
        evidence=Evidence(
            file=file_fact.path,
            kind="data-layer",
            line_start=_line_for_first_text(source, ("org.jetbrains.exposed.", "SchemaUtils.", "transaction {", "IntIdTable", "Table(")),
            line_end=_line_for_first_text(source, ("org.jetbrains.exposed.", "SchemaUtils.", "transaction {", "IntIdTable", "Table(")),
        ),
    )


def _scala_data_facts(file_fact: FileFact, source: str) -> list[DataLayerFact]:
    lower_source = source.lower()
    if not any(marker in lower_source for marker in ("anorm", "slick.", "play.api.db", "databaseconfigprovider", "tablequery", "extends table[")):
        return []
    details: list[str] = []
    if "anorm" in lower_source:
        details.append("library:anorm")
    if "slick." in lower_source or "tablequery" in lower_source or "extends table[" in lower_source:
        details.append("library:slick")
    if "play.api.db" in lower_source:
        details.append("library:play-db")
    details.extend(
        f"table:{name}"
        for name in re.findall(r"extends\s+Table\[[^\]]+\]\s*\([^,\n]+,\s*['\"]([^'\"]+)['\"]", source)
    )
    details.extend(
        f"table-query:{name}"
        for name in re.findall(r"\bTableQuery\[[A-Za-z0-9_.#]+\]\s*\(\s*(?P<name>[A-Za-z_]\w*)", source)
    )
    details.extend(
        f"query-table:{name}"
        for name in re.findall(r"\b(?:from|join|update|into)\s+([A-Za-z_][\w.]*)", source, re.IGNORECASE)
        if _looks_like_table_identifier(name)
    )
    if not details:
        return []
    marker = "anorm" if "anorm" in lower_source else ("TableQuery" if "TableQuery" in source else "play.api.db")
    return [
        DataLayerFact(
            path=file_fact.path,
            kind="scala-data",
            name=Path(file_fact.path).stem,
            details=_dedupe(details),
            evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=_line_for_text(source, marker), line_end=_line_for_text(source, marker)),
        )
    ]


def _php_data_facts(file_fact: FileFact, source: str) -> list[DataLayerFact]:
    normalized = file_fact.path.replace("\\", "/").lower()
    facts: list[DataLayerFact] = []
    if "/database/migrations/" in f"/{normalized}" or "schema::" in source.lower():
        details = []
        details.extend(f"table:{name}" for name in re.findall(r"Schema::(?:create|table)\(\s*['\"]([^'\"]+)['\"]", source))
        details.extend(f"column:{name}" for name in re.findall(r"->(?:string|integer|bigInteger|uuid|boolean|dateTime|timestamp|text)\(\s*['\"]([^'\"]+)['\"]", source))
        if details:
            facts.append(
                DataLayerFact(
                    path=file_fact.path,
                    kind="laravel-migration",
                    name=Path(file_fact.path).stem,
                    details=_dedupe(details),
                    evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=_line_for_text(source, "Schema::"), line_end=_line_for_text(source, "Schema::")),
                )
            )
    if _looks_like_doctrine_entity(source):
        facts.append(_doctrine_entity_fact(file_fact, source))
    facts.extend(_wordpress_php_data_facts(file_fact, source))
    facts.extend(_drupal_php_data_facts(file_fact, source))
    return facts


def _drupal_yaml_fact(file_fact: FileFact, source: str) -> DataLayerFact | None:
    normalized = file_fact.path.replace("\\", "/").lower()
    name = Path(normalized).name
    kind: str | None = None
    if name.endswith(".schema.yml") or "/config/schema/" in f"/{normalized}":
        kind = "drupal-config-schema"
    elif name.endswith(".services.yml"):
        kind = "drupal-service-container"
    elif name.endswith(".libraries.yml"):
        kind = "drupal-library"
    elif name.endswith(".permissions.yml"):
        kind = "drupal-permissions"
    elif name.endswith(".links.menu.yml"):
        kind = "drupal-menu-links"
    elif name.endswith(".links.task.yml"):
        kind = "drupal-local-tasks"
    if not kind:
        return None
    details = _drupal_yaml_details(kind, source)
    if not details:
        return None
    return DataLayerFact(
        path=file_fact.path,
        kind=kind,
        name=Path(file_fact.path).name,
        details=_dedupe(details[: _drupal_yaml_detail_limit(kind)]),
        evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=1, line_end=1),
    )


def _drupal_yaml_details(kind: str, source: str) -> list[str]:
    details: list[str] = []
    current_top: str | None = None
    current_top_indent: int | None = None
    schema_mapping_indent: int | None = None
    inside_services = False
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        top = re.match(r"^([A-Za-z0-9_.:*%-]+):\s*(?:#.*)?$", line)
        if kind == "drupal-permissions" and indent == 0:
            permission = re.match(r"^([^:#][^:]*):\s*(?:#.*)?$", line)
            if permission:
                details.append(f"permission:{_clean_yaml_value(permission.group(1))}")
                continue
        if top and indent == 0:
            if kind == "drupal-service-container":
                inside_services = top.group(1) == "services"
                current_top = None
                current_top_indent = None
                continue
            current_top = top.group(1)
            current_top_indent = indent
            schema_mapping_indent = None
            prefix = {
                "drupal-config-schema": "schema",
                "drupal-service-container": "service",
                "drupal-library": "library",
                "drupal-permissions": "permission",
                "drupal-menu-links": "menu-link",
                "drupal-local-tasks": "local-task",
            }.get(kind, "item")
            details.append(f"{prefix}:{current_top}")
            continue
        if kind == "drupal-service-container" and inside_services and indent == 2:
            service = re.match(r"^([A-Za-z0-9_.-]+):\s*(?:#.*)?$", stripped)
            if service:
                current_top = service.group(1)
                current_top_indent = indent
                if current_top == "_defaults":
                    continue
                details.append(f"service:{current_top}")
                continue
        if current_top is None or current_top_indent is None or indent <= current_top_indent:
            continue
        if kind == "drupal-config-schema":
            typed = re.match(r"^type:\s*([^#]+)", stripped)
            label = re.match(r"^label:\s*['\"]?([^'\"]+?)['\"]?\s*(?:#.*)?$", stripped)
            mapping = re.match(r"^([A-Za-z_][\w.-]*):\s*(?:#.*)?$", stripped)
            if stripped == "mapping:" and indent == current_top_indent + 2:
                schema_mapping_indent = indent
            elif typed and indent == current_top_indent + 2:
                details.append(f"type:{current_top}:{_clean_yaml_value(typed.group(1))}")
            elif label and indent == current_top_indent + 2:
                details.append(f"label:{current_top}:{_clean_yaml_value(label.group(1))}")
            elif mapping and schema_mapping_indent is not None and indent == schema_mapping_indent + 2:
                details.append(f"field:{current_top}:{mapping.group(1)}")
        elif kind == "drupal-service-container":
            service_class = re.match(r"^class:\s*['\"]?([^'\"#]+)", stripped)
            tag = re.match(r"^-\s*\{\s*name:\s*([^,}]+)", stripped)
            if service_class:
                details.append(f"class:{current_top}:{_clean_yaml_value(service_class.group(1))}")
            elif tag:
                details.append(f"tag:{current_top}:{_clean_yaml_value(tag.group(1))}")
        elif kind == "drupal-library":
            asset = re.match(r"^([A-Za-z0-9_./@-]+\.(?:css|js)):\s*(?:\{\})?", stripped)
            dependency = re.match(r"^-\s*([A-Za-z0-9_./@-]+)\s*$", stripped)
            if asset:
                details.append(f"asset:{current_top}:{asset.group(1)}")
            elif dependency:
                details.append(f"dependency:{current_top}:{dependency.group(1)}")
        elif kind in {"drupal-menu-links", "drupal-local-tasks"}:
            route = re.match(r"^route_name:\s*['\"]?([^'\"#]+)", stripped)
            parent = re.match(r"^parent:\s*['\"]?([^'\"#]+)", stripped)
            if route:
                details.append(f"route:{current_top}:{_clean_yaml_value(route.group(1))}")
            elif parent:
                details.append(f"parent:{current_top}:{_clean_yaml_value(parent.group(1))}")
    return _dedupe(details)


def _drupal_yaml_detail_limit(kind: str) -> int:
    return {
        "drupal-config-schema": 60,
        "drupal-service-container": 80,
        "drupal-library": 80,
    }.get(kind, 80)


def _drupal_php_data_facts(file_fact: FileFact, source: str) -> list[DataLayerFact]:
    normalized = file_fact.path.replace("\\", "/").lower()
    if not (
        normalized.endswith((".install", ".module", ".profile", ".theme", ".php"))
        and (
            "ContentEntityType" in source
            or "ConfigEntityType" in source
            or "_schema(" in source
            or "BaseFieldDefinition::create" in source
            or "->schema()->" in source
        )
    ):
        return []
    details: list[str] = []
    details.extend(f"entity-attribute:{name}" for name in re.findall(r"#\[\s*(ContentEntityType|ConfigEntityType)\s*\(", source))
    details.extend(
        f"base-field:{name}:{field_type}"
        for name, field_type in re.findall(
            r"\$fields\[\s*['\"]([A-Za-z_][\w.-]*)['\"]\s*\]\s*=\s*BaseFieldDefinition::create\(\s*['\"]([^'\"]+)['\"]",
            source,
        )
    )
    details.extend(f"hook-schema:{name}" for name in re.findall(r"\bfunction\s+([A-Za-z_]\w*_schema)\s*\(", source))
    details.extend(f"table:{name}" for name in re.findall(r"\$schema\[\s*['\"]([^'\"]+)['\"]\s*\]", source))
    details.extend(f"create-table:{name}" for name in re.findall(r"->schema\(\)->createTable\(\s*['\"]([^'\"]+)['\"]", source))
    details.extend(f"drop-table:{name}" for name in re.findall(r"->schema\(\)->dropTable\(\s*['\"]([^'\"]+)['\"]", source))
    details.extend(f"field-type-schema:{name}" for name in re.findall(r"\bclass\s+([A-Za-z_]\w*)[\s\S]{0,800}\bpublic\s+static\s+function\s+schema\s*\(", source))
    if not details:
        return []
    return [
        DataLayerFact(
            path=file_fact.path,
            kind="drupal-php-data",
            name=Path(file_fact.path).stem,
            details=_dedupe(details[:160]),
            evidence=Evidence(
                file=file_fact.path,
                kind="data-layer",
                line_start=_line_for_first_text(source, ("ContentEntityType", "ConfigEntityType", "_schema", "BaseFieldDefinition", "->schema()")),
                line_end=_line_for_first_text(source, ("ContentEntityType", "ConfigEntityType", "_schema", "BaseFieldDefinition", "->schema()")),
            ),
        )
    ]


def _wordpress_php_data_facts(file_fact: FileFact, source: str) -> list[DataLayerFact]:
    details = _wordpress_table_details(source)
    data_store_details = _woocommerce_data_store_details(source)
    facts: list[DataLayerFact] = []
    if details:
        facts.append(
            DataLayerFact(
                path=file_fact.path,
                kind="wordpress-table-reference",
                name=Path(file_fact.path).stem,
                details=_dedupe(details[:120]),
                evidence=Evidence(
                    file=file_fact.path,
                    kind="data-layer",
                    line_start=_line_for_first_text(source, ("$wpdb->prefix", "CREATE TABLE", "dbDelta")),
                    line_end=_line_for_first_text(source, ("$wpdb->prefix", "CREATE TABLE", "dbDelta")),
                ),
            )
        )
    if data_store_details:
        facts.append(
            DataLayerFact(
                path=file_fact.path,
                kind="woocommerce-data-store",
                name=Path(file_fact.path).stem,
                details=_dedupe(data_store_details[:120]),
                evidence=Evidence(
                    file=file_fact.path,
                    kind="data-layer",
                    line_start=_line_for_first_text(source, ("WC_Data_Store", "DataStore", "data_store_name")),
                    line_end=_line_for_first_text(source, ("WC_Data_Store", "DataStore", "data_store_name")),
                ),
            )
        )
    return facts


def _wordpress_table_details(source: str) -> list[str]:
    details: list[str] = []
    details.extend(f"table:{name}" for name in re.findall(r"\{\$wpdb->prefix\}([A-Za-z_][\w]*)", source))
    details.extend(f"table:{name}" for name in re.findall(r"\$wpdb->prefix\s*\.\s*['\"]([A-Za-z_][\w]*)['\"]", source))
    details.extend(
        f"table:{name}"
        for name in re.findall(
            r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"]?\{\$wpdb->prefix\}([A-Za-z_][\w]*)",
            source,
            re.IGNORECASE,
        )
    )
    details.extend(
        f"alter:{name}"
        for name in re.findall(r"\bALTER\s+TABLE\s+[`\"]?\{\$wpdb->prefix\}([A-Za-z_][\w]*)", source, re.IGNORECASE)
    )
    details.extend(
        f"drop:{name}"
        for name in re.findall(
            r"\bDROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?[`\"]?\{\$wpdb->prefix\}([A-Za-z_][\w]*)",
            source,
            re.IGNORECASE,
        )
    )
    if "dbDelta" in source:
        details.append("migration:dbDelta")
    return _dedupe(details)


def _woocommerce_data_store_details(source: str) -> list[str]:
    details: list[str] = []
    details.extend(f"load:{name}" for name in re.findall(r"WC_Data_Store::load\(\s*['\"]([^'\"]+)['\"]", source))
    details.extend(f"data-store-name:{name}" for name in re.findall(r"\$data_store_name\s*=\s*['\"]([^'\"]+)['\"]", source))
    if re.search(r"\bclass\s+[A-Za-z_]\w*DataStore\b", source) or "DataStoreInterface" in source:
        class_name = _first_match(source, r"\bclass\s+([A-Za-z_]\w*)")
        details.append(f"class:{class_name or 'unknown'}")
    return _dedupe(details)


def _looks_like_doctrine_entity(source: str) -> bool:
    return (
        "@ORM\\Entity" in source
        or "#[ORM\\Entity" in source
        or "#[Entity" in source and "Doctrine\\ORM\\Mapping" in source
    )


def _doctrine_entity_fact(file_fact: FileFact, source: str) -> DataLayerFact:
    class_name = _first_match(source, r"\bclass\s+([A-Za-z_]\w*)") or Path(file_fact.path).stem
    details = [f"entity:{class_name}"]
    table = (
        _first_match(source, r"@ORM\\Table\s*\(\s*name\s*=\s*['\"]([^'\"]+)['\"]")
        or _first_match(source, r"#\[ORM\\Table\s*\(\s*name\s*:\s*['\"]([^'\"]+)['\"]")
    )
    if table:
        details.append(f"table:{table}")
    details.extend(f"column:{name}" for name in _doctrine_column_names(source))
    details.extend(f"relation:{name}" for name in re.findall(r"(?:@ORM\\|#\[ORM\\)(OneToOne|OneToMany|ManyToOne|ManyToMany)\b", source))
    repository = _first_match(source, r"repositoryClass\s*=\s*['\"]([^'\"]+)['\"]")
    if repository:
        details.append(f"repository:{repository}")
    line = _line_for_first_text(source, ("@ORM\\Entity", "#[ORM\\Entity", "#[Entity"))
    return DataLayerFact(
        path=file_fact.path,
        kind="doctrine-entity",
        name=class_name,
        details=_dedupe(details),
        evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=line, line_end=line),
    )


def _doctrine_column_names(source: str) -> list[str]:
    names: list[str] = []
    for match in re.finditer(r"(?:@ORM\\Column|#\[ORM\\Column)[\s\S]{0,260}?\b(?:private|protected|public)\s+[?\\A-Za-z_][\\\w|?]*\s+\$(?P<name>[A-Za-z_]\w*)", source):
        names.append(match.group("name"))
    return names


def _ruby_data_facts(file_fact: FileFact, source: str) -> list[DataLayerFact]:
    normalized = file_fact.path.replace("\\", "/").lower()
    if "/db/migrate/" not in f"/{normalized}" and "activerecord::migration" not in source.lower():
        return []
    details = []
    details.extend(f"table:{name}" for name in re.findall(r"\bcreate_table\s+:([A-Za-z_]\w*)", source))
    details.extend(f"table:{name}" for name in re.findall(r"\bchange_table\s+:([A-Za-z_]\w*)", source))
    details.extend(f"column:{name}" for name in re.findall(r"\bt\.\w+\s+:([A-Za-z_]\w*)", source))
    if not details:
        return []
    return [
        DataLayerFact(
            path=file_fact.path,
            kind="rails-migration",
            name=Path(file_fact.path).stem,
            details=_dedupe(details),
            evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=1, line_end=1),
        )
    ]


def _elixir_data_facts(file_fact: FileFact, source: str) -> list[DataLayerFact]:
    normalized = file_fact.path.replace("\\", "/").lower()
    if "/priv/repo/migrations/" not in f"/{normalized}" and "ecto.migration" not in source.lower():
        return []
    details = []
    details.extend(f"table:{name}" for name in re.findall(r"\btable\(\s*:([A-Za-z_]\w*)", source))
    details.extend(f"column:{name}" for name in re.findall(r"\badd\s*\(?\s*:([A-Za-z_]\w*)", source))
    details.extend(
        f"reference:{column}:{target}"
        for column, target in re.findall(r"\badd\s*\(?\s*:([A-Za-z_]\w*)\s*,\s*references\(\s*:([A-Za-z_]\w*)", source)
    )
    index_patterns = (
        r"\bcreate\s+(?:unique_)?index\(\s*:([A-Za-z_]\w*)\s*,\s*\[(?P<columns>[^\]]+)\]",
        r"\bcreate\s*\(\s*(?:unique_)?index\(\s*:([A-Za-z_]\w*)\s*,\s*\[(?P<columns>[^\]]+)\]",
    )
    for pattern in index_patterns:
        for table, columns in re.findall(pattern, source):
            index_columns = _elixir_index_columns(columns)
            if index_columns:
                details.append(f"index:{table}:{','.join(index_columns)}")
    if not details:
        return []
    return [
        DataLayerFact(
            path=file_fact.path,
            kind="ecto-migration",
            name=Path(file_fact.path).stem,
            details=_dedupe(details),
            evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=1, line_end=1),
        )
    ]


def _elixir_atom_names(source: str) -> list[str]:
    return re.findall(r":([A-Za-z_]\w*)", source)


def _elixir_index_columns(source: str) -> list[str]:
    columns = _elixir_atom_names(source)
    columns.extend(re.findall(r"['\"]([^'\"]+)['\"]", source))
    return _dedupe(columns)


def _clojure_data_facts(file_fact: FileFact, source: str) -> list[DataLayerFact]:
    active_source = _strip_clojure_comment_forms(source)
    active_source = "\n".join(line.split(";", 1)[0] for line in active_source.splitlines())
    has_jdbc_require = _clojure_has_jdbc_require(source)
    has_jdbc_call = re.search(r"(?m)^\s*\((?:jdbc|sql)/[A-Za-z0-9_.!?*-]+", active_source) is not None
    if not (has_jdbc_require or has_jdbc_call):
        return []
    details = []
    if _clojure_has_require(source, "next.jdbc"):
        details.append("library:next.jdbc")
    if _clojure_has_require(source, "clojure.java.jdbc"):
        details.append("library:clojure.java.jdbc")
    details.extend(f"dbtype:{name}" for name in re.findall(r":dbtype\s+['\"]([^'\"]+)['\"]", active_source))
    details.extend(f"dbname:{name}" for name in re.findall(r":dbname\s+['\"]([^'\"]+)['\"]", active_source))
    details.extend(
        f"table:{name}"
        for name in re.findall(r"\bcreate\s+table\s+(?:if\s+not\s+exists\s+)?([A-Za-z_][\w.]*)", active_source, re.IGNORECASE)
    )
    details.extend(
        f"query-table:{name}"
        for name in re.findall(r"\b(?:from|join)\s+([A-Za-z_][\w.]*)", active_source, re.IGNORECASE)
        if _looks_like_table_identifier(name)
    )
    details.extend(
        f"write-table:{name}"
        for name in re.findall(r"\bsql/(?:insert!|update!|delete!|get-by-id)\s+\([^)]*\)\s+:([A-Za-z_][\w-]*)", active_source)
    )
    if not details:
        return []
    line = _line_for_offset(source, _first_data_marker(source))
    return [
        DataLayerFact(
            path=file_fact.path,
            kind="clojure-jdbc-data",
            name=Path(file_fact.path).stem,
            details=_dedupe(details),
            evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=line, line_end=line),
        )
    ]


def _clojure_has_jdbc_require(source: str) -> bool:
    return _clojure_has_require(source, "next.jdbc") or _clojure_has_require(source, "clojure.java.jdbc")


def _clojure_has_require(source: str, namespace: str) -> bool:
    ns_form = _clojure_ns_form(source)
    return re.search(rf"\(:require[\s\S]{{0,1600}}?\[{re.escape(namespace)}\b", ns_form) is not None


def _clojure_ns_form(source: str) -> str:
    match = re.search(r"\(ns\b", source)
    if not match:
        return ""
    end = _clojure_matching_paren(source, match.start())
    return source[match.start() : end + 1] if end is not None else source[match.start() :]


def _strip_clojure_comment_forms(source: str) -> str:
    result: list[str] = []
    offset = 0
    while True:
        match = re.search(r"\(comment\b", source[offset:])
        if not match:
            result.append(source[offset:])
            break
        start = offset + match.start()
        result.append(source[offset:start])
        end = _clojure_matching_paren(source, start)
        if end is None:
            break
        result.append("\n" * source.count("\n", start, end + 1))
        offset = end + 1
    return "".join(result)


def _clojure_matching_paren(source: str, start: int) -> int | None:
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _first_data_marker(source: str) -> int:
    markers = [source.find(marker) for marker in ("next.jdbc", "clojure.java.jdbc", "jdbc/execute", "sql/query", "create table") if source.find(marker) != -1]
    return min(markers) if markers else 0


def _looks_like_table_identifier(name: str) -> bool:
    return name.lower() not in {"a", "an", "and", "by", "from", "in", "of", "on", "or", "the", "which", "with"}


def _csharp_data_facts(file_fact: FileFact, source: str) -> list[DataLayerFact]:
    lower_source = source.lower()
    if "migrationbuilder." not in lower_source and "dbset<" not in lower_source:
        return []
    details = []
    details.extend(f"table:{name}" for name in re.findall(r"CreateTable\(\s*name:\s*['\"]([^'\"]+)['\"]", source))
    details.extend(f"table:{name}" for name in re.findall(r"DbSet<[^>]+>\s+([A-Za-z_]\w*)", source))
    if not details:
        return []
    return [
        DataLayerFact(
            path=file_fact.path,
            kind="efcore-data",
            name=Path(file_fact.path).stem,
            details=_dedupe(details),
            evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=1, line_end=1),
        )
    ]


def _go_data_facts(file_fact: FileFact, source: str) -> list[DataLayerFact]:
    facts: list[DataLayerFact] = []
    if "gorm.io/gorm" in source or "gorm.Model" in source or "gorm:\"" in source:
        for match in re.finditer(r"\btype\s+([A-Za-z_]\w*)\s+struct\s*\{(?P<body>.*?)^\}", source, re.DOTALL | re.MULTILINE):
            name = match.group(1)
            body = match.group("body")
            if "gorm.Model" not in body and "gorm:\"" not in body:
                continue
            details = [f"model:{name}"]
            details.extend(f"column:{column}" for column in re.findall(r"gorm:\"[^\"]*column:([A-Za-z_]\w*)", body))
            details.extend(f"relation:{relation}" for relation in re.findall(r"gorm:\"[^\"]*(many2many:[^;\"\s]+|ForeignKey:[^;\"\s]+)", body))
            facts.append(
                DataLayerFact(
                    path=file_fact.path,
                    kind="gorm-model",
                    name=name,
                    details=_dedupe(details),
                    evidence=Evidence(
                        file=file_fact.path,
                        kind="data-layer",
                        line_start=_line_for_offset(source, match.start()),
                        line_end=_line_for_offset(source, match.start()),
                    ),
                )
            )
    if "gorm.Open" in source or "*gorm.DB" in source:
        line = _line_for_first_text(source, ("gorm.Open", "*gorm.DB"))
        facts.append(
            DataLayerFact(
                path=file_fact.path,
                kind="gorm-database",
                name=Path(file_fact.path).stem,
                details=_dedupe(re.findall(r"\bgorm\.Open\(\s*([A-Za-z_]\w*)\.", source) or ["gorm.DB"]),
                evidence=Evidence(
                    file=file_fact.path,
                    kind="data-layer",
                    line_start=line,
                    line_end=line,
                ),
            )
        )
    if "AutoMigrate" in source:
        models = re.findall(r"AutoMigrate\((?P<args>[^)]*)\)", source)
        details = []
        for args in models:
            details.extend(f"model:{name}" for name in re.findall(r"&?([A-Za-z_]\w*)\{\}", args))
        facts.append(
            DataLayerFact(
                path=file_fact.path,
                kind="gorm-migration",
                name=Path(file_fact.path).stem,
                details=_dedupe(details or ["AutoMigrate"]),
                evidence=Evidence(
                    file=file_fact.path,
                    kind="data-layer",
                    line_start=_line_for_text(source, "AutoMigrate"),
                    line_end=_line_for_text(source, "AutoMigrate"),
                ),
            )
        )
    return facts


def _swift_data_facts(file_fact: FileFact, source: str) -> list[DataLayerFact]:
    if "Fluent" not in source and ": Model" not in source and "CREATE TABLE" not in source.upper():
        return []
    facts: list[DataLayerFact] = []
    for match in SWIFT_FLUENT_MODEL_RE.finditer(source):
        bases = match.group("bases")
        if not any(base.strip().split(".")[-1] == "Model" for base in bases.split(",")):
            continue
        name = match.group("name")
        open_brace = source.find("{", match.end() - 1)
        close_brace = _find_matching_delimiter(source, open_brace, "{", "}") if open_brace >= 0 else None
        body = source[open_brace + 1 : close_brace] if close_brace is not None else source[match.end() : match.end() + 2200]
        details = [f"model:{name}"]
        schema = re.search(r"\bstatic\s+let\s+schema\s*=\s*['\"](?P<schema>[^'\"]+)['\"]", body)
        if schema:
            details.append(f"table:{schema.group('schema')}")
        details.extend(_swift_fluent_property_details(body))
        details.extend(_swift_raw_sql_details(source))
        facts.append(
            DataLayerFact(
                path=file_fact.path,
                kind="fluent-model",
                name=name,
                details=_dedupe(details),
                evidence=Evidence(
                    file=file_fact.path,
                    kind="data-layer",
                    line_start=_line_for_offset(source, match.start()),
                    line_end=_line_for_offset(source, match.start()),
                ),
            )
        )
    if facts:
        return facts
    raw_sql_details = _swift_raw_sql_details(source)
    if raw_sql_details:
        return [
            DataLayerFact(
                path=file_fact.path,
                kind="swift-sql",
                name=Path(file_fact.path).stem,
                details=_dedupe(raw_sql_details),
                evidence=Evidence(file=file_fact.path, kind="data-layer", line_start=1, line_end=1),
            )
        ]
    return []


def _swift_fluent_property_details(body: str) -> list[str]:
    details: list[str] = []
    for match in SWIFT_FLUENT_PROPERTY_RE.finditer(body):
        wrapper = match.group("wrapper")
        name = match.group("name")
        field_type = " ".join(match.group("type").strip().split())
        key = _swift_wrapper_key(match.group("args") or "")
        details.append(f"field:{name}:{field_type}")
        if key:
            details.append(f"column:{key}")
        if wrapper in {"Parent", "Children", "Siblings"}:
            details.append(f"relation:{wrapper.lower()}:{name}:{field_type}")
        else:
            details.append(f"wrapper:{wrapper}:{name}")
    return details


def _swift_raw_sql_details(source: str) -> list[str]:
    details: list[str] = []
    details.extend(
        f"sql-table:{name}"
        for name in re.findall(
            r"\bCREATE[ \t]+TABLE[ \t]+(?:IF[ \t]+NOT[ \t]+EXISTS[ \t]+)?[`\"]?([A-Za-z_]\w*)",
            source,
            re.IGNORECASE,
        )
        if name.upper() != "IF"
    )
    details.extend(f"sql-column:{name}" for name in re.findall(r"(?m)^\s*`([A-Za-z_]\w*)`\s+[A-Za-z]", source))
    details.extend(f"sql-index:{name}" for name in re.findall(r"\b(?:UNIQUE\s+)?KEY\s+`([^`]+)`", source, re.IGNORECASE))
    return details


def _swift_wrapper_key(args: str) -> str | None:
    key = re.search(r"\bkey\s*:\s*['\"](?P<key>[^'\"]+)['\"]", args)
    if key:
        return key.group("key")
    custom = re.search(r"\bcustom\s*:\s*\.?(?P<key>[A-Za-z_]\w*)", args)
    if custom:
        return custom.group("key")
    return None


def _python_data_facts(file_fact: FileFact, source: str) -> list[DataLayerFact]:
    facts: list[DataLayerFact] = []
    data_io_details = _python_data_io_details(source)
    workflow_details = _python_workflow_details(source)
    if data_io_details or workflow_details:
        facts.append(
            DataLayerFact(
                path=file_fact.path,
                kind="python-data-pipeline",
                name=Path(file_fact.path).stem,
                details=_dedupe([*workflow_details, *data_io_details]),
                evidence=Evidence(
                    file=file_fact.path,
                    kind="data-layer",
                    line_start=_line_for_first_text(source, ("read_csv", "read_parquet", "SparkSession", "@dag", "@flow", "@asset", "Pipeline(", "node(")),
                    line_end=_line_for_first_text(source, ("read_csv", "read_parquet", "SparkSession", "@dag", "@flow", "@asset", "Pipeline(", "node(")),
                ),
            )
        )
    ml_details = _python_ml_details(source)
    if ml_details:
        facts.append(
            DataLayerFact(
                path=file_fact.path,
                kind="ml-pipeline",
                name=Path(file_fact.path).stem,
                details=_dedupe(ml_details),
                evidence=Evidence(
                    file=file_fact.path,
                    kind="data-layer",
                    line_start=_line_for_first_text(source, ("import torch", "from torch", "tensorflow", "sklearn", "transformers", "mlflow", "wandb", "streamlit", "gradio", "nn.Module", "DataLoader(")),
                    line_end=_line_for_first_text(source, ("import torch", "from torch", "tensorflow", "sklearn", "transformers", "mlflow", "wandb", "streamlit", "gradio", "nn.Module", "DataLoader(")),
                ),
            )
        )
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


def _python_data_io_details(source: str) -> list[str]:
    details: list[str] = []
    for call in re.findall(r"\b(?:pd\.)?read_(csv|parquet|json|excel|sql|table)\s*\(\s*([^)\\n]+)", source):
        kind, arg = call
        details.append(f"read:{kind}:{_first_literal(arg) or 'unknown'}")
    for call in re.findall(r"\.to_(csv|parquet|json|excel|sql)\s*\(\s*([^)\\n]*)", source):
        kind, arg = call
        details.append(f"write:{kind}:{_first_literal(arg) or 'unknown'}")
    if "SparkSession" in source or "pyspark" in source or "spark." in source or "spark.read" in source or "readStream" in source:
        for format_name in re.findall(r"\.format\(\s*['\"]([^'\"]+)['\"]", source):
            details.append(f"spark-format:{format_name}")
    for path in re.findall(r"\b(?:spark\.read|readStream)\.[A-Za-z_]\w*\(\s*['\"]([^'\"]+)['\"]", source):
        details.append(f"spark-read:{path}")
    for table in re.findall(r"\bspark\.table\(\s*['\"]([^'\"]+)['\"]", source):
        details.append(f"spark-table:{table}")
    return _dedupe(details)


def _python_ml_details(source: str) -> list[str]:
    details: list[str] = []
    markers = [
        ("framework:pytorch", re.search(r"^(?:import|from)\s+torch\b", source, re.MULTILINE) is not None or "nn.Module" in source),
        ("framework:pytorch-lightning", "LightningModule" in source or "pytorch_lightning" in source or "lightning.pytorch" in source),
        ("framework:tensorflow", re.search(r"^(?:import|from)\s+tensorflow\b", source, re.MULTILINE) is not None or "tf.keras" in source),
        ("framework:keras", re.search(r"^(?:import|from)\s+keras\b", source, re.MULTILINE) is not None or "keras.models" in source),
        ("framework:scikit-learn", re.search(r"^(?:import|from)\s+sklearn\b", source, re.MULTILINE) is not None),
        ("framework:transformers", re.search(r"^(?:import|from)\s+transformers\b", source, re.MULTILINE) is not None or "AutoModel" in source or "AutoTokenizer" in source),
        ("framework:mlflow", re.search(r"^(?:import|from)\s+mlflow\b", source, re.MULTILINE) is not None or "mlflow." in source),
        ("framework:wandb", re.search(r"^(?:import|from)\s+wandb\b", source, re.MULTILINE) is not None or "wandb." in source),
        ("framework:hydra", "@hydra.main" in source or "hydra.compose" in source or "OmegaConf" in source),
        ("framework:streamlit", "import streamlit" in source or "streamlit." in source or re.search(r"\bst\.(?:title|write|sidebar|button|dataframe|plotly_chart)\b", source) is not None),
        ("framework:gradio", "import gradio" in source or "gradio." in source or re.search(r"\bgr\.(?:Interface|Blocks|ChatInterface|TabbedInterface)\b", source) is not None),
    ]
    details.extend(value for value, matched in markers if matched)
    details.extend(
        f"model-class:{name}"
        for name in re.findall(r"^\s*class\s+([A-Za-z_]\w*)\s*\([^)]*(?:nn\.Module|LightningModule|tf\.keras\.Model|keras\.Model)[^)]*\)", source, re.MULTILINE)[:40]
    )
    details.extend(f"dataset-class:{name}" for name in re.findall(r"^\s*class\s+([A-Za-z_]\w*)\s*\([^)]*Dataset[^)]*\)", source, re.MULTILINE)[:40])
    details.extend(f"train-function:{name}" for name in re.findall(r"^\s*def\s+(train(?:_[A-Za-z_]\w*)?|fit(?:_[A-Za-z_]\w*)?)\s*\(", source, re.MULTILINE)[:40])
    has_ml_context = bool(details)
    if has_ml_context:
        details.extend(f"eval-function:{name}" for name in re.findall(r"^\s*def\s+((?:evaluate|eval|test|validate)(?:_[A-Za-z_]\w*)?)\s*\(", source, re.MULTILINE)[:40])
    if has_ml_context and "DataLoader(" in source:
        details.append("data-loader:DataLoader")
    if has_ml_context and ("mlflow.log_metric" in source or "mlflow.log_param" in source or "mlflow.start_run" in source):
        details.append("tracking:mlflow")
    if has_ml_context and ("wandb.log" in source or "wandb.init" in source):
        details.append("tracking:wandb")
    if has_ml_context and re.search(r"\.(?:save|save_model|save_pretrained)\s*\(", source):
        details.append("artifact:model-save")
    if has_ml_context and re.search(r"\.(?:load|load_state_dict|from_pretrained)\s*\(", source):
        details.append("artifact:model-load")
    return _dedupe(details)


def _python_workflow_details(source: str) -> list[str]:
    details = []
    details.extend(f"airflow-dag:{name}" for name in re.findall(r"\bdag_id\s*=\s*['\"]([^'\"]+)['\"]", source))
    details.extend(f"prefect-flow:{name}" for name in re.findall(r"@flow(?:\([^)]*name\s*=\s*['\"]([^'\"]+)['\"][^)]*\))?", source) if name)
    details.extend(f"dagster-asset:{name}" for name in re.findall(r"@asset(?:\([^)]*\))?\s*\n\s*def\s+([A-Za-z_]\w*)", source))
    if "kedro" in source.lower():
        details.extend(f"kedro-node:{name}" for name in re.findall(r"\bnode\(\s*(?:func\s*=\s*)?([A-Za-z_]\w*)", source))
    if "SparkSession" in source or "pyspark" in source:
        details.append("spark:SparkSession")
    return _dedupe(details)


def _python_import_names(source: str) -> list[str]:
    names = []
    names.extend(re.findall(r"^\s*import\s+([A-Za-z_][\w.]*)", source, re.MULTILINE))
    names.extend(re.findall(r"^\s*from\s+([A-Za-z_][\w.]*)\s+import\b", source, re.MULTILINE))
    return _dedupe(names)


def _notebook_code(source: str) -> str:
    try:
        data = json.loads(source)
    except json.JSONDecodeError:
        return source
    cells = data.get("cells") if isinstance(data, dict) else None
    if not isinstance(cells, list):
        return source
    snippets: list[str] = []
    for cell in cells:
        if not isinstance(cell, dict) or cell.get("cell_type") != "code":
            continue
        raw_source = cell.get("source", "")
        if isinstance(raw_source, list):
            snippets.append("".join(str(line) for line in raw_source))
        elif isinstance(raw_source, str):
            snippets.append(raw_source)
    return "\n".join(snippets)


def _first_literal(expression: str) -> str | None:
    match = re.search(r"['\"]([^'\"]+)['\"]", expression)
    if match:
        return match.group(1)
    return None


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


def _find_matching_delimiter(source: str, start: int, open_char: str, close_char: str) -> int | None:
    if start < 0 or start >= len(source) or source[start] != open_char:
        return None
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"', "`"}:
            quote = char
            continue
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return index
    return None


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _first_match(source: str, pattern: str) -> str | None:
    match = re.search(pattern, source, re.MULTILINE)
    return match.group(1) if match else None


def _string_value(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _line_for_text(source: str, text: str) -> int:
    index = source.find(text)
    return source.count("\n", 0, index) + 1 if index >= 0 else 1


def _line_for_offset(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _line_for_first_text(source: str, values: tuple[str, ...]) -> int:
    offsets = [source.find(value) for value in values]
    offsets = [offset for offset in offsets if offset >= 0]
    return _line_for_offset(source, min(offsets)) if offsets else 1


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
