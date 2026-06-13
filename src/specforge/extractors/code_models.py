from __future__ import annotations

import json
import re
from pathlib import Path

from specforge.models import DataModelFact, Evidence, FileFact


GO_STRUCT_RE = re.compile(r"\btype\s+(?P<name>[A-Za-z_]\w*)\s+struct\s*\{(?P<body>.*?)^\}", re.DOTALL | re.MULTILINE)
GO_FIELD_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z_]\w*)\s+(?P<type>(?:\[\])?[*]?[A-Za-z_][\w.]*(?:\[[^\]]+\])?)"
    r"(?:\s+`(?P<tags>[^`]*)`)?",
    re.MULTILINE,
)
RUST_STRUCT_HEAD_RE = re.compile(
    r"(?P<attrs>(?:^\s*#\[[^\n]+\]\s*\n)*)"
    r"^\s*(?:pub(?:\([^)]*\))?\s+)?struct\s+(?P<name>[A-Za-z_]\w*)(?:<[^>{}]+>)?\s*"
    r"(?P<kind>[\{\(])",
    re.MULTILINE,
)
RUST_FIELD_RE = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?P<name>[A-Za-z_]\w*)\s*:\s*(?P<type>.+?),?\s*$")
MONGOOSE_SCHEMA_RE = re.compile(
    r"\b(?:const|let|var)\s+(?P<schema>[A-Za-z_$][\w$]*)\s*=\s*new\s+(?:mongoose\.)?Schema\s*\(",
    re.IGNORECASE,
)
MONGOOSE_MODEL_RE = re.compile(
    r"\bmongoose\.model\(\s*['\"`](?P<name>[^'\"`]+)['\"`]\s*,\s*(?P<schema>[A-Za-z_$][\w$]*)",
    re.IGNORECASE,
)
SEQUELIZE_INIT_RE = re.compile(r"\b(?P<class>[A-Za-z_$][\w$]*)\.init\s*\(", re.MULTILINE)
SEQUELIZE_DEFINE_RE = re.compile(
    r"\bsequelize\.define\(\s*['\"`](?P<name>[^'\"`]+)['\"`]\s*,\s*\{",
    re.IGNORECASE | re.MULTILINE,
)
LUCID_MODEL_RE = re.compile(
    r"\b(?:export\s+default\s+)?class\s+(?P<name>[A-Za-z_$][\w$]*)\s+extends\s+BaseModel\s*\{",
    re.MULTILINE,
)
TS_PROPERTY_RE = re.compile(
    r"^\s*(?:public|private|protected)?\s*(?:readonly\s+)?(?P<name>[A-Za-z_$][\w$]*)[?!]?\s*:\s*(?P<type>[^=;]+)",
)
WATERLINE_ATTRIBUTES_RE = re.compile(r"\battributes\s*:\s*\{", re.IGNORECASE)
LOOPBACK_MODEL_RE = re.compile(
    r"@\s*model(?:\s*\([^)]*\))?\s*"
    r"(?:export\s+)?class\s+(?P<name>[A-Za-z_$][\w$]*)\s+extends\s+(?P<base>Entity|Model)\s*\{",
    re.MULTILINE,
)
ASTRO_COLLECTION_RE = re.compile(r"^\s*(?P<name>[A-Za-z_$][\w$]*)\s*:\s*defineCollection\s*\(", re.MULTILINE)
ASTRO_INLINE_Z_OBJECT_RE = re.compile(r"schema\s*:\s*z\.object\s*\(\s*\{(?P<body>[\s\S]{0,1200}?)\}\s*\)", re.MULTILINE)
ASTRO_Z_FIELD_RE = re.compile(r"(?:^|[,{\n])\s*(?P<name>[A-Za-z_$][\w$]*)\s*:", re.MULTILINE)
TS_CLASS_RE = re.compile(
    r"(?:export\s+)?class\s+(?P<name>[A-Za-z_$][\w$]*)"
    r"(?:\s+extends\s+(?P<extends>[^{}]+?))?"
    r"(?:\s+implements\s+(?P<implements>[^{}]+?))?\s*\{",
    re.MULTILINE,
)
PRISMA_MODEL_RE = re.compile(r"^\s*model\s+(?P<name>[A-Za-z_]\w*)\s*\{(?P<body>.*?)^\}", re.MULTILINE | re.DOTALL)
ELIXIR_MODULE_RE = re.compile(r"\bdefmodule\s+(?P<name>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s+do")
ECTO_SCHEMA_RE = re.compile(r"\bschema\s+['\"](?P<table>[^'\"]+)['\"]\s+do")
DART_FREEZED_CLASS_RE = re.compile(
    r"@\s*freezed[\s\S]{0,500}?"
    r"\b(?:sealed\s+|base\s+|final\s+|abstract\s+)?class\s+(?P<name>[A-Za-z_]\w*)"
    r"\s+with\s+_\$(?P=name)(?:\s+implements\s+[^{]+)?\s*\{",
    re.MULTILINE,
)
DART_FACTORY_RE = re.compile(
    r"\bconst\s+factory\s+(?P<name>[A-Za-z_]\w*)"
    r"(?:\.(?P<variant>[A-Za-z_]\w*))?\s*\((?P<body>[\s\S]*?)\)\s*=",
    re.MULTILINE,
)
CS_CLASS_RE = re.compile(
    r"^\s*(?:public|internal)\s+(?:abstract\s+|sealed\s+|partial\s+)?class\s+(?P<name>[A-Za-z_]\w*)"
    r"(?:\s*:\s*(?P<bases>[^{]+))?\s*\{",
    re.MULTILINE,
)
CS_PROPERTY_RE = re.compile(
    r"^\s*public\s+(?P<type>[A-Za-z_][\w<>,.?[\]\s]*)\s+(?P<name>[A-Za-z_]\w*)\s*\{\s*(?:get|init)\b",
    re.MULTILINE,
)
KOTLIN_DATA_CLASS_RE = re.compile(
    r"(?P<attrs>(?:^\s*@[^\n]+\n)*)"
    r"^\s*(?:public\s+|internal\s+|private\s+)?data\s+class\s+(?P<name>[A-Za-z_]\w*)"
    r"(?:\s+[A-Za-z_]\w*)?\s*\(",
    re.MULTILINE,
)
KOTLIN_FIELD_RE = re.compile(
    r"(?:@[A-Za-z_]\w*(?:\([^)]*\))?\s*)*(?:val|var)\s+(?P<name>[A-Za-z_]\w*)\s*:\s*(?P<type>[^=,\n]+)"
)
SCALA_CASE_CLASS_HEAD_RE = re.compile(
    r"^\s*(?:final\s+|sealed\s+|private\s+|protected\s+)*case\s+class\s+(?P<name>[A-Za-z_]\w*)"
    r"(?:\[[^\]]+\])?\s*\(",
    re.MULTILINE,
)
SCALA_FIELD_RE = re.compile(r"^(?:val\s+|var\s+)?(?P<name>[A-Za-z_]\w*)\s*:\s*(?P<type>[^=]+?)(?:\s*=.+)?$")
SWIFT_TYPE_HEAD_RE = re.compile(
    r"(?P<attrs>(?:^\s*@[A-Za-z_]\w*(?:\([^)]*\))?\s*\n)*)"
    r"^\s*(?:public\s+|internal\s+|private\s+|fileprivate\s+)?(?:final\s+)?"
    r"(?P<type_kind>struct|enum|class)\s+(?P<name>[A-Za-z_]\w*)"
    r"(?:<[^>{}]+>)?\s*(?::\s*(?P<bases>[^{\n]+))?\s*\{",
    re.MULTILINE,
)
SWIFT_FIELD_RE = re.compile(
    r"^\s*(?:@[A-Za-z_]\w*(?:\([^)]*\))?\s+)*"
    r"(?:public\s+|internal\s+|private\s+|fileprivate\s+)?"
    r"(?:let|var)\s+(?P<name>[A-Za-z_]\w*)\s*:\s*(?P<type>[^=\n{]+)",
    re.MULTILINE,
)
SWIFT_CASE_RE = re.compile(r"^\s*case\s+(?P<name>[A-Za-z_]\w*)(?:\((?P<args>[^)]*)\))?", re.MULTILINE)
CLOJURE_NS_RE = re.compile(r"\(ns\s+(?:\^[^\s()]+\s+|\^\{[\s\S]{0,300}?\}\s+)*(?P<namespace>[A-Za-z0-9_.-]+)")
CLOJURE_DEFRECORD_RE = re.compile(r"\(defrecord\s+(?P<name>[A-Za-z0-9_.-]+)\s+\[(?P<fields>[^\]]*)\]")
CLOJURE_DB_SPEC_RE = re.compile(r"\(def\s+(?:\^[^\s()]+\s+)?(?P<name>[A-Za-z0-9_.!?*-]+)\s+(?:\"[^\"]*\"\s+)?\{(?P<body>[\s\S]{0,500}?):dbtype\s+['\"](?P<dbtype>[^'\"]+)['\"]")
PY_CLASS_RE = re.compile(
    r"(?m)^class\s+(?P<name>[A-Za-z_]\w*)\s*\((?P<bases>[^)]*)\)\s*:(?P<body>(?:\n[ \t]+[^\n]*)*)",
)
PY_FIELD_RE = re.compile(
    r"(?m)^[ \t]+(?P<name>[A-Za-z_]\w*)\s*:\s*(?P<type>[^=\n#]+?)(?:\s*=\s*(?P<default>[^\n#]+))?\s*(?:#.*)?$",
)
DJANGO_FIELD_RE = re.compile(
    r"(?m)^[ \t]+(?P<name>[A-Za-z_]\w*)\s*=\s*(?P<module>models\.)?"
    r"(?P<field>[A-Za-z_]\w*Field|ForeignKey|OneToOneField|ManyToManyField)\s*\((?P<args>[\s\S]{0,900}?)\)"
)
SQLALCHEMY_ASSIGN_FIELD_RE = re.compile(
    r"(?m)^[ \t]+(?P<name>[A-Za-z_]\w*)\s*=\s*(?:db\.)?"
    r"(?P<call>Column|relationship|reference_col)\s*\((?P<args>[^\n]*)",
)
MARSHMALLOW_FIELD_RE = re.compile(
    r"(?m)^[ \t]+(?P<name>[A-Za-z_]\w*)\s*=\s*fields\.(?P<field>[A-Za-z_]\w*)\s*\((?P<args>[^\n]*)",
)
PHP_CLASS_RE = re.compile(
    r"(?P<doc>/\*\*[\s\S]*?\*/\s*)?"
    r"^\s*(?:abstract\s+)?class\s+(?P<name>[A-Za-z_]\w*)"
    r"(?:\s+extends\s+(?P<extends>[A-Za-z_\\][\w\\]*))?"
    r"(?:\s+implements\s+(?P<implements>[^{]+))?\s*\{",
    re.MULTILINE,
)
PHP_PROPERTY_RE = re.compile(r"@property\s+(?P<type>[^\s$]+(?:\s*\|[^\s$]+)*)\s+\$(?P<name>[A-Za-z_]\w*)")
PHP_ARRAY_PROPERTY_RE = re.compile(
    r"protected\s+\$(?P<name>fillable|casts)\s*=\s*\[(?P<body>[\s\S]*?)\]\s*;",
    re.MULTILINE,
)
PHP_ARRAY_STRING_RE = re.compile(r"['\"](?P<key>[A-Za-z_][\w-]*)['\"](?:\s*=>\s*['\"](?P<value>[^'\"]+)['\"])?")
PHP_TABLE_RE = re.compile(r"protected\s+\$table\s*=\s*['\"](?P<table>[^'\"]+)['\"]")
PHP_RELATION_METHOD_RE = re.compile(
    r"public\s+function\s+(?P<name>[A-Za-z_]\w*)\s*\([^)]*\)\s*(?::\s*(?P<return>[A-Za-z_\\][\w\\]*))?\s*\{(?P<body>[\s\S]{0,1200}?)\n\s*\}",
    re.MULTILINE,
)
PHP_RELATION_CALL_RE = re.compile(
    r"\$this->(?P<relation>belongsToMany|belongsTo|hasMany|hasOne|morphMany|morphOne|morphTo|morphedByMany)\s*\(\s*(?P<target>[A-Za-z_\\][\w\\]*::class)?",
)
PHP_WC_MODEL_BASES = {
    "WC_Data",
    "WC_Product",
    "WC_Product_Simple",
    "WC_Product_Variable",
    "WC_Product_Variation",
    "WC_Product_Grouped",
    "WC_Product_External",
    "WC_Abstract_Order",
    "WC_Order",
    "WC_Order_Refund",
    "WC_Coupon",
    "WC_Customer",
    "WC_Customer_Download",
}
DRUPAL_ENTITY_ATTRIBUTE_RE = re.compile(r"#\[\s*(?P<kind>ContentEntityType|ConfigEntityType)\s*\(")
DRUPAL_BASE_FIELD_RE = re.compile(
    r"\$fields\[\s*['\"](?P<name>[A-Za-z_][\w.-]*)['\"]\s*\]\s*=\s*BaseFieldDefinition::create\(\s*['\"](?P<type>[^'\"]+)['\"]",
    re.MULTILINE,
)
DRUPAL_PROTECTED_PROPERTY_RE = re.compile(
    r"(?P<doc>/\*\*[\s\S]*?\*/\s*)?"
    r"^\s*protected\s+\$(?P<name>[A-Za-z_]\w*)\s*(?:=\s*(?P<default>[^;]+))?;",
    re.MULTILINE,
)
RUBY_CLASS_RE = re.compile(
    r"^\s*class\s+(?P<name>[A-Z][\w:]*)(?:\s*<\s*(?P<base>[A-Z][\w:]*))?",
    re.MULTILINE,
)
RUBY_ASSOC_RE = re.compile(
    r"^\s*(?P<kind>belongs_to|has_one|has_many|has_and_belongs_to_many)\s+:?(?P<name>[A-Za-z_]\w*)(?P<args>[^\n]*)",
    re.MULTILINE,
)
RUBY_VALIDATION_RE = re.compile(
    r"^\s*(?P<kind>validates(?:_[a-z_]+)?|validate)\s+(?P<args>[^\n]*)",
    re.MULTILINE,
)
RUBY_CALLBACK_RE = re.compile(
    r"^\s*(?P<kind>before_validation|before_save|before_create|before_destroy|after_save|after_create|after_destroy|after_commit|after_create_commit|after_update_commit)\s+(?P<args>[^\n]*)",
    re.MULTILINE,
)
RUBY_SCOPE_RE = re.compile(r"^\s*scope\s+:?(?P<name>[A-Za-z_]\w*)", re.MULTILINE)
RUBY_TABLE_RE = re.compile(r"^\s*self\.table_name\s*=\s*['\"](?P<table>[^'\"]+)['\"]", re.MULTILINE)
RUBY_OPTION_SYMBOL_NAMES = {
    "allow_blank",
    "allow_nil",
    "case_sensitive",
    "class_name",
    "dependent",
    "foreign_key",
    "if",
    "in",
    "inverse_of",
    "message",
    "maximum",
    "minimum",
    "numericality",
    "on",
    "only_integer",
    "scope",
    "through",
    "with",
    "without",
}
RUBY_NON_MODEL_BASES = {
    "ActionMailer::Base",
    "ActiveSupport::CurrentAttributes",
    "Array",
    "Hash",
    "Object",
    "StandardError",
    "Struct",
}
RUBY_NON_MODEL_BASE_MARKERS = ("Helper", "Helpers", "Mailer", "Presenter", "Serializer")


def extract_code_model_facts(root: Path, files: list[FileFact]) -> list[DataModelFact]:
    models: list[DataModelFact] = []
    for file_fact in files:
        if file_fact.role in {"test", "sample", "generated"}:
            continue
        normalized = file_fact.path.replace("\\", "/").lower()
        if file_fact.language != "go":
            if normalized.endswith("schema.prisma"):
                source = _read(root / file_fact.path)
                models.extend(_extract_prisma_models(file_fact, source))
            elif file_fact.language == "rust":
                source = _read(root / file_fact.path)
                models.extend(_extract_rust_models(file_fact, source))
            elif file_fact.language in {"javascript", "typescript"}:
                source = _read(root / file_fact.path)
                models.extend(_extract_astro_content_collections(file_fact, source))
                models.extend(_extract_mongoose_models(file_fact, source))
                models.extend(_extract_sequelize_models(file_fact, source))
                models.extend(_extract_lucid_models(file_fact, source))
                models.extend(_extract_waterline_models(file_fact, source))
                models.extend(_extract_loopback_models(file_fact, source))
                models.extend(_extract_nestjs_models(file_fact, source))
            elif file_fact.language == "elixir":
                source = _read(root / file_fact.path)
                models.extend(_extract_ecto_schema_models(file_fact, source))
            elif file_fact.language == "dart":
                source = _read(root / file_fact.path)
                models.extend(_extract_dart_freezed_models(file_fact, source))
            elif file_fact.language == "csharp":
                source = _read(root / file_fact.path)
                models.extend(_extract_csharp_models(file_fact, source))
            elif file_fact.language == "kotlin":
                source = _read(root / file_fact.path)
                models.extend(_extract_kotlin_models(file_fact, source))
            elif file_fact.language == "swift":
                source = _read(root / file_fact.path)
                models.extend(_extract_swift_models(file_fact, source))
            elif file_fact.language == "clojure":
                source = _read(root / file_fact.path)
                models.extend(_extract_clojure_models(file_fact, source))
            elif file_fact.language == "scala":
                source = _read(root / file_fact.path)
                models.extend(_extract_scala_models(file_fact, source))
            elif file_fact.language == "python":
                source = _read(root / file_fact.path)
                models.extend(_extract_python_models(file_fact, source))
            elif file_fact.language == "php":
                source = _read(root / file_fact.path)
                models.extend(_extract_php_doctrine_entities(file_fact, source))
                models.extend(_extract_php_eloquent_models(file_fact, source))
                models.extend(_extract_php_woocommerce_models(file_fact, source))
                models.extend(_extract_php_drupal_models(file_fact, source))
            elif file_fact.language == "ruby":
                source = _read(root / file_fact.path)
                models.extend(_extract_ruby_active_record_models(file_fact, source))
            elif file_fact.language == "json" and file_fact.path.replace("\\", "/").lower().endswith("schema.json"):
                source = _read(root / file_fact.path)
                model = _extract_strapi_schema_model(file_fact, source)
                if model:
                    models.append(model)
            continue
        source = _read(root / file_fact.path)
        models.extend(_extract_go_models(file_fact, source))
    return _dedupe_models(models)


def _extract_astro_content_collections(file_fact: FileFact, source: str) -> list[DataModelFact]:
    normalized = file_fact.path.replace("\\", "/").lower()
    if not normalized.endswith(("content.config.ts", "content.config.js")) or "defineCollection" not in source:
        return []
    matches = list(ASTRO_COLLECTION_RE.finditer(source))
    models: list[DataModelFact] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else min(len(source), match.end() + 1800)
        window = source[start:end]
        line = _line_for_offset(source, start)
        models.append(
            DataModelFact(
                name=match.group("name"),
                path=file_fact.path,
                kind="astro-content-collection",
                fields=_astro_collection_fields(window),
                annotations=_astro_collection_annotations(window),
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    return models


def _astro_collection_fields(source: str) -> list[str]:
    object_match = re.search(r"\bschema\s*:\s*z\.object\s*\(\s*\{", source)
    if not object_match:
        return []
    open_brace = source.find("{", object_match.start())
    close_brace = _find_matching_delimiter(source, open_brace, "{", "}") if open_brace >= 0 else None
    if close_brace is None:
        return []
    body = source[open_brace + 1 : close_brace]
    return _dedupe([match.group("name") for match in ASTRO_Z_FIELD_RE.finditer(body)])


def _astro_collection_annotations(source: str) -> list[str]:
    annotations: list[str] = []
    loader_match = re.search(r"\bloader\s*:\s*(?P<loader>[A-Za-z_$][\w$]*)", source)
    if loader_match:
        annotations.append(f"loader:{loader_match.group('loader')}")
    schema_match = re.search(r"\bschema\s*:\s*(?P<schema>[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)?)", source)
    if schema_match:
        annotations.append(f"schema:{schema_match.group('schema')}")
    extend_match = re.search(r"\bextend\s*:\s*(?P<schema>[A-Za-z_$][\w$]*)", source)
    if extend_match:
        annotations.append(f"extends:{extend_match.group('schema')}")
    return _dedupe(annotations)


def _extract_clojure_models(file_fact: FileFact, source: str) -> list[DataModelFact]:
    models: list[DataModelFact] = []
    namespace = _clojure_namespace(source)
    namespace_tail = namespace.rsplit(".", 1)[-1] if namespace else Path(file_fact.path).stem
    for match in CLOJURE_DEFRECORD_RE.finditer(source):
        fields = _clojure_record_fields(match.group("fields"))
        line = _line_for_offset(source, match.start())
        models.append(
            DataModelFact(
                name=match.group("name"),
                path=file_fact.path,
                kind="clojure-record",
                fields=fields,
                annotations=[f"namespace:{namespace}"] if namespace else [],
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    if _looks_like_clojure_model_namespace(file_fact.path, namespace, source):
        line = _line_for_offset(source, source.find("(ns ")) if "(ns " in source else 1
        models.append(
            DataModelFact(
                name=namespace_tail,
                path=file_fact.path,
                kind="clojure-namespace-model",
                fields=_clojure_keyword_fields(source),
                annotations=[f"namespace:{namespace}"] if namespace else [],
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    for match in CLOJURE_DB_SPEC_RE.finditer(source):
        line = _line_for_offset(source, match.start())
        models.append(
            DataModelFact(
                name=match.group("name"),
                path=file_fact.path,
                kind="clojure-db-spec",
                fields=_clojure_map_keys(match.group("body")),
                annotations=[f"dbtype:{match.group('dbtype')}"],
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    return models


def _clojure_namespace(source: str) -> str | None:
    match = CLOJURE_NS_RE.search(source)
    return match.group("namespace") if match else None


def _looks_like_clojure_model_namespace(path: str, namespace: str | None, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return (
        "/model/" in f"/{normalized}"
        or "/models/" in f"/{normalized}"
        or bool(namespace and re.search(r"(?:^|\.)models?(?:\.|$)", namespace))
    )


def _clojure_record_fields(source: str) -> list[str]:
    cleaned_lines = [line.split(";", 1)[0] for line in source.splitlines()]
    cleaned = " ".join(cleaned_lines)
    return [field for field in re.split(r"\s+", cleaned.strip()) if field]


def _clojure_keyword_fields(source: str) -> list[str]:
    fields = []
    for namespace, name in re.findall(r":(?:(?P<namespace>[A-Za-z0-9_.-]+)/)?(?P<name>[A-Za-z0-9_.!?*-]+)", source):
        if name in {"require", "refer", "as", "gen-class", "doc", "private"}:
            continue
        fields.append(f"{namespace}/{name}" if namespace else name)
    return _dedupe(fields[:80])


def _clojure_map_keys(source: str) -> list[str]:
    return _dedupe([name for name in re.findall(r":([A-Za-z0-9_.!?*-]+)", source)])


def _extract_scala_models(file_fact: FileFact, source: str) -> list[DataModelFact]:
    models: list[DataModelFact] = []
    for match in SCALA_CASE_CLASS_HEAD_RE.finditer(source):
        open_paren = source.find("(", match.start())
        close_paren = _find_matching_delimiter(source, open_paren, "(", ")")
        if close_paren is None:
            continue
        body = source[open_paren + 1 : close_paren]
        fields = _scala_case_class_fields(body)
        line = _line_for_offset(source, match.start())
        models.append(
            DataModelFact(
                name=match.group("name"),
                path=file_fact.path,
                kind="scala-case-class",
                fields=fields,
                annotations=_scala_model_annotations(source, match.group("name")),
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    return models


def _scala_case_class_fields(source: str) -> list[str]:
    fields: list[str] = []
    for raw_field in _split_scala_top_level_commas(source):
        match = SCALA_FIELD_RE.match(raw_field.strip())
        if not match:
            continue
        fields.append(f"{match.group('name')}:{match.group('type').strip()}")
    return _dedupe(fields)


def _split_scala_top_level_commas(source: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depths = {"(": 0, "[": 0, "{": 0}
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
        if char in {"'", '"'}:
            quote = char
            continue
        if char in depths:
            depths[char] += 1
        elif char == ")" and depths["("]:
            depths["("] -= 1
        elif char == "]" and depths["["]:
            depths["["] -= 1
        elif char == "}" and depths["{"]:
            depths["{"] -= 1
        elif char == "," and not any(depths.values()):
            parts.append(source[start:index])
            start = index + 1
    parts.append(source[start:])
    return parts


def _scala_model_annotations(source: str, name: str) -> list[str]:
    annotations: list[str] = []
    if re.search(rf"\bJson\.format\[{re.escape(name)}\]", source):
        annotations.append("json-format")
    if re.search(rf"\bJson\.reads\[{re.escape(name)}\]", source):
        annotations.append("json-reads")
    if re.search(rf"\bJson\.writes\[{re.escape(name)}\]", source):
        annotations.append("json-writes")
    return annotations


def _extract_python_models(file_fact: FileFact, source: str) -> list[DataModelFact]:
    if not _looks_like_python_model_source(file_fact.path, source):
        return []
    models: list[DataModelFact] = []
    known_model_kinds: dict[str, str] = {}
    for match in PY_CLASS_RE.finditer(source):
        name = match.group("name")
        if _is_python_migration_model_noise(file_fact.path, name):
            continue
        bases = match.group("bases")
        body = _python_class_body(source, match)
        kind = _python_model_kind(bases, body, known_model_kinds)
        if not kind:
            continue
        fields, annotations = _python_model_fields(body)
        if not fields and "table=True" not in bases:
            continue
        known_model_kinds[name] = kind
        line = _line_for_offset(source, match.start())
        models.append(
            DataModelFact(
                name=name,
                path=file_fact.path,
                kind=kind,
                fields=_dedupe(fields),
                annotations=_dedupe(annotations),
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    return models


def _is_python_migration_model_noise(path: str, name: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return name == "Migration" and "/migrations/" in f"/{normalized}"


def _python_class_body(source: str, match: re.Match[str]) -> str:
    line_start = source.rfind("\n", 0, match.start()) + 1
    line_end = source.find("\n", line_start)
    class_line = source[line_start : line_end if line_end >= 0 else len(source)]
    class_indent = len(class_line) - len(class_line.lstrip(" \t"))
    body_start = source.find("\n", match.start())
    if body_start < 0:
        return ""
    lines: list[str] = []
    for line in source[body_start + 1 :].splitlines(keepends=True):
        stripped = line.strip()
        if not stripped:
            lines.append(line)
            continue
        indent = len(line) - len(line.lstrip(" \t"))
        if indent <= class_indent:
            break
        lines.append(line)
    return "".join(lines)


def _extract_php_eloquent_models(file_fact: FileFact, source: str) -> list[DataModelFact]:
    if not _looks_like_php_model_source(file_fact.path, source):
        return []
    models: list[DataModelFact] = []
    for match in PHP_CLASS_RE.finditer(source):
        name = match.group("name")
        extends = match.group("extends") or ""
        if _looks_like_php_factory(file_fact.path, name, extends, source):
            continue
        fields, annotations = _php_model_fields_and_annotations(match.group("doc") or "", source)
        if not _looks_like_php_model_class(
            file_fact.path,
            source,
            extends,
            match.group("implements") or "",
            fields,
            annotations,
        ):
            continue
        line = _line_for_offset(source, match.start("name"))
        models.append(
            DataModelFact(
                name=name,
                path=file_fact.path,
                kind="eloquent-model",
                fields=_dedupe(fields),
                annotations=_dedupe(annotations),
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    return models


def _extract_php_doctrine_entities(file_fact: FileFact, source: str) -> list[DataModelFact]:
    if not _looks_like_php_doctrine_entity_source(source):
        return []
    class_match = PHP_CLASS_RE.search(source)
    if not class_match:
        return []
    name = class_match.group("name")
    fields, annotations = _php_doctrine_entity_fields_and_annotations(source)
    line = _line_for_offset(source, class_match.start("name"))
    return [
        DataModelFact(
            name=name,
            path=file_fact.path,
            kind="doctrine-entity",
            fields=_dedupe(fields),
            annotations=_dedupe(annotations),
            evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
        )
    ]


def _looks_like_php_doctrine_entity_source(source: str) -> bool:
    return (
        "@ORM\\Entity" in source
        or "#[ORM\\Entity" in source
        or ("#[Entity" in source and "Doctrine\\ORM\\Mapping" in source)
    )


def _php_doctrine_entity_fields_and_annotations(source: str) -> tuple[list[str], list[str]]:
    fields: list[str] = []
    annotations: list[str] = []
    table = (
        _first_match(source, r"@ORM\\Table\s*\(\s*name\s*=\s*['\"]([^'\"]+)['\"]")
        or _first_match(source, r"#\[ORM\\Table\s*\(\s*name\s*:\s*['\"]([^'\"]+)['\"]")
    )
    if table:
        annotations.append(f"table:{table}")
    repository = (
        _first_match(source, r"repositoryClass\s*:\s*([A-Za-z_\\][\w\\]*)::class")
        or _first_match(source, r"repositoryClass\s*=\s*['\"]([^'\"]+)['\"]")
    )
    if repository:
        repository_name = repository.split("\\")[-1]
        annotations.append(f"repository:{repository_name}")
    for match in re.finditer(
        r"(?m)^\s*(?:private|protected|public)\s+(?P<type>[?\\A-Za-z_][\\\w|?<>]*(?:<[^>]+>)?)\s+\$(?P<name>[A-Za-z_]\w*)",
        source,
    ):
        attrs = _php_attribute_prefix(source, match.start())
        if not re.search(r"ORM\\(?:Id|GeneratedValue|Column|JoinColumn|JoinTable|OneToOne|OneToMany|ManyToOne|ManyToMany)\b", attrs):
            continue
        field_name = match.group("name")
        field_type = " ".join(match.group("type").split())
        if "ORM\\Column" in attrs:
            fields.append(f"{field_name}:{field_type}")
        relation = _first_match(attrs, r"ORM\\(OneToOne|OneToMany|ManyToOne|ManyToMany)\b")
        if relation:
            fields.append(f"{field_name}:{field_type}")
            annotations.append(f"relation:{field_name}:{relation}")
        if "ORM\\Id" in attrs:
            annotations.append(f"primary-key:{field_name}")
        column_type = _first_match(attrs, r"ORM\\Column\s*\(\s*type\s*:\s*([A-Za-z_\\][\w\\:]*)")
        if column_type:
            annotations.append(f"column-type:{field_name}:{column_type.rsplit('::', 1)[-1]}")
        join_table = _first_match(attrs, r"ORM\\JoinTable\s*\(\s*name\s*:\s*['\"]([^'\"]+)['\"]")
        if join_table:
            annotations.append(f"join-table:{field_name}:{join_table}")
    return fields, annotations


def _php_attribute_prefix(source: str, offset: int) -> str:
    boundary = max(source.rfind(";", 0, offset), source.rfind("{", 0, offset), source.rfind("}", 0, offset))
    return source[boundary + 1 : offset] if boundary >= 0 else source[:offset]


def _looks_like_php_factory(path: str, name: str, extends: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    base = extends.rsplit("\\", 1)[-1]
    return (
        "/database/factories/" in f"/{normalized}"
        or "\\database\\factories" in source.lower()
        or base == "Factory"
        or name.endswith("Factory") and "Illuminate\\Database\\Eloquent\\Factories\\Factory" in source
    )


def _looks_like_php_model_source(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    if "/database/factories/" in f"/{normalized}":
        return False
    return (
        "/models/" in f"/{normalized}"
        or "Illuminate\\Database\\Eloquent" in source
        or "extends Model" in source
        or "extends Authenticatable" in source
    )


def _looks_like_php_model_class(
    path: str,
    source: str,
    extends: str,
    implements: str,
    fields: list[str],
    annotations: list[str],
) -> bool:
    normalized = path.replace("\\", "/").lower()
    base = extends.rsplit("\\", 1)[-1]
    if base in {"Model", "Authenticatable"}:
        return True
    if base in {"Builder", "Factory"} or re.search(r"\bScope\b", implements):
        return False
    if "/models/" in f"/{normalized}" and (
        fields
        or annotations
        or "protected $fillable" in source
        or "protected $casts" in source
        or "protected $table" in source
        or re.search(r"\$this->(?:belongsTo|hasMany|hasOne|morph)", source)
    ):
        return True
    return bool(implements and "/models/" in f"/{normalized}" and (fields or annotations))


def _php_model_fields_and_annotations(doc: str, source: str) -> tuple[list[str], list[str]]:
    fields: list[str] = []
    annotations: list[str] = []
    for prop in PHP_PROPERTY_RE.finditer(doc):
        fields.append(f"{prop.group('name')}:{prop.group('type')}")
    table = PHP_TABLE_RE.search(source)
    if table:
        annotations.append(f"table:{table.group('table')}")
    for array_prop in PHP_ARRAY_PROPERTY_RE.finditer(source):
        kind = array_prop.group("name")
        for item in PHP_ARRAY_STRING_RE.finditer(array_prop.group("body")):
            key = item.group("key")
            value = item.group("value")
            if kind == "fillable":
                fields.append(f"{key}:fillable")
                annotations.append(f"fillable:{key}")
            elif kind == "casts":
                fields.append(f"{key}:{value or 'cast'}")
                annotations.append(f"cast:{key}:{value or 'unknown'}")
    for relation in PHP_RELATION_METHOD_RE.finditer(source):
        body = relation.group("body")
        call = PHP_RELATION_CALL_RE.search(body)
        if not call:
            continue
        target = (call.group("target") or "").removesuffix("::class")
        target = target.rsplit("\\", 1)[-1] if target else "unknown"
        name = relation.group("name")
        relation_kind = call.group("relation")
        fields.append(f"{name}:relation")
        annotations.append(f"relation:{name}:{relation_kind}:{target}")
    return fields, annotations


def _extract_php_woocommerce_models(file_fact: FileFact, source: str) -> list[DataModelFact]:
    if not _looks_like_php_woocommerce_source(file_fact.path, source):
        return []
    models: list[DataModelFact] = []
    for match in PHP_CLASS_RE.finditer(source):
        name = match.group("name")
        extends = match.group("extends") or ""
        open_brace = source.find("{", match.end() - 1)
        close_brace = _find_matching_delimiter(source, open_brace, "{", "}")
        body = source[open_brace + 1 : close_brace] if close_brace is not None else source[match.end() :]
        if not _looks_like_php_woocommerce_model_class(name, extends, body):
            continue
        fields, annotations = _php_woocommerce_fields_and_annotations(body)
        if extends:
            base_name = extends.rsplit("\\", 1)[-1]
            annotations.append(f"extends:{base_name}")
        line = _line_for_offset(source, match.start("name"))
        models.append(
            DataModelFact(
                name=name,
                path=file_fact.path,
                kind="woocommerce-data-model",
                fields=_dedupe(fields),
                annotations=_dedupe(annotations),
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    return models


def _looks_like_php_woocommerce_source(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return (
        "/woocommerce/" in f"/{normalized}" and "class WC_" in source
        or "extends WC_Data" in source
        or "protected $data = array" in source
    )


def _looks_like_php_woocommerce_model_class(name: str, extends: str, body: str) -> bool:
    base = extends.rsplit("\\", 1)[-1]
    non_model_markers = ("Data_Store", "Factory", "Query", "Controller", "Exception", "Logger")
    if any(marker in name for marker in non_model_markers) or any(marker in base for marker in non_model_markers):
        return False
    if base in PHP_WC_MODEL_BASES:
        return True
    if name == "WC_Data":
        return True
    return name.startswith("WC_") and re.search(r"protected\s+\$(?:data|extra_data)\s*=\s*array\s*\(", body) is not None


def _php_woocommerce_fields_and_annotations(source: str) -> tuple[list[str], list[str]]:
    fields: list[str] = []
    annotations: list[str] = []
    for array_name in ("data", "extra_data"):
        for key, value_type in _php_array_assignment_items(source, array_name):
            fields.append(f"{key}:{value_type}")
            annotations.append(f"{array_name}:{key}")
    for key, value_type in _php_array_assignment_items(source, "legacy_datastore_props"):
        annotations.append(f"legacy-datastore-prop:{key or value_type}")
    for prop in ("object_type", "post_type", "data_store_name", "cache_group"):
        value = _first_match(source, rf"\b(?:protected|private|public)\s+\${prop}\s*=\s*['\"]([^'\"]+)['\"]")
        if value:
            annotations.append(f"{prop.replace('_', '-')}:{value}")
    return fields, annotations


def _php_array_assignment_items(source: str, property_name: str) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    pattern = re.compile(rf"\b(?:protected|private|public)\s+\${property_name}\s*=\s*array\s*\(")
    for match in pattern.finditer(source):
        open_paren = source.find("(", match.end() - 1)
        close_paren = _find_matching_delimiter(source, open_paren, "(", ")")
        if close_paren is None:
            continue
        body = source[open_paren + 1 : close_paren]
        for item in _split_js_top_level_commas(body):
            keyed = re.match(r"\s*['\"](?P<key>[A-Za-z_][\w-]*)['\"]\s*=>\s*(?P<value>[\s\S]+)$", item)
            if keyed:
                results.append((keyed.group("key"), _php_value_type(keyed.group("value"))))
                continue
            scalar = re.match(r"\s*['\"](?P<value>[A-Za-z_][\w-]*)['\"]\s*$", item)
            if scalar:
                results.append(("", scalar.group("value")))
    return results


def _php_value_type(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("array(") or stripped.startswith("["):
        return "array"
    if re.match(r"^(?:true|false)\b", stripped, re.IGNORECASE):
        return "bool"
    if re.match(r"^-?\d+(?:\.\d+)?\b", stripped):
        return "number"
    if re.match(r"^null\b", stripped, re.IGNORECASE):
        return "null"
    if stripped.startswith(("'", '"')):
        return "string"
    return "mixed"


def _extract_php_drupal_models(file_fact: FileFact, source: str) -> list[DataModelFact]:
    if not _looks_like_php_drupal_entity_source(file_fact.path, source):
        return []
    models: list[DataModelFact] = []
    for attr_match in DRUPAL_ENTITY_ATTRIBUTE_RE.finditer(source):
        open_paren = source.find("(", attr_match.end() - 1)
        close_paren = _find_matching_delimiter(source, open_paren, "(", ")")
        if close_paren is None:
            continue
        args = source[open_paren + 1 : close_paren]
        class_match = PHP_CLASS_RE.search(source, close_paren)
        if not class_match:
            continue
        name = class_match.group("name")
        extends = class_match.group("extends") or ""
        fields, annotations = _php_drupal_entity_fields_and_annotations(source, args, attr_match.group("kind"))
        if extends:
            annotations.append(f"extends:{_php_short_class_name(extends)}")
        line = _line_for_offset(source, attr_match.start())
        models.append(
            DataModelFact(
                name=name,
                path=file_fact.path,
                kind="drupal-content-entity" if attr_match.group("kind") == "ContentEntityType" else "drupal-config-entity",
                fields=_dedupe(fields),
                annotations=_dedupe(annotations),
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    return models


def _looks_like_php_drupal_entity_source(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    if "/tests/" in f"/{normalized}":
        return False
    return (
        "#[ContentEntityType(" in source
        or "#[ConfigEntityType(" in source
        or "@ContentEntityType(" in source
        or "@ConfigEntityType(" in source
    )


def _php_drupal_entity_fields_and_annotations(source: str, args: str, attribute_kind: str) -> tuple[list[str], list[str]]:
    fields: list[str] = []
    annotations: list[str] = [f"entity-kind:{attribute_kind}"]

    entity_id = _first_match(args, r"\bid\s*:\s*['\"]([^'\"]+)['\"]")
    if entity_id:
        annotations.append(f"entity-id:{entity_id}")

    for key in ("base_table", "data_table", "revision_table", "revision_data_table"):
        value = _first_match(args, rf"\b{key}\s*:\s*['\"]([^'\"]+)['\"]")
        if value:
            annotations.append(f"{key.replace('_', '-')}:{value}")

    admin_permission = _first_match(args, r"\badmin_permission\s*:\s*['\"]([^'\"]+)['\"]")
    if admin_permission:
        annotations.append(f"admin-permission:{admin_permission}")

    for section_name, detail_prefix in (("entity_keys", "entity-key"), ("handlers", "handler"), ("links", "link")):
        section = _php_named_array_section(args, section_name)
        if section:
            annotations.extend(_php_string_map_details(section, detail_prefix))

    config_export = _php_named_array_section(args, "config_export")
    if config_export:
        for item in _php_array_string_items(config_export):
            fields.append(f"{item}:config")
            annotations.append(f"config-export:{item}")

    fields.extend(_php_drupal_base_fields(source))
    if attribute_kind == "ConfigEntityType":
        fields.extend(_php_drupal_declared_properties(source))
    return fields, annotations


def _php_drupal_base_fields(source: str) -> list[str]:
    fields: list[str] = []
    for match in DRUPAL_BASE_FIELD_RE.finditer(source):
        fields.append(f"{match.group('name')}:{match.group('type')}")
    return fields


def _php_drupal_declared_properties(source: str) -> list[str]:
    fields: list[str] = []
    for match in DRUPAL_PROTECTED_PROPERTY_RE.finditer(source):
        name = match.group("name")
        var_type = _first_match(match.group("doc") or "", r"@var\s+([^\s]+)") or _php_value_type(match.group("default") or "")
        if name in {"pluginCollection", "typedConfigManager"}:
            continue
        fields.append(f"{name}:{var_type}")
    return fields


def _php_named_array_section(source: str, name: str) -> str | None:
    match = re.search(rf"\b{re.escape(name)}\s*:\s*\[", source)
    if not match:
        return None
    open_bracket = source.find("[", match.end() - 1)
    close_bracket = _find_matching_delimiter(source, open_bracket, "[", "]")
    return source[open_bracket + 1 : close_bracket] if close_bracket is not None else None


def _php_string_map_details(source: str, prefix: str) -> list[str]:
    details: list[str] = []
    for key, raw_value in re.findall(r"['\"]([^'\"]+)['\"]\s*=>\s*([^,\n\]]+)", source):
        value = raw_value.strip()
        class_match = re.search(r"([A-Za-z_\\][\w\\]*)::class", value)
        literal_match = re.search(r"['\"]([^'\"]+)['\"]", value)
        if class_match:
            details.append(f"{prefix}:{key}:{_php_short_class_name(class_match.group(1))}")
        elif literal_match:
            details.append(f"{prefix}:{key}:{literal_match.group(1)}")
        elif value.startswith("["):
            details.append(f"{prefix}:{key}:nested")
    return details


def _php_array_string_items(source: str) -> list[str]:
    return _dedupe(re.findall(r"['\"]([^'\"]+)['\"]", source))


def _php_short_class_name(value: str) -> str:
    return value.rsplit("\\", 1)[-1]


def _extract_ruby_active_record_models(file_fact: FileFact, source: str) -> list[DataModelFact]:
    if not _looks_like_ruby_model_source(file_fact.path, source):
        return []
    models: list[DataModelFact] = []
    for match in RUBY_CLASS_RE.finditer(source):
        name = match.group("name").split("::")[-1]
        base = match.group("base") or ""
        body = source[match.end() : _next_ruby_class_offset(source, match.end())]
        fields, annotations = _ruby_model_fields_and_annotations(body)
        if not _looks_like_ruby_model_class(file_fact.path, name, base, fields, annotations):
            continue
        line = _line_for_offset(source, match.start("name"))
        models.append(
            DataModelFact(
                name=name,
                path=file_fact.path,
                kind="active-record-model",
                fields=_dedupe(fields),
                annotations=_dedupe([*annotations, *(_ruby_base_annotations(base))]),
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    return models


def _looks_like_ruby_model_source(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    if any(marker in f"/{normalized}" for marker in ("/db/migrate/", "/lib/tasks/", "/extra/sample")):
        return False
    return (
        "/app/models/" in f"/{normalized}"
        or "ApplicationRecord" in source
        or "ActiveRecord::Base" in source
        or "ActiveRecord::Migration" in source
    )


def _looks_like_ruby_model_class(
    path: str,
    name: str,
    base: str,
    fields: list[str],
    annotations: list[str],
) -> bool:
    normalized = path.replace("\\", "/").lower()
    if base in RUBY_NON_MODEL_BASES:
        return False
    if any(marker in base for marker in RUBY_NON_MODEL_BASE_MARKERS):
        return False
    if base in {"ApplicationRecord", "ActiveRecord::Base"} or base.endswith("::Base"):
        return True
    if "/app/models/" not in f"/{normalized}":
        return bool(fields or annotations)
    if _ruby_class_matches_file(path, name):
        return bool(base or fields or annotations)
    return False


def _ruby_class_matches_file(path: str, name: str) -> bool:
    basename = Path(path.replace("\\", "/")).stem
    return basename == _snake_case(name.split("::")[-1])


def _snake_case(name: str) -> str:
    value = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return value.replace("-", "_").lower()


def _ruby_model_fields_and_annotations(source: str) -> tuple[list[str], list[str]]:
    fields: list[str] = []
    annotations: list[str] = []
    table = RUBY_TABLE_RE.search(source)
    if table:
        annotations.append(f"table:{table.group('table')}")
    for association in RUBY_ASSOC_RE.finditer(source):
        name = association.group("name")
        kind = association.group("kind")
        target = _ruby_class_name_option(association.group("args")) or _classify_rails_relation_target(name)
        fields.append(f"{name}:relation")
        annotations.append(f"relation:{name}:{kind}:{target}")
    for validation in RUBY_VALIDATION_RE.finditer(source):
        kind = validation.group("kind")
        for name in _ruby_symbol_names(validation.group("args"))[:12]:
            annotations.append(f"validation:{kind}:{name}")
    for callback in RUBY_CALLBACK_RE.finditer(source):
        kind = callback.group("kind")
        for name in _ruby_symbol_names(callback.group("args"))[:12]:
            annotations.append(f"callback:{kind}:{name}")
    for scope in RUBY_SCOPE_RE.finditer(source):
        name = scope.group("name")
        if name not in {"end", "else"}:
            annotations.append(f"scope:{name}")
    for macro in re.findall(r"^\s*(acts_as_[A-Za-z_]\w*)", source, re.MULTILINE):
        annotations.append(f"macro:{macro}")
    return fields, annotations


def _ruby_class_name_option(args: str) -> str | None:
    match = re.search(r"(?:class_name:|:class_name\s*=>)\s*['\"](?P<name>[A-Z][\w:]+)['\"]", args)
    return match.group("name").split("::")[-1] if match else None


def _classify_rails_relation_target(name: str) -> str:
    if name.endswith("ies"):
        singular = f"{name[:-3]}y"
    elif name.endswith("sses"):
        singular = name[:-2]
    elif name.endswith("ses"):
        singular = name[:-2]
    else:
        singular = name[:-1] if name.endswith("s") and not name.endswith("ss") else name
    return "".join(part.capitalize() for part in singular.split("_")) or "unknown"


def _ruby_symbol_names(args: str) -> list[str]:
    names = []
    for match in re.finditer(r":([A-Za-z_]\w*)", args):
        name = match.group(1)
        if name in RUBY_OPTION_SYMBOL_NAMES:
            continue
        if re.match(r"\s*=>", args[match.end() : match.end() + 4]):
            continue
        names.append(name)
    names.extend(re.findall(r"['\"]([A-Za-z_]\w*)['\"]", args))
    return _dedupe(names)


def _ruby_base_annotations(base: str) -> list[str]:
    return [f"bases:{base}"] if base else []


def _next_ruby_class_offset(source: str, offset: int) -> int:
    match = RUBY_CLASS_RE.search(source, offset)
    return match.start() if match else len(source)


def _looks_like_python_model_source(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    if "sqlmodel" in source or "pydantic" in source or "BaseModel" in source:
        return True
    if "marshmallow" in source or ("Schema" in source and "fields." in source):
        return True
    if "Column(" in source or "mapped_column(" in source or "relationship(" in source:
        return True
    if "models.Model" in source or "django.db" in source and "models." in source:
        return True
    return "/models" in f"/{normalized}" or normalized.endswith(("models.py", "schemas.py", "schema.py"))


def _python_model_kind(
    bases: str,
    body: str,
    known_model_kinds: dict[str, str],
) -> str | None:
    base_names = {name for name in re.findall(r"\b[A-Za-z_]\w*\b", bases) if name not in {"table", "True", "False"}}
    inherited_kinds = {known_model_kinds[name] for name in base_names if name in known_model_kinds}
    if "SQLModel" in base_names or any(kind.startswith("sqlmodel") for kind in inherited_kinds) or "table=True" in bases:
        return "sqlmodel-table" if "table=True" in bases else "sqlmodel-model"
    if "BaseModel" in base_names or "RootModel" in base_names or "pydantic-model" in inherited_kinds:
        return "pydantic-model"
    if {"Base", "DeclarativeBase"} & base_names and ("Column(" in body or "mapped_column(" in body):
        return "sqlalchemy-model"
    if "Model" in base_names and ("Column(" in body or "relationship(" in body or "__tablename__" in body):
        return "sqlalchemy-model"
    if "Schema" in base_names and "fields." in body:
        return "marshmallow-schema"
    if (
        "models.Model" in bases
        or "django-model" in inherited_kinds
        or ("Model" in base_names and "models." in body)
        or ("models." in body and DJANGO_FIELD_RE.search(body))
    ):
        return "django-model"
    return None


def _python_model_fields(body: str) -> tuple[list[str], list[str]]:
    fields: list[str] = []
    annotations: list[str] = []
    for match in PY_FIELD_RE.finditer(body):
        name = match.group("name")
        if name in {"if", "elif", "else", "for", "while", "try", "except", "finally", "with", "def", "class", "return"}:
            continue
        type_name = " ".join(match.group("type").strip().split())
        default = (match.group("default") or "").strip()
        fields.append(f"{name}:{type_name}")
        if "Field(" in default:
            annotations.append(f"field:{name}")
            if "primary_key=True" in default:
                annotations.append(f"primary-key:{name}")
            foreign_key = re.search(r"foreign_key\s*=\s*['\"]([^'\"]+)['\"]", default)
            if foreign_key:
                annotations.append(f"foreign-key:{name}:{foreign_key.group(1)}")
        if "Relationship(" in default:
            annotations.append(f"relationship:{name}")
            back_populates = re.search(r"back_populates\s*=\s*['\"]([^'\"]+)['\"]", default)
            if back_populates:
                annotations.append(f"relationship:{name}:back_populates:{back_populates.group(1)}")
        if "Column(" in default or "mapped_column(" in default:
            annotations.append(f"column:{name}")
            if "primary_key=True" in default:
                annotations.append(f"primary-key:{name}")
    for match in DJANGO_FIELD_RE.finditer(body):
        name = match.group("name")
        field_type = match.group("field")
        args = match.group("args")
        fields.append(f"{name}:{field_type}")
        annotations.append(f"django-field:{name}:{field_type}")
        if field_type in {"ForeignKey", "OneToOneField", "ManyToManyField"}:
            target = _first_python_string(args) or _first_python_identifier(args) or "unknown"
            annotations.append(f"relationship:{name}:{field_type}:{target}")
        for flag in ("null", "blank", "unique", "primary_key"):
            if re.search(rf"\b{flag}\s*=\s*True\b", args):
                annotations.append(f"{flag.replace('_', '-')}:{name}")
    for match in SQLALCHEMY_ASSIGN_FIELD_RE.finditer(body):
        name = match.group("name")
        call = match.group("call")
        args = match.group("args")
        fields.append(f"{name}:{_sqlalchemy_field_type(call, args)}")
        if call == "relationship":
            annotations.append(f"relationship:{name}")
        if "primary_key=True" in args:
            annotations.append(f"primary-key:{name}")
        if "unique=True" in args:
            annotations.append(f"unique:{name}")
        if "nullable=False" in args:
            annotations.append(f"required:{name}")
    for match in MARSHMALLOW_FIELD_RE.finditer(body):
        name = match.group("name")
        field_type = match.group("field")
        args = match.group("args")
        fields.append(f"{name}:fields.{field_type}")
        if "dump_only=True" in args:
            annotations.append(f"dump-only:{name}")
        if "load_only=True" in args:
            annotations.append(f"load-only:{name}")
    return fields, annotations


def _sqlalchemy_field_type(call: str, args: str) -> str:
    if call == "relationship":
        return f"relationship:{_first_python_string(args) or _first_python_identifier(args) or 'unknown'}"
    if call == "reference_col":
        return f"reference:{_first_python_string(args) or _first_python_identifier(args) or 'unknown'}"
    type_match = re.search(r"\b(?:db\.)?(?P<type>[A-Za-z_]\w*)\s*(?:\(|,|$)", args.strip())
    return type_match.group("type") if type_match else "Column"


def _first_python_string(source: str) -> str | None:
    match = re.search(r"['\"]([^'\"]+)['\"]", source)
    return match.group(1) if match else None


def _first_python_identifier(source: str) -> str | None:
    match = re.search(r"\b([A-Z][A-Za-z_]\w*)\b", source)
    return match.group(1) if match else None


def _extract_go_models(file_fact: FileFact, source: str) -> list[DataModelFact]:
    models: list[DataModelFact] = []
    for match in GO_STRUCT_RE.finditer(source):
        body = match.group("body")
        if not _looks_like_go_data_model(file_fact.path, body):
            continue
        fields: list[str] = []
        annotations: list[str] = []
        if re.search(r"(?m)^\s*gorm\.Model\s*$", body):
            fields.append("embed:gorm.Model")
        for field in GO_FIELD_RE.finditer(body):
            name = field.group("name")
            type_name = field.group("type")
            tags = field.group("tags") or ""
            fields.append(f"{name}:{type_name}")
            annotations.extend(_go_field_annotations(name, tags))
        line = _line_for_offset(source, match.start())
        models.append(
            DataModelFact(
                name=match.group("name"),
                path=file_fact.path,
                kind="gorm-struct" if _looks_like_gorm_struct(body) else "go-struct",
                fields=_dedupe(fields),
                annotations=_dedupe(annotations),
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    return models


def _looks_like_go_data_model(path: str, body: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return _looks_like_gorm_struct(body) or "/model/" in f"/{normalized}" and any(tag in body for tag in ('`json:', '`db:', '`sql:'))


def _looks_like_gorm_struct(body: str) -> bool:
    return "gorm.Model" in body or 'gorm:"' in body or 'sql:"' in body


def _go_field_annotations(name: str, tags: str) -> list[str]:
    annotations: list[str] = []
    gorm = _struct_tag_value(tags, "gorm")
    sql = _struct_tag_value(tags, "sql")
    json_tag = _struct_tag_value(tags, "json")
    if gorm:
        annotations.append(f"{name}:gorm:{gorm}")
        if "many2many:" in gorm:
            relation = gorm.split("many2many:", 1)[1].split(";", 1)[0]
            annotations.append(f"relation:{name}:many2many:{relation}")
        if "foreignKey:" in gorm:
            relation = gorm.split("foreignKey:", 1)[1].split(";", 1)[0]
            annotations.append(f"relation:{name}:foreignKey:{relation}")
        if "primaryKey" in gorm:
            annotations.append(f"primary-key:{name}")
    if sql:
        annotations.append(f"{name}:sql:{sql}")
    if json_tag:
        annotations.append(f"{name}:json:{json_tag.split(',', 1)[0]}")
    return annotations


def _struct_tag_value(tags: str, key: str) -> str | None:
    match = re.search(rf"\b{re.escape(key)}:\"([^\"]+)\"", tags)
    return match.group(1) if match else None


def _extract_rust_models(file_fact: FileFact, source: str) -> list[DataModelFact]:
    models: list[DataModelFact] = []
    for match in RUST_STRUCT_HEAD_RE.finditer(source):
        attrs = match.group("attrs") or ""
        name = match.group("name")
        if not _looks_like_rust_data_model(name, attrs):
            continue
        body = ""
        tuple_source = ""
        if match.group("kind") == "{":
            open_index = match.end("kind") - 1
            close_index = _find_matching_delimiter(source, open_index, "{", "}")
            if close_index is None:
                continue
            body = source[open_index + 1 : close_index]
        else:
            open_index = match.end("kind") - 1
            close_index = _find_matching_delimiter(source, open_index, "(", ")")
            if close_index is None:
                continue
            semicolon = source.find(";", close_index)
            if semicolon < 0 or semicolon > close_index + 4:
                continue
            tuple_source = source[open_index + 1 : close_index]
        fields = _rust_struct_fields(body, tuple_source)
        annotations = _rust_struct_annotations(attrs)
        line = _line_for_offset(source, match.start("name"))
        models.append(
            DataModelFact(
                name=name,
                path=file_fact.path,
                kind=_rust_model_kind(attrs, name),
                fields=fields,
                annotations=annotations,
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    return models


def _looks_like_rust_data_model(name: str, attrs: str) -> bool:
    return (
        "serde::Serialize" in attrs
        or "serde::Deserialize" in attrs
        or "Serialize" in attrs
        or "Deserialize" in attrs
        or "sqlx::Type" in attrs
        or name.endswith("FromQuery")
    )


def _rust_model_kind(attrs: str, name: str) -> str:
    if "sqlx::Type" in attrs:
        return "rust-sqlx-type"
    if name.endswith("FromQuery"):
        return "rust-query-shape"
    return "rust-serde-struct"


def _rust_struct_fields(body: str, tuple_source: str) -> list[str]:
    fields: list[str] = []
    if tuple_source:
        inner = tuple_source.strip()
        for index, type_name in enumerate(_split_rust_top_level_commas(inner)):
            fields.append(f"{index}:{type_name.removeprefix('pub ').strip()}")
        return fields
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "//")) or ":" not in stripped:
            continue
        field = RUST_FIELD_RE.match(stripped)
        if not field:
            continue
        type_name = field.group("type").rstrip(",").strip()
        fields.append(f"{field.group('name')}:{' '.join(type_name.split())}")
    return _dedupe(fields)


def _rust_struct_annotations(attrs: str) -> list[str]:
    annotations: list[str] = []
    for derive in re.findall(r"#\[derive\(([^)]*)\)\]", attrs):
        annotations.extend(f"derive:{item.strip()}" for item in derive.split(",") if item.strip())
    annotations.extend(f"serde:{item.strip()}" for item in re.findall(r"#\[serde\(([^)]*)\)\]", attrs))
    annotations.extend("sqlx:Type" for _ in re.findall(r"#\[derive\([^)]*sqlx::Type[^)]*\)\]", attrs))
    return _dedupe(annotations)


def _extract_mongoose_models(file_fact: FileFact, source: str) -> list[DataModelFact]:
    if "mongoose" not in source or ".Schema" not in source:
        return []
    model_names = _mongoose_model_names(source)
    models: list[DataModelFact] = []
    for match in MONGOOSE_SCHEMA_RE.finditer(source):
        schema_name = match.group("schema")
        open_paren = source.find("(", match.end() - 1)
        close_paren = _find_matching_delimiter(source, open_paren, "(", ")")
        if close_paren is None:
            continue
        args = source[open_paren + 1 : close_paren]
        open_brace = args.find("{")
        if open_brace < 0:
            continue
        close_brace = _find_matching_delimiter(args, open_brace, "{", "}")
        if close_brace is None:
            continue
        body = args[open_brace + 1 : close_brace]
        options = args[close_brace + 1 :]
        fields, annotations = _mongoose_schema_fields(body)
        if "timestamps" in options:
            annotations.append("timestamps:true")
        annotations.extend(f"method:{name}" for name in re.findall(rf"\b{re.escape(schema_name)}\.methods\.([A-Za-z_$][\w$]*)\s*=", source))
        line = _line_for_offset(source, match.start("schema"))
        models.append(
            DataModelFact(
                name=model_names.get(schema_name) or schema_name.removesuffix("Schema"),
                path=file_fact.path,
                kind="mongoose-model",
                fields=_dedupe(fields),
                annotations=_dedupe(annotations),
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    return models


def _mongoose_model_names(source: str) -> dict[str, str]:
    names: dict[str, str] = {}
    for match in MONGOOSE_MODEL_RE.finditer(source):
        names[match.group("schema")] = match.group("name")
    return names


def _mongoose_schema_fields(body: str) -> tuple[list[str], list[str]]:
    fields: list[str] = []
    annotations: list[str] = []
    for item in _split_js_top_level_commas(body):
        if ":" not in item:
            continue
        name, value = item.split(":", 1)
        field_name = _clean_js_property_name(name)
        if not field_name:
            continue
        value = value.strip()
        field_type = _mongoose_field_type(value)
        fields.append(f"{field_name}:{field_type}")
        annotations.extend(_mongoose_field_annotations(field_name, value))
    return fields, annotations


def _clean_js_property_name(value: str) -> str | None:
    stripped = value.strip().strip("'\"`")
    return stripped if re.fullmatch(r"[A-Za-z_$][\w$]*", stripped) else None


def _mongoose_field_type(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("["):
        inner = stripped[1 : stripped.rfind("]") if "]" in stripped else len(stripped)].strip()
        return f"Array<{_mongoose_field_type(inner)}>" if inner else "Array"
    type_match = re.search(r"\btype\s*:\s*(?P<type>(?:mongoose\.)?Schema\.Types\.[A-Za-z_$][\w$]*|[A-Za-z_$][\w$]*)", stripped)
    if type_match:
        return _mongoose_normalized_type(type_match.group("type"))
    direct_match = re.match(r"(?P<type>(?:mongoose\.)?Schema\.Types\.[A-Za-z_$][\w$]*|[A-Za-z_$][\w$]*)\b", stripped)
    if direct_match:
        return _mongoose_normalized_type(direct_match.group("type"))
    return "unknown"


def _mongoose_normalized_type(value: str) -> str:
    return value.removeprefix("mongoose.Schema.Types.").removeprefix("Schema.Types.")


def _mongoose_field_annotations(field_name: str, value: str) -> list[str]:
    annotations: list[str] = []
    for key in ("required", "unique", "index", "lowercase"):
        if re.search(rf"\b{key}\s*:\s*true\b", value, re.IGNORECASE) or (
            key == "required" and re.search(r"\brequired\s*:\s*\[", value)
        ):
            annotations.append(f"{key}:{field_name}")
    if re.search(r"\bdefault\s*:", value):
        annotations.append(f"default:{field_name}")
    ref_match = re.search(r"\bref\s*:\s*['\"`]([^'\"`]+)['\"`]", value)
    if ref_match:
        annotations.append(f"ref:{field_name}:{ref_match.group(1)}")
    return annotations


def _extract_sequelize_models(file_fact: FileFact, source: str) -> list[DataModelFact]:
    if "sequelize" not in source.lower() and "DataTypes" not in source:
        return []
    models: list[DataModelFact] = []
    for match in SEQUELIZE_INIT_RE.finditer(source):
        open_paren = source.find("(", match.end() - 1)
        fields_open = source.find("{", open_paren)
        fields_close = _find_matching_delimiter(source, fields_open, "{", "}") if fields_open >= 0 else None
        if fields_close is None:
            continue
        options_open = source.find("{", fields_close)
        options_close = _find_matching_delimiter(source, options_open, "{", "}") if options_open >= 0 else None
        options = source[options_open + 1 : options_close] if options_close is not None else ""
        class_name = match.group("class")
        name = _first_match(options, r"\bmodelName\s*:\s*['\"`]([^'\"`]+)['\"`]") or class_name
        line = _line_for_offset(source, match.start())
        models.append(
            DataModelFact(
                name=name,
                path=file_fact.path,
                kind="sequelize-model",
                fields=_sequelize_fields(source[fields_open + 1 : fields_close]),
                annotations=_sequelize_associations(source, class_name),
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    for match in SEQUELIZE_DEFINE_RE.finditer(source):
        fields_open = source.find("{", match.end() - 1)
        fields_close = _find_matching_delimiter(source, fields_open, "{", "}") if fields_open >= 0 else None
        if fields_close is None:
            continue
        line = _line_for_offset(source, match.start())
        models.append(
            DataModelFact(
                name=match.group("name"),
                path=file_fact.path,
                kind="sequelize-model",
                fields=_sequelize_fields(source[fields_open + 1 : fields_close]),
                annotations=[],
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    return models


def _sequelize_fields(source: str) -> list[str]:
    fields: list[str] = []
    for item in _split_js_top_level_commas(source):
        if ":" not in item:
            continue
        name, value = item.split(":", 1)
        field_name = _clean_js_property_name(name)
        if not field_name:
            continue
        fields.append(f"{field_name}:{_sequelize_field_type(value)}")
    return _dedupe(fields)


def _sequelize_field_type(value: str) -> str:
    type_match = re.search(r"\b(?:DataTypes|Sequelize)\.(?P<type>[A-Za-z_$][\w$]*)", value)
    if type_match:
        return type_match.group("type")
    direct_match = re.match(r"(?P<type>[A-Za-z_$][\w$]*)\b", value.strip())
    return direct_match.group("type") if direct_match else "unknown"


def _sequelize_associations(source: str, class_name: str) -> list[str]:
    class_match = re.search(rf"\bclass\s+{re.escape(class_name)}\s+extends\s+Model\s*\{{", source)
    if not class_match:
        return []
    open_brace = source.find("{", class_match.start())
    close_brace = _find_matching_delimiter(source, open_brace, "{", "}") if open_brace >= 0 else None
    body = source[class_match.end() : close_brace] if close_brace is not None else source[class_match.end() : class_match.end() + 1800]
    annotations: list[str] = []
    for relation, target in re.findall(r"\bthis\.(belongsTo|hasOne|hasMany|belongsToMany)\(\s*([A-Za-z_$][\w$]*)", body):
        annotations.append(f"relation:{relation}:{target}")
    for foreign_key in re.findall(r"\bforeignKey\s*:\s*['\"`]([^'\"`]+)['\"`]", body):
        annotations.append(f"foreign-key:{foreign_key}")
    for through in re.findall(r"\bthrough\s*:\s*['\"`]([^'\"`]+)['\"`]", body):
        annotations.append(f"through:{through}")
    return _dedupe(annotations)


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
    part = source[start:].strip()
    if part:
        parts.append(part)
    return parts


def _extract_lucid_models(file_fact: FileFact, source: str) -> list[DataModelFact]:
    if "BaseModel" not in source or ("@ioc:Adonis/Lucid/Orm" not in source and "@column" not in source):
        return []
    models: list[DataModelFact] = []
    for match in LUCID_MODEL_RE.finditer(source):
        open_brace = source.find("{", match.end() - 1)
        close_brace = _find_matching_delimiter(source, open_brace, "{", "}")
        if close_brace is None:
            continue
        body = source[open_brace + 1 : close_brace]
        fields, annotations = _lucid_model_fields(body)
        line = _line_for_offset(source, match.start("name"))
        models.append(
            DataModelFact(
                name=match.group("name"),
                path=file_fact.path,
                kind="adonis-lucid-model",
                fields=_dedupe(fields),
                annotations=_dedupe(annotations),
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    return models


def _lucid_model_fields(body: str) -> tuple[list[str], list[str]]:
    fields: list[str] = []
    annotations: list[str] = []
    decorators: list[str] = []
    lines = body.splitlines()
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
        property_match = TS_PROPERTY_RE.match(lines[index])
        if property_match and decorators:
            field_name = property_match.group("name")
            field_type = " ".join(property_match.group("type").strip().split())
            fields.append(f"{field_name}:{field_type}")
            annotations.extend(_lucid_property_annotations(field_name, field_type, decorators))
            decorators = []
        elif stripped and not stripped.startswith("//"):
            decorators = []
        index += 1
    return fields, annotations


def _lucid_property_annotations(field_name: str, field_type: str, decorators: list[str]) -> list[str]:
    annotations: list[str] = []
    joined = " ".join(decorators)
    if "@column" in joined:
        annotations.append(f"column:{field_name}")
    if "isPrimary" in joined:
        annotations.append(f"primary-key:{field_name}")
    if "autoCreate" in joined:
        annotations.append(f"auto-create:{field_name}")
    if "autoUpdate" in joined:
        annotations.append(f"auto-update:{field_name}")
    if "serializeAs" in joined:
        annotations.append(f"serialize:{field_name}")
    if "@slugify" in joined:
        annotations.append(f"slugify:{field_name}")
    relation_map = {
        "@belongsTo": "belongsTo",
        "@hasOne": "hasOne",
        "@hasMany": "hasMany",
        "@manyToMany": "manyToMany",
    }
    for decorator, relation in relation_map.items():
        if decorator not in joined:
            continue
        target_match = re.search(r"\(\s*\(\)\s*=>\s*([A-Za-z_$][\w$]*)", joined)
        target = target_match.group(1) if target_match else _lucid_relation_target(field_type)
        annotations.append(f"relation:{relation}:{field_name}:{target or 'unknown'}")
    return annotations


def _lucid_relation_target(field_type: str) -> str | None:
    match = re.search(r"typeof\s+([A-Za-z_$][\w$]*)", field_type)
    return match.group(1) if match else None


def _extract_waterline_models(file_fact: FileFact, source: str) -> list[DataModelFact]:
    normalized = file_fact.path.replace("\\", "/").lower()
    if "/api/models/" not in f"/{normalized}" or "attributes" not in source:
        return []
    match = WATERLINE_ATTRIBUTES_RE.search(source)
    if not match:
        return []
    open_brace = source.find("{", match.start())
    close_brace = _find_matching_delimiter(source, open_brace, "{", "}")
    if close_brace is None:
        return []
    body = source[open_brace + 1 : close_brace]
    fields, annotations = _waterline_fields(body)
    model_name = Path(file_fact.path).stem
    line = _line_for_offset(source, match.start())
    return [
        DataModelFact(
            name=model_name,
            path=file_fact.path,
            kind="sails-waterline-model",
            fields=_dedupe(fields),
            annotations=_dedupe(annotations),
            evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
        )
    ]


def _waterline_fields(body: str) -> tuple[list[str], list[str]]:
    fields: list[str] = []
    annotations: list[str] = []
    for item in _split_js_top_level_commas(body):
        if ":" not in item:
            continue
        name, config = item.split(":", 1)
        field_name = _clean_js_property_name(name)
        if not field_name:
            continue
        field_type = _waterline_field_type(config)
        fields.append(f"{field_name}:{field_type}")
        annotations.extend(_waterline_annotations(field_name, config))
    return fields, annotations


def _waterline_field_type(config: str) -> str:
    type_match = re.search(r"\btype\s*:\s*['\"`]([^'\"`]+)['\"`]", config)
    if type_match:
        return type_match.group(1)
    collection_match = re.search(r"\bcollection\s*:\s*['\"`]([^'\"`]+)['\"`]", config)
    if collection_match:
        return f"collection<{collection_match.group(1)}>"
    model_match = re.search(r"\bmodel\s*:\s*['\"`]([^'\"`]+)['\"`]", config)
    if model_match:
        return f"model<{model_match.group(1)}>"
    return "unknown"


def _waterline_annotations(field_name: str, config: str) -> list[str]:
    annotations: list[str] = []
    for key in ("required", "unique"):
        if re.search(rf"\b{key}\s*:\s*true\b", config):
            annotations.append(f"{key}:{field_name}")
    collection_match = re.search(r"\bcollection\s*:\s*['\"`]([^'\"`]+)['\"`]", config)
    if collection_match:
        annotations.append(f"collection:{field_name}:{collection_match.group(1)}")
    model_match = re.search(r"\bmodel\s*:\s*['\"`]([^'\"`]+)['\"`]", config)
    if model_match:
        annotations.append(f"model:{field_name}:{model_match.group(1)}")
    via_match = re.search(r"\bvia\s*:\s*['\"`]([^'\"`]+)['\"`]", config)
    if via_match:
        annotations.append(f"via:{field_name}:{via_match.group(1)}")
    return annotations


def _extract_loopback_models(file_fact: FileFact, source: str) -> list[DataModelFact]:
    if "@model" not in source or "@loopback/repository" not in source:
        return []
    models: list[DataModelFact] = []
    for match in LOOPBACK_MODEL_RE.finditer(source):
        open_brace = source.find("{", match.end() - 1)
        close_brace = _find_matching_delimiter(source, open_brace, "{", "}")
        if close_brace is None:
            continue
        body = source[open_brace + 1 : close_brace]
        fields, annotations = _loopback_model_fields(body)
        annotations.append(f"base:{match.group('base')}")
        line = _line_for_offset(source, match.start("name"))
        models.append(
            DataModelFact(
                name=match.group("name"),
                path=file_fact.path,
                kind="loopback-model",
                fields=_dedupe(fields),
                annotations=_dedupe(annotations),
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    return models


def _loopback_model_fields(body: str) -> tuple[list[str], list[str]]:
    fields: list[str] = []
    annotations: list[str] = []
    decorators: list[str] = []
    lines = body.splitlines()
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
        property_match = TS_PROPERTY_RE.match(lines[index])
        if property_match and decorators:
            field_name = property_match.group("name")
            ts_type = " ".join(property_match.group("type").strip().split())
            field_type = _loopback_field_type(ts_type, decorators)
            fields.append(f"{field_name}:{field_type}")
            annotations.extend(_loopback_property_annotations(field_name, field_type, decorators))
            decorators = []
        elif stripped and not stripped.startswith("//"):
            decorators = []
        index += 1
    return fields, annotations


def _loopback_field_type(ts_type: str, decorators: list[str]) -> str:
    joined = " ".join(decorators)
    array_match = re.search(r"@property\.array\(\s*([A-Za-z_$][\w$]*)", joined)
    if array_match:
        return f"Array<{array_match.group(1)}>"
    config_type = re.search(r"\btype\s*:\s*['\"`]([^'\"`]+)['\"`]", joined)
    if config_type:
        return config_type.group(1)
    return ts_type


def _loopback_property_annotations(field_name: str, field_type: str, decorators: list[str]) -> list[str]:
    annotations: list[str] = []
    joined = " ".join(decorators)
    if "@property" in joined:
        annotations.append(f"property:{field_name}")
    if re.search(r"\bid\s*:\s*true\b", joined):
        annotations.append(f"primary-key:{field_name}")
    if re.search(r"\bgenerated\s*:\s*true\b", joined):
        annotations.append(f"generated:{field_name}")
    if re.search(r"\brequired\s*:\s*true\b", joined):
        annotations.append(f"required:{field_name}")
    relation_map = {
        "@belongsTo": "belongsTo",
        "@hasOne": "hasOne",
        "@hasMany": "hasMany",
        "@hasManyThrough": "hasManyThrough",
        "@referencesMany": "referencesMany",
    }
    for decorator, relation in relation_map.items():
        if decorator not in joined:
            continue
        target = _loopback_relation_target(joined) or field_type
        annotations.append(f"relation:{relation}:{field_name}:{target}")
    return annotations


def _loopback_relation_target(source: str) -> str | None:
    match = re.search(r"\(\s*\(\)\s*=>\s*([A-Za-z_$][\w$]*)", source)
    return match.group(1) if match else None


def _extract_nestjs_models(file_fact: FileFact, source: str) -> list[DataModelFact]:
    normalized = file_fact.path.replace("\\", "/").lower()
    if not _looks_like_nestjs_model_source(normalized, source):
        return []
    models: list[DataModelFact] = []
    for match in TS_CLASS_RE.finditer(source):
        name = match.group("name")
        extends = " ".join((match.group("extends") or "").split())
        implements = " ".join((match.group("implements") or "").split())
        if not _looks_like_nestjs_model_class(name, normalized, source, match.start(), extends, implements):
            continue
        open_brace = source.find("{", match.end() - 1)
        close_brace = _find_matching_delimiter(source, open_brace, "{", "}")
        if close_brace is None:
            continue
        body = source[open_brace + 1 : close_brace]
        fields, annotations = _nestjs_model_fields(body)
        if extends:
            annotations.append(f"extends:{extends}")
            partial_match = re.search(r"PartialType\(\s*([A-Za-z_$][\w$]*)\s*\)", extends)
            if partial_match:
                annotations.append(f"partial-of:{partial_match.group(1)}")
        if implements:
            annotations.append(f"implements:{implements}")
        line = _line_for_offset(source, match.start("name"))
        models.append(
            DataModelFact(
                name=name,
                path=file_fact.path,
                kind=_nestjs_model_kind(name, normalized),
                fields=_dedupe(fields),
                annotations=_dedupe(annotations),
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    return models


def _looks_like_nestjs_model_source(normalized_path: str, source: str) -> bool:
    return (
        "/dto/" in f"/{normalized_path}"
        or "/entities/" in f"/{normalized_path}"
        or "/entity/" in f"/{normalized_path}"
        or "@Entity" in source
        or "ApiProperty" in source
        or "class-validator" in source
        or "PartialType(" in source
    )


def _looks_like_nestjs_model_class(
    name: str,
    normalized_path: str,
    source: str,
    offset: int,
    extends: str,
    implements: str,
) -> bool:
    if name.endswith(("Dto", "DTO", "Entity")):
        return True
    if "/dto/" in f"/{normalized_path}" or "/entities/" in f"/{normalized_path}":
        return True
    nearby = source[max(0, offset - 600) : offset + 2000]
    if re.search(r"@\s*Entity\b", nearby):
        return True
    if any(token in extends for token in ("VendureEntity", "BaseEntity")):
        return True
    if "/entity/" in f"/{normalized_path}" and _typescript_class_matches_model_file(normalized_path, name):
        return True
    return "ApiProperty" in nearby or re.search(r"@\s*Is[A-Za-z]+\b", nearby) is not None


def _nestjs_model_kind(name: str, normalized_path: str) -> str:
    if name.endswith(("Dto", "DTO")) or "/dto/" in f"/{normalized_path}":
        return "nestjs-dto"
    if (
        name.endswith("Entity")
        or "/entities/" in f"/{normalized_path}"
        or "/entity/" in f"/{normalized_path}"
        or normalized_path.endswith((".entity.ts", ".entity.js", ".entity.tsx", ".entity.jsx"))
    ):
        return "nestjs-entity"
    return "nestjs-model"


def _typescript_class_matches_model_file(normalized_path: str, name: str) -> bool:
    stem = Path(normalized_path).stem
    stem = stem.removesuffix(".entity").removesuffix(".model").removesuffix(".dto")
    stem = stem.replace("-", "_")
    return stem == _snake_case(name)


def _nestjs_model_fields(body: str) -> tuple[list[str], list[str]]:
    fields: list[str] = []
    annotations: list[str] = []
    decorators: list[str] = []
    lines = body.splitlines()
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
        property_match = TS_PROPERTY_RE.match(lines[index])
        if property_match:
            field_name = property_match.group("name")
            field_type = " ".join(property_match.group("type").strip().split())
            fields.append(f"{field_name}:{field_type}")
            annotations.extend(_nestjs_property_annotations(field_name, lines[index], decorators))
            decorators = []
        elif stripped and not stripped.startswith("//"):
            decorators = []
        index += 1
    return fields, annotations


def _nestjs_property_annotations(field_name: str, line: str, decorators: list[str]) -> list[str]:
    annotations: list[str] = []
    joined = " ".join(decorators)
    is_optional = "?" in line.split(":", 1)[0] or "@IsOptional" in joined or re.search(r"\brequired\s*:\s*false\b", joined) is not None
    if is_optional:
        annotations.append(f"optional:{field_name}")
    if not is_optional and ("@IsNotEmpty" in joined or re.search(r"\brequired\s*:\s*true\b", joined)):
        annotations.append(f"required:{field_name}")
    if "@ApiProperty" in joined:
        annotations.append(f"api-property:{field_name}")
    if "@ApiHideProperty" in joined:
        annotations.append(f"api-hidden:{field_name}")
    if re.search(r"@\s*(?:Column|PrimaryGeneratedColumn|PrimaryColumn|Money)\b", joined):
        annotations.append(f"column:{field_name}")
    if "@EntityId" in joined:
        annotations.append(f"entity-id:{field_name}")
    if re.search(r"@\s*(?:PrimaryGeneratedColumn|PrimaryColumn)\b", joined) or re.search(r"\bprimary\s*:\s*true\b", joined):
        annotations.append(f"primary-key:{field_name}")
    if re.search(r"\bnullable\s*:\s*true\b", joined):
        annotations.append(f"nullable:{field_name}")
    if re.search(r"\bunique\s*:\s*true\b", joined):
        annotations.append(f"unique:{field_name}")
    for relation in re.findall(r"@\s*(OneToOne|OneToMany|ManyToOne|ManyToMany)\b", joined):
        target = _typeorm_relation_target(joined) or "unknown"
        annotations.append(f"relation:{relation}:{field_name}:{target}")
    if "@JoinTable" in joined:
        annotations.append(f"join-table:{field_name}")
    for validator in re.findall(r"@\s*(Is[A-Za-z]+|MinLength|MaxLength|Length|Matches)\b(?:\(([^)]*)\))?", joined):
        name, args = validator
        detail = f":{args.strip()}" if args.strip() else ""
        annotations.append(f"validator:{field_name}:{name}{detail}")
    if "=" in line:
        annotations.append(f"default:{field_name}")
    return annotations


def _typeorm_relation_target(source: str) -> str | None:
    match = re.search(r"(?:type\s*=>|\(\s*\)\s*=>)\s*([A-Za-z_$][\w$]*)", source)
    return match.group(1) if match else None


def _extract_csharp_models(file_fact: FileFact, source: str) -> list[DataModelFact]:
    normalized = file_fact.path.replace("\\", "/").lower()
    models: list[DataModelFact] = []
    for match in CS_CLASS_RE.finditer(source):
        name = match.group("name")
        bases = " ".join((match.group("bases") or "").split())
        if not _looks_like_csharp_model(name, bases, normalized):
            continue
        open_brace = source.find("{", match.end() - 1)
        close_brace = _find_matching_delimiter(source, open_brace, "{", "}")
        if close_brace is None:
            continue
        body = source[open_brace + 1 : close_brace]
        fields, annotations = _csharp_model_fields_and_annotations(body, bases)
        line = _line_for_offset(source, match.start("name"))
        models.append(
            DataModelFact(
                name=name,
                path=file_fact.path,
                kind=_csharp_model_kind(name, bases, normalized),
                fields=_dedupe(fields),
                annotations=_dedupe(annotations),
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    return models


def _looks_like_csharp_model(name: str, bases: str, normalized_path: str) -> bool:
    if any(marker in f"/{normalized_path}" for marker in ("/domain/", "/entities/", "/models/", "/viewmodels/")):
        return True
    if any(token in bases for token in ("BaseEntity", "IAggregateRoot", "BaseRequest", "BaseResponse")):
        return True
    return name.endswith(("Request", "Response", "Dto", "DTO", "ViewModel"))


def _csharp_model_kind(name: str, bases: str, normalized_path: str) -> str:
    if "BaseEntity" in bases or "IAggregateRoot" in bases or any(marker in f"/{normalized_path}" for marker in ("/domain/", "/entities/")):
        return "csharp-entity"
    if "BaseRequest" in bases or name.endswith("Request"):
        return "csharp-request"
    if "BaseResponse" in bases or name.endswith("Response"):
        return "csharp-response"
    if name.endswith(("Dto", "DTO")):
        return "csharp-dto"
    if name.endswith("ViewModel") or "/viewmodels/" in f"/{normalized_path}":
        return "csharp-view-model"
    return "csharp-model"


def _csharp_model_fields_and_annotations(body: str, bases: str) -> tuple[list[str], list[str]]:
    fields: list[str] = []
    annotations: list[str] = []
    if bases:
        annotations.append(f"bases:{bases}")
    for match in CS_PROPERTY_RE.finditer(body):
        if _csharp_brace_depth_before(body, match.start()) != 0:
            continue
        field_type = " ".join(match.group("type").split())
        field_name = match.group("name")
        fields.append(f"{field_name}:{field_type}")
        accessor = body[match.start() : body.find("}", match.start()) + 1]
        if "private set" in accessor:
            annotations.append(f"private-set:{field_name}")
        if "init" in accessor:
            annotations.append(f"init-only:{field_name}")
        if field_type.endswith("?"):
            annotations.append(f"nullable:{field_name}")
    return fields, annotations


def _extract_kotlin_models(file_fact: FileFact, source: str) -> list[DataModelFact]:
    models: list[DataModelFact] = []
    for match in KOTLIN_DATA_CLASS_RE.finditer(source):
        open_paren = source.find("(", match.end() - 1)
        close_paren = _find_matching_delimiter(source, open_paren, "(", ")")
        if close_paren is None:
            continue
        name = match.group("name")
        attrs = _kotlin_annotation_block_before(source, match.start()) or match.group("attrs") or ""
        body = source[open_paren + 1 : close_paren]
        fields = _kotlin_model_fields(body)
        if not fields and not _looks_like_kotlin_model(file_fact.path, name, attrs):
            continue
        line = _line_for_offset(source, match.start("name"))
        models.append(
            DataModelFact(
                name=name,
                path=file_fact.path,
                kind=_kotlin_model_kind(file_fact.path, name, attrs),
                fields=_dedupe(fields),
                annotations=_dedupe(_kotlin_model_annotations(attrs)),
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    return models


def _kotlin_model_fields(body: str) -> list[str]:
    fields: list[str] = []
    for part in _split_kotlin_constructor_params(body):
        match = KOTLIN_FIELD_RE.search(part.strip())
        if match:
            fields.append(f"{match.group('name')}:{' '.join(match.group('type').strip().split())}")
    return fields


def _split_kotlin_constructor_params(body: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth_angle = 0
    depth_paren = 0
    depth_bracket = 0
    for char in body:
        if char == "<":
            depth_angle += 1
        elif char == ">" and depth_angle:
            depth_angle -= 1
        elif char == "(":
            depth_paren += 1
        elif char == ")" and depth_paren:
            depth_paren -= 1
        elif char == "[":
            depth_bracket += 1
        elif char == "]" and depth_bracket:
            depth_bracket -= 1
        if char == "," and depth_angle == 0 and depth_paren == 0 and depth_bracket == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    if current:
        parts.append("".join(current))
    return parts


def _looks_like_kotlin_model(path: str, name: str, attrs: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return (
        "/model/" in f"/{normalized}"
        or "/models/" in f"/{normalized}"
        or "/database/" in f"/{normalized}"
        or "/network/" in f"/{normalized}"
        or "@Entity" in attrs
        or "@Serializable" in attrs
        or name.endswith(("Dto", "DTO", "Entity", "Model", "State", "Result"))
    )


def _kotlin_model_kind(path: str, name: str, attrs: str) -> str:
    normalized = path.replace("\\", "/").lower()
    if "@Entity" in attrs or name.endswith("Entity") or "/database/" in f"/{normalized}":
        return "kotlin-room-entity"
    if "@Serializable" in attrs or "/network/" in f"/{normalized}":
        return "kotlin-serializable-model"
    if name.endswith(("State", "Result")):
        return "kotlin-ui-state"
    return "kotlin-data-class"


def _kotlin_model_annotations(attrs: str) -> list[str]:
    annotations = [f"annotation:{name}" for name in re.findall(r"@([A-Za-z_]\w*)", attrs)]
    table = re.search(r"tableName\s*=\s*\"([^\"]+)\"", attrs)
    if table:
        annotations.append(f"table:{table.group(1)}")
    return annotations


def _kotlin_annotation_block_before(source: str, offset: int) -> str:
    lines = source[:offset].splitlines()
    window = lines[-14:]
    start: int | None = None
    for index in range(len(window) - 1, -1, -1):
        if window[index].lstrip().startswith("@"):
            start = index
            break
        if not window[index].strip():
            continue
        if start is None and window[index].lstrip().startswith(("//", "/*", "*", "*/")):
            break
    if start is None:
        return ""
    block_lines: list[str] = []
    for line in window[start:]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("//", "/*", "*", "*/")):
            continue
        block_lines.append(line)
    return "\n".join(block_lines)


def _extract_swift_models(file_fact: FileFact, source: str) -> list[DataModelFact]:
    models: list[DataModelFact] = []
    spans = _swift_type_spans(source)
    for type_match, open_brace, close_brace in spans:
        name = type_match.group("name")
        type_kind = type_match.group("type_kind")
        bases = " ".join((type_match.group("bases") or "").split())
        attrs = type_match.group("attrs") or ""
        body = source[open_brace + 1 : close_brace]
        parent = _swift_nearest_parent_type(spans, type_match.start(), open_brace, close_brace)
        kind = _swift_model_kind(file_fact.path, name, type_kind, bases, attrs, body, parent)
        if not kind:
            continue
        fields, annotations = _swift_model_fields_and_annotations(type_kind, bases, attrs, body, parent)
        display_name = _swift_display_model_name(name, parent, kind)
        line = _line_for_offset(source, type_match.start("name"))
        models.append(
            DataModelFact(
                name=display_name,
                path=file_fact.path,
                kind=kind,
                fields=_dedupe(fields),
                annotations=_dedupe(annotations),
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    return models


def _swift_type_spans(source: str) -> list[tuple[re.Match[str], int, int]]:
    spans: list[tuple[re.Match[str], int, int]] = []
    for match in SWIFT_TYPE_HEAD_RE.finditer(source):
        open_brace = source.find("{", match.end() - 1)
        close_brace = _find_matching_delimiter(source, open_brace, "{", "}")
        if close_brace is None:
            continue
        spans.append((match, open_brace, close_brace))
    return spans


def _swift_nearest_parent_type(
    spans: list[tuple[re.Match[str], int, int]],
    offset: int,
    open_brace: int,
    close_brace: int,
) -> str | None:
    parents = [
        (candidate_open, candidate_match.group("name"))
        for candidate_match, candidate_open, candidate_close in spans
        if candidate_open < offset < candidate_close and not (candidate_open == open_brace and candidate_close == close_brace)
    ]
    if not parents:
        return None
    return max(parents, key=lambda item: item[0])[1]


def _swift_model_kind(
    path: str,
    name: str,
    type_kind: str,
    bases: str,
    attrs: str,
    body: str,
    parent: str | None,
) -> str | None:
    normalized = path.replace("\\", "/").lower()
    if "@Reducer" in attrs or "Reducer" in bases or (name.endswith("Reducer") and "some Reducer" in body):
        return "tca-reducer"
    if "@ObservableState" in attrs or name in {"State", "ViewState"} and parent:
        return "tca-state" if _looks_like_tca_context(attrs, body, parent, normalized) else "swift-state-model"
    if "Codable" in bases or "Decodable" in bases or "Encodable" in bases:
        return "swift-codable-model"
    if any(base.strip().split(".")[-1] == "Model" for base in bases.split(",")):
        return "fluent-model"
    if name.endswith("State"):
        return "tca-state" if _looks_like_tca_context(attrs, body, parent, normalized) else "swift-state-model"
    if type_kind == "enum" and (name == "Action" or name.endswith("Action")):
        return "tca-action" if _looks_like_tca_context(attrs, body, parent, normalized) else "swift-action-model"
    if "Equatable" in bases or "Identifiable" in bases or "Hashable" in bases:
        return "swift-model"
    if any(marker in f"/{normalized}" for marker in ("/models/", "/clientmodels/", "/sharedmodels/", "/serverrouter/")):
        return "swift-model"
    if name.endswith(("Request", "Response", "Envelope", "Model", "Context", "Settings")):
        return "swift-model"
    return None


def _looks_like_tca_context(attrs: str, body: str, parent: str | None, normalized_path: str) -> bool:
    return (
        bool(parent)
        or "@ObservableState" in attrs
        or "@Reducer" in attrs
        or "BindableAction" in body
        or "Reducer" in body
        or "/feature/" in f"/{normalized_path}"
        or normalized_path.endswith("feature.swift")
    )


def _swift_display_model_name(name: str, parent: str | None, kind: str) -> str:
    if parent and kind in {"tca-state", "tca-action"} and name in {"State", "Action"}:
        return f"{parent}.{name}"
    return name


def _swift_model_fields_and_annotations(
    type_kind: str,
    bases: str,
    attrs: str,
    body: str,
    parent: str | None,
) -> tuple[list[str], list[str]]:
    fields: list[str] = []
    annotations: list[str] = []
    if bases:
        annotations.extend(f"conforms:{item.strip()}" for item in bases.split(",") if item.strip())
    annotations.extend(f"annotation:{name}" for name in re.findall(r"@([A-Za-z_]\w*)", attrs))
    if parent:
        annotations.append(f"parent:{parent}")
    schema = re.search(r"\bstatic\s+let\s+schema\s*=\s*['\"](?P<schema>[^'\"]+)['\"]", body)
    if schema:
        annotations.append(f"table:{schema.group('schema')}")
    annotations.extend(_swift_property_wrapper_annotations(body))
    if type_kind == "enum":
        for case_match in SWIFT_CASE_RE.finditer(body):
            case_name = case_match.group("name")
            args = " ".join((case_match.group("args") or "").split())
            fields.append(f"case:{case_name}{f'({args})' if args else ''}")
        return fields, annotations
    for field_match in SWIFT_FIELD_RE.finditer(body):
        if _swift_brace_depth_before(body, field_match.start()) != 0:
            continue
        field_name = field_match.group("name")
        field_type = " ".join(field_match.group("type").strip().rstrip(",").split())
        if field_name == "body" and field_type.startswith("some View"):
            continue
        fields.append(f"{field_name}:{field_type}")
        if field_type.endswith("?"):
            annotations.append(f"optional:{field_name}")
        if "IdentifiedArray" in field_type:
            annotations.append(f"identified-array:{field_name}")
    return fields, annotations


def _swift_property_wrapper_annotations(body: str) -> list[str]:
    annotations: list[str] = []
    pattern = re.compile(
        r"@(?P<wrapper>ID|Field|OptionalField|Parent|Children|Siblings|Timestamp)\s*(?:\((?P<args>[^)]*)\))?"
        r"\s*(?:\r?\n\s*)+(?:public\s+|internal\s+|private\s+|fileprivate\s+)?var\s+"
        r"(?P<name>[A-Za-z_]\w*)\s*:\s*(?P<type>[^=\n{]+)",
        re.MULTILINE,
    )
    for match in pattern.finditer(body):
        wrapper = match.group("wrapper")
        name = match.group("name")
        field_type = " ".join(match.group("type").strip().split())
        key = _swift_wrapper_key(match.group("args") or "")
        if key:
            annotations.append(f"column:{name}:{key}")
        if wrapper in {"Parent", "Children", "Siblings"}:
            annotations.append(f"relation:{wrapper.lower()}:{name}:{field_type}")
        else:
            annotations.append(f"fluent-field:{wrapper}:{name}")
    return annotations


def _swift_wrapper_key(args: str) -> str | None:
    key = re.search(r"\bkey\s*:\s*['\"](?P<key>[^'\"]+)['\"]", args)
    if key:
        return key.group("key")
    custom = re.search(r"\bcustom\s*:\s*\.?(?P<key>[A-Za-z_]\w*)", args)
    if custom:
        return custom.group("key")
    return None


def _swift_brace_depth_before(source: str, offset: int) -> int:
    depth = 0
    for char in source[:offset]:
        if char == "{":
            depth += 1
        elif char == "}":
            depth = max(0, depth - 1)
    return depth


def _csharp_brace_depth_before(source: str, offset: int) -> int:
    depth = 0
    quote: str | None = None
    escaped = False
    for char in source[:offset]:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth = max(0, depth - 1)
    return depth


def _extract_dart_freezed_models(file_fact: FileFact, source: str) -> list[DataModelFact]:
    if "@freezed" not in source and "freezed_annotation" not in source:
        return []
    models: list[DataModelFact] = []
    for match in DART_FREEZED_CLASS_RE.finditer(source):
        name = match.group("name")
        open_brace = source.find("{", match.end() - 1)
        close_brace = _find_matching_delimiter(source, open_brace, "{", "}")
        if close_brace is None:
            continue
        body = source[open_brace + 1 : close_brace]
        factories = [item for item in DART_FACTORY_RE.finditer(body) if item.group("name") == name]
        if not factories:
            continue
        fields: list[str] = []
        annotations: list[str] = []
        for factory in factories:
            factory_fields, factory_annotations = _dart_factory_fields(factory.group("body"))
            fields.extend(factory_fields)
            annotations.extend(factory_annotations)
            if factory.group("variant"):
                annotations.append(f"factory:{factory.group('variant')}")
        if "fromJson" in body or f"_${name}FromJson" in body:
            annotations.append("json-serializable")
        line = _line_for_offset(source, match.start("name"))
        models.append(
            DataModelFact(
                name=name,
                path=file_fact.path,
                kind="dart-freezed-model",
                fields=_dedupe(fields),
                annotations=_dedupe(annotations),
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    return models


def _dart_factory_fields(body: str) -> tuple[list[str], list[str]]:
    fields: list[str] = []
    annotations: list[str] = []
    cleaned_body = body.strip()
    if cleaned_body.startswith("{") and cleaned_body.endswith("}"):
        cleaned_body = cleaned_body[1:-1].strip()
    for part in _split_rust_top_level_commas(cleaned_body):
        raw = " ".join(part.strip().split())
        if not raw:
            continue
        json_key = re.search(r"@\s*JsonKey\s*\([^)]*\bname\s*:\s*['\"](?P<name>[^'\"]+)['\"]", raw)
        raw = re.sub(r"@\s*[A-Za-z_]\w*(?:\([^)]*\))?\s*", "", raw).strip()
        if not raw:
            continue
        has_default = "=" in raw
        raw = raw.split("=", 1)[0].strip()
        required = raw.startswith("required ")
        if required:
            raw = raw.removeprefix("required ").strip()
        raw = re.sub(r"^(?:final|covariant)\s+", "", raw)
        if raw.startswith("this."):
            field_name = raw.removeprefix("this.").strip()
            field_type = "unknown"
        else:
            tokens = raw.rsplit(" ", 1)
            if len(tokens) != 2:
                continue
            field_type, field_name = tokens[0].strip(), tokens[1].strip()
        field_name = field_name.rstrip(",")
        if not re.fullmatch(r"[A-Za-z_]\w*", field_name):
            continue
        fields.append(f"{field_name}:{field_type}")
        if required:
            annotations.append(f"required:{field_name}")
        if has_default:
            annotations.append(f"default:{field_name}")
        if json_key:
            annotations.append(f"json-key:{field_name}:{json_key.group('name')}")
    return fields, annotations


def _extract_ecto_schema_models(file_fact: FileFact, source: str) -> list[DataModelFact]:
    if "Ecto.Schema" not in source and "schema " not in source:
        return []
    module_name = _elixir_module_name(source)
    models: list[DataModelFact] = []
    for match in ECTO_SCHEMA_RE.finditer(source):
        block = _elixir_do_block(source, match.start())
        if block is None:
            continue
        table = match.group("table")
        fields, annotations = _ecto_schema_fields(block)
        annotations.insert(0, f"table:{table}")
        line = _line_for_offset(source, match.start())
        models.append(
            DataModelFact(
                name=(module_name.split(".")[-1] if module_name else _pascal_case(table)),
                path=file_fact.path,
                kind="ecto-schema",
                fields=_dedupe(fields),
                annotations=_dedupe(annotations),
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    return models


def _elixir_module_name(source: str) -> str | None:
    match = ELIXIR_MODULE_RE.search(source)
    return match.group("name") if match else None


def _elixir_do_block(source: str, offset: int) -> str | None:
    line_start = source.rfind("\n", 0, offset) + 1
    lines = source[line_start:].splitlines()
    depth = 0
    collected: list[str] = []
    started = False
    for line in lines:
        if not started:
            if re.search(r"\bdo\s*(?:#.*)?$", line):
                started = True
                depth = 1
            continue
        stripped = line.strip()
        if re.search(r"\bdo\s*(?:#.*)?$", line):
            depth += 1
        if stripped == "end":
            depth -= 1
            if depth == 0:
                return "\n".join(collected)
        collected.append(line)
    return None


def _ecto_schema_fields(block: str) -> tuple[list[str], list[str]]:
    fields: list[str] = []
    annotations: list[str] = []
    for line in block.splitlines():
        stripped = line.strip()
        field_match = re.match(
            r"field\s*\(?\s*:(?P<name>[A-Za-z_]\w*)\s*,\s*"
            r"(?P<type>\{[^}]+\}|:?[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)(?P<opts>.*)$",
            stripped,
        )
        if field_match:
            name = field_match.group("name")
            type_name = _ecto_type_name(field_match.group("type"))
            opts = field_match.group("opts") or ""
            fields.append(f"{name}:{type_name}")
            if "Ecto.Enum" in type_name:
                annotations.append(f"enum:{name}")
                enum_values = re.search(r"values:\s*\[(?P<values>[^\]]+)\]", opts)
                if enum_values:
                    annotations.append(f"enum-values:{name}:{'|'.join(_ecto_atom_names(enum_values.group('values')))}")
            if "default:" in opts:
                annotations.append(f"default:{name}")
            if "virtual: true" in opts:
                annotations.append(f"virtual:{name}")
            continue

        relation_match = re.match(
            r"(?P<kind>belongs_to|has_one|has_many|many_to_many)\s*\(?\s*:"
            r"(?P<name>[A-Za-z_]\w*)\s*,\s*(?P<target>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)",
            stripped,
        )
        if relation_match:
            fields.append(f"{relation_match.group('name')}:{relation_match.group('target')}")
            annotations.append(
                f"relation:{relation_match.group('kind')}:{relation_match.group('name')}:{relation_match.group('target')}"
            )
            continue

        embed_match = re.match(
            r"(?P<kind>embeds_one|embeds_many)\s*\(?\s*:(?P<name>[A-Za-z_]\w*)\s*,\s*(?P<target>[A-Za-z_]\w*)",
            stripped,
        )
        if embed_match:
            fields.append(f"{embed_match.group('name')}:{embed_match.group('target')}")
            annotations.append(f"embed:{embed_match.group('kind')}:{embed_match.group('name')}:{embed_match.group('target')}")
            continue

        if stripped.startswith("timestamps("):
            annotations.append("timestamps:true")
    return fields, annotations


def _ecto_type_name(value: str) -> str:
    stripped = value.strip().rstrip(")")
    array_match = re.match(r"\{\s*:array\s*,\s*:(?P<type>[A-Za-z_]\w*)\s*\}", stripped)
    if array_match:
        return f"array:{array_match.group('type')}"
    return stripped.removeprefix(":")


def _ecto_atom_names(source: str) -> list[str]:
    names = re.findall(r":([A-Za-z_]\w*)", source)
    names.extend(re.findall(r"\b([A-Za-z_]\w*)\s*:", source))
    return _dedupe(names)


def _extract_prisma_models(file_fact: FileFact, source: str) -> list[DataModelFact]:
    models: list[DataModelFact] = []
    for match in PRISMA_MODEL_RE.finditer(source):
        fields, annotations = _prisma_model_fields(match.group("body"))
        line = _line_for_offset(source, match.start("name"))
        models.append(
            DataModelFact(
                name=match.group("name"),
                path=file_fact.path,
                kind="prisma-model",
                fields=_dedupe(fields),
                annotations=_dedupe(annotations),
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    return models


def _prisma_model_fields(body: str) -> tuple[list[str], list[str]]:
    fields: list[str] = []
    annotations: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "@@")):
            continue
        match = re.match(r"(?P<name>[A-Za-z_]\w*)\s+(?P<type>[A-Za-z_][\w\[\]?]*)(?P<attrs>.*)$", stripped)
        if not match:
            continue
        name = match.group("name")
        type_name = match.group("type")
        attrs = match.group("attrs")
        fields.append(f"{name}:{type_name}")
        if type_name.endswith("?"):
            annotations.append(f"optional:{name}")
        if type_name.endswith("[]"):
            annotations.append(f"list:{name}")
        if "@id" in attrs:
            annotations.append(f"primary-key:{name}")
        if "@unique" in attrs:
            annotations.append(f"unique:{name}")
        if "@updatedAt" in attrs:
            annotations.append(f"updatedAt:{name}")
        default_match = re.search(r"@default\(([^)]*(?:\)[^)]*)?)\)", attrs)
        if default_match:
            annotations.append(f"default:{name}:{default_match.group(1)}")
        relation_match = re.search(r"@relation\(([^)]*)\)", attrs)
        if relation_match:
            annotations.append(f"relation:{name}:{relation_match.group(1).strip()}")
    return fields, annotations


def _extract_strapi_schema_model(file_fact: FileFact, source: str) -> DataModelFact | None:
    normalized = file_fact.path.replace("\\", "/").lower()
    if "/content-types/" not in f"/{normalized}" and "/components/" not in f"/{normalized}":
        return None
    try:
        schema = json.loads(source)
    except json.JSONDecodeError:
        return None
    if not isinstance(schema, dict) or not isinstance(schema.get("attributes"), dict):
        return None

    info = schema.get("info") if isinstance(schema.get("info"), dict) else {}
    name = _string_value(info.get("singularName")) or _string_value(info.get("displayName")) or Path(file_fact.path).parent.name
    fields, annotations = _strapi_schema_fields(schema["attributes"])
    collection_name = _string_value(schema.get("collectionName"))
    kind_value = _string_value(schema.get("kind"))
    if collection_name:
        annotations.append(f"collection:{collection_name}")
    if kind_value:
        annotations.append(f"kind:{kind_value}")
    options = schema.get("options") if isinstance(schema.get("options"), dict) else {}
    if options.get("draftAndPublish") is True:
        annotations.append("draftAndPublish:true")
    plugin_options = schema.get("pluginOptions") if isinstance(schema.get("pluginOptions"), dict) else {}
    i18n = plugin_options.get("i18n") if isinstance(plugin_options.get("i18n"), dict) else {}
    if i18n.get("localized") is True:
        annotations.append("localized:model")

    return DataModelFact(
        name=name,
        path=file_fact.path,
        kind=_strapi_schema_kind(normalized),
        fields=_dedupe(fields),
        annotations=_dedupe(annotations),
        evidence=Evidence(file=file_fact.path, kind="data-model", line_start=1, line_end=1),
    )


def _strapi_schema_kind(normalized_path: str) -> str:
    if "/content-types/" in f"/{normalized_path}":
        return "strapi-content-type"
    if "/components/" in f"/{normalized_path}":
        return "strapi-component"
    return "strapi-schema"


def _strapi_schema_fields(attributes: object) -> tuple[list[str], list[str]]:
    fields: list[str] = []
    annotations: list[str] = []
    if not isinstance(attributes, dict):
        return fields, annotations
    for field_name, raw_config in attributes.items():
        if not isinstance(field_name, str) or not isinstance(raw_config, dict):
            continue
        attr_type = _string_value(raw_config.get("type")) or "unknown"
        field_type = attr_type
        if attr_type == "relation":
            relation = _string_value(raw_config.get("relation")) or "relation"
            target = _string_value(raw_config.get("target")) or "unknown"
            field_type = f"relation<{target}>"
            annotations.append(f"relation:{field_name}:{relation}:{target}")
            inversed_by = _string_value(raw_config.get("inversedBy"))
            mapped_by = _string_value(raw_config.get("mappedBy"))
            if inversed_by:
                annotations.append(f"inversedBy:{field_name}:{inversed_by}")
            if mapped_by:
                annotations.append(f"mappedBy:{field_name}:{mapped_by}")
        elif attr_type == "component":
            component = _string_value(raw_config.get("component")) or "unknown"
            repeatable = raw_config.get("repeatable") is True
            field_type = f"component<{component}>"
            annotations.append(f"component:{field_name}:{component}")
            if repeatable:
                annotations.append(f"repeatable:{field_name}")
        elif attr_type == "dynamiczone":
            components = raw_config.get("components") if isinstance(raw_config.get("components"), list) else []
            component_names = [str(item) for item in components if item]
            component_list = "|".join(component_names)
            field_type = f"dynamiczone<{component_list}>" if component_list else "dynamiczone"
            annotations.append(f"dynamiczone:{field_name}:{'|'.join(component_names) if component_names else 'unknown'}")
        elif attr_type == "media":
            field_type = "media[] " if raw_config.get("multiple") is True else "media"
            field_type = field_type.strip()
        elif attr_type == "customField":
            field_type = f"customField<{_string_value(raw_config.get('customField')) or 'unknown'}>"
        fields.append(f"{field_name}:{field_type}")
        if raw_config.get("required") is True:
            annotations.append(f"required:{field_name}")
        if raw_config.get("unique") is True:
            annotations.append(f"unique:{field_name}")
        target_field = _string_value(raw_config.get("targetField"))
        if target_field:
            annotations.append(f"targetField:{field_name}:{target_field}")
        plugin_options = raw_config.get("pluginOptions") if isinstance(raw_config.get("pluginOptions"), dict) else {}
        i18n = plugin_options.get("i18n") if isinstance(plugin_options.get("i18n"), dict) else {}
        if i18n.get("localized") is True:
            annotations.append(f"localized:{field_name}")
        enum_values = raw_config.get("enum") if isinstance(raw_config.get("enum"), list) else []
        if enum_values:
            annotations.append(f"enum:{field_name}:{'|'.join(str(item) for item in enum_values)}")
    return fields, annotations


def _string_value(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _first_match(source: str, pattern: str) -> str | None:
    match = re.search(pattern, source, re.MULTILINE)
    return match.group(1) if match else None


def _pascal_case(value: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in re.split(r"[^A-Za-z0-9]+", value) if part)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _line_for_offset(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _find_matching_delimiter(source: str, open_index: int, open_char: str, close_char: str) -> int | None:
    if open_index < 0 or open_index >= len(source):
        return None
    depth = 0
    for index in range(open_index, len(source)):
        char = source[index]
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return index
    return None


def _split_rust_top_level_commas(source: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depths = {"<": 0, "(": 0, "[": 0, "{": 0}
    closing = {">": "<", ")": "(", "]": "[", "}": "{"}
    for index, char in enumerate(source):
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
    part = source[start:].strip()
    if part:
        parts.append(part)
    return parts


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _dedupe_models(models: list[DataModelFact]) -> list[DataModelFact]:
    seen: set[tuple[str, str, str]] = set()
    result: list[DataModelFact] = []
    for model in models:
        key = (model.path, model.kind, model.name)
        if key in seen:
            continue
        seen.add(key)
        result.append(model)
    return result
