from __future__ import annotations

import re
from bisect import bisect_right
from pathlib import Path

from specforge.models import CommandFact, Evidence, ExtractionIssue, FileFact, ImportFact, SymbolFact


SUPPORTED_LANGUAGES = {
    "clojure",
    "csharp",
    "dart",
    "elixir",
    "go",
    "kotlin",
    "php",
    "ruby",
    "rust",
    "scala",
    "svelte",
}

GO_IMPORT_BLOCK_RE = re.compile(r"^\s*import\s*\((?P<body>.*?)^\s*\)", re.MULTILINE | re.DOTALL)
GO_IMPORT_LINE_RE = re.compile(r'^\s*import\s+(?:[._A-Za-z]\w*\s+)?["](?P<module>[^"]+)["]', re.MULTILINE)
GO_BLOCK_MODULE_RE = re.compile(r'(?:^|\s)(?:[._A-Za-z]\w*\s+)?["](?P<module>[^"]+)["]')
GO_FUNC_RE = re.compile(
    r"^\s*func\s+(?P<receiver>\([^)]*\)\s*)?(?P<name>[A-Za-z_]\w*)\s*\((?P<args>[^)]*)\)",
    re.MULTILINE,
)
GO_TYPE_RE = re.compile(r"^\s*type\s+(?P<name>[A-Za-z_]\w*)\s+(?P<kind>struct|interface|func|map|\[)", re.MULTILINE)

RUST_IMPORT_RE = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?use\s+(?P<module>[^;]+);", re.MULTILINE)
RUST_MOD_RE = re.compile(r"^\s*(?:pub\s+)?mod\s+(?P<name>[A-Za-z_]\w*)\s*;", re.MULTILINE)
RUST_FN_RE = re.compile(
    r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+(?P<name>[A-Za-z_]\w*)\s*\((?P<args>[^)]*)\)",
    re.MULTILINE,
)
RUST_TYPE_RE = re.compile(
    r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?P<kind>struct|enum|trait)\s+(?P<name>[A-Za-z_]\w*)",
    re.MULTILINE,
)

CSHARP_USING_RE = re.compile(r"^\s*using\s+(?:static\s+)?(?P<module>[A-Za-z_][\w.]+)\s*;", re.MULTILINE)
CSHARP_TYPE_RE = re.compile(
    r"^\s*(?:(?:public|private|protected|internal|static|abstract|sealed|partial|readonly|record)\s+)*"
    r"(?P<kind>class|interface|record|struct|enum)\s+(?P<name>[A-Za-z_]\w*)",
    re.MULTILINE,
)
CSHARP_METHOD_RE = re.compile(
    r"^\s*(?:(?:public|private|protected|internal|static|async|virtual|override|sealed|partial|new)\s+)+"
    r"(?P<return>[A-Za-z_][\w<>,.?[\]\s]*?)\s+(?P<name>[A-Za-z_]\w*)\s*\((?P<args>[^)]*)\)",
    re.MULTILINE,
)

PHP_IMPORT_RE = re.compile(r"^\s*use\s+(?P<module>[A-Za-z_\\][\w\\]+)", re.MULTILINE)
PHP_REQUIRE_RE = re.compile(r"\b(?:require|require_once|include|include_once)\s*\(?\s*['\"](?P<module>[^'\"]+)['\"]")
PHP_TYPE_RE = re.compile(r"^\s*(?:(?:abstract|final|readonly)\s+)*(?P<kind>class|interface|trait|enum)\s+(?P<name>[A-Za-z_]\w*)", re.MULTILINE)
PHP_FUNCTION_RE = re.compile(r"^\s*(?:(?:public|private|protected|static|final|abstract)\s+)*function\s+(?P<name>[A-Za-z_]\w*)\s*\((?P<args>[^)]*)\)", re.MULTILINE)

RUBY_REQUIRE_RE = re.compile(r"^\s*(?P<kind>require|require_relative)\s+['\"](?P<module>[^'\"]+)['\"]", re.MULTILINE)
RUBY_TYPE_RE = re.compile(r"^\s*(?P<kind>class|module)\s+(?P<name>[A-Za-z_:]\w*(?:::[A-Za-z_]\w*)*)", re.MULTILINE)
RUBY_DEF_RE = re.compile(r"^\s*def\s+(?P<name>(?:self\.)?[A-Za-z_]\w*[!?=]?)\s*(?P<args>\([^)]*\)|[^\n]*)", re.MULTILINE)

KOTLIN_IMPORT_RE = re.compile(r"^\s*import\s+(?P<module>[A-Za-z_][\w.*]+)", re.MULTILINE)
KOTLIN_TYPE_RE = re.compile(
    r"^\s*(?:(?:public|private|protected|internal|open|data|sealed|abstract|enum|value|annotation)\s+)*"
    r"(?P<kind>class|object|interface)\s+(?P<name>[A-Za-z_]\w*)",
    re.MULTILINE,
)
KOTLIN_FUN_RE = re.compile(r"^\s*(?:(?:public|private|protected|internal|suspend|inline|override|open)\s+)*fun\s+(?:<[^>]+>\s*)?(?P<name>[A-Za-z_]\w*)\s*\((?P<args>[^)]*)\)", re.MULTILINE)

DART_IMPORT_RE = re.compile(r"^\s*(?P<kind>import|export|part)\s+['\"](?P<module>[^'\"]+)['\"]", re.MULTILINE)
DART_TYPE_RE = re.compile(r"^\s*(?P<kind>class|mixin|extension|enum)\s+(?P<name>[A-Za-z_]\w*)", re.MULTILINE)
DART_FUNCTION_RE = re.compile(
    r"^\s*(?:(?:static|final|const|external)\s+)*(?:[A-Za-z_<][\w<>?,\s]*\s+)?"
    r"(?P<name>[A-Za-z_]\w*)\s*\((?P<args>[^)]*)\)\s*(?:async\s*)?(?:\{|=>)",
    re.MULTILINE,
)

ELIXIR_IMPORT_RE = re.compile(r"^\s*(?P<kind>alias|import|use)\s+(?P<module>[A-Z][\w.]+)", re.MULTILINE)
ELIXIR_MODULE_RE = re.compile(r"^\s*defmodule\s+(?P<name>[A-Z][\w.]+)\s+do", re.MULTILINE)
ELIXIR_DEF_RE = re.compile(r"^\s*(?P<kind>defp?|defmacro)\s+(?P<name>[a-z_]\w*[!?=]?)\s*(?P<args>\([^)]*\))?", re.MULTILINE)

CLOJURE_NS_RE = re.compile(r"^\s*\(ns\s+(?P<module>[A-Za-z0-9_.-]+)", re.MULTILINE)
CLOJURE_REQUIRE_RE = re.compile(r"\[\s*(?P<module>[A-Za-z0-9_.-]+)(?:\s|])")
CLOJURE_DEF_RE = re.compile(r"^\s*\((?P<kind>defn|defrecord|defprotocol|defmulti|def)\s+(?P<name>[^\s)]+)", re.MULTILINE)

SVELTE_SCRIPT_RE = re.compile(r"<script\b[^>]*>(?P<body>.*?)</script>", re.IGNORECASE | re.DOTALL)
SVELTE_IMPORT_RE = re.compile(r"^\s*import\s+(?P<names>.+?)\s+from\s+['\"](?P<module>[^'\"]+)['\"]", re.MULTILINE)
SCALA_IMPORT_RE = re.compile(r"^\s*import\s+(?P<module>[A-Za-z_][\w.{}_, *=>]+)", re.MULTILINE)
SCALA_TYPE_RE = re.compile(
    r"^\s*(?:(?:final|sealed|abstract|private|protected)\s+)*(?P<case>case\s+)?(?P<kind>class|object|trait|enum)\s+(?P<name>[A-Za-z_]\w*)",
    re.MULTILINE,
)
SCALA_DEF_RE = re.compile(r"^\s*(?:(?:private|protected|override|final|implicit)\s+)*def\s+(?P<name>[A-Za-z_]\w*)\s*(?P<args>\([^)]*\))?", re.MULTILINE)

SKIPPED_DART_FUNCTIONS = {"assert", "for", "if", "switch", "while"}


def extract_polyglot_facts(
    root: Path,
    files: list[FileFact],
) -> tuple[list[ImportFact], list[SymbolFact], list[CommandFact], list[ExtractionIssue]]:
    imports: list[ImportFact] = []
    symbols: list[SymbolFact] = []
    issues: list[ExtractionIssue] = []

    for file_fact in files:
        if file_fact.role in {"generated", "sample"}:
            continue
        if file_fact.language not in SUPPORTED_LANGUAGES:
            continue
        path = root / file_fact.path
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as error:
            issues.append(
                ExtractionIssue(
                    path=file_fact.path,
                    extractor="polyglot-text",
                    message=str(error),
                    evidence=Evidence(file=file_fact.path, kind="polyglot-text"),
                )
            )
            continue

        line_starts = _line_starts(source)
        language_imports, language_symbols = _extract_for_language(file_fact, source, line_starts)
        imports.extend(language_imports)
        symbols.extend(language_symbols)

    return _dedupe_imports(imports), _dedupe_symbols(symbols), [], issues


def _extract_for_language(
    file_fact: FileFact,
    source: str,
    line_starts: list[int],
) -> tuple[list[ImportFact], list[SymbolFact]]:
    language = file_fact.language
    if language == "go":
        return _extract_go(file_fact, source, line_starts)
    if language == "rust":
        return _extract_rust(file_fact, source, line_starts)
    if language == "csharp":
        return _extract_csharp(file_fact, source, line_starts)
    if language == "php":
        return _extract_php(file_fact, source, line_starts)
    if language == "ruby":
        return _extract_ruby(file_fact, source, line_starts)
    if language == "kotlin":
        return _extract_kotlin(file_fact, source, line_starts)
    if language == "dart":
        return _extract_dart(file_fact, source, line_starts)
    if language == "elixir":
        return _extract_elixir(file_fact, source, line_starts)
    if language == "clojure":
        return _extract_clojure(file_fact, source, line_starts)
    if language == "scala":
        return _extract_scala(file_fact, source, line_starts)
    if language == "svelte":
        return _extract_svelte(file_fact, source, line_starts)
    return [], []


def _extract_go(file_fact: FileFact, source: str, line_starts: list[int]) -> tuple[list[ImportFact], list[SymbolFact]]:
    imports: list[ImportFact] = []
    for match in GO_IMPORT_LINE_RE.finditer(source):
        imports.append(_import(file_fact.path, match.group("module"), [], "go-import", match.start(), line_starts))
    for block in GO_IMPORT_BLOCK_RE.finditer(source):
        for match in GO_BLOCK_MODULE_RE.finditer(block.group("body")):
            offset = block.start("body") + match.start("module")
            imports.append(_import(file_fact.path, match.group("module"), [], "go-import", offset, line_starts))

    symbols: list[SymbolFact] = []
    for match in GO_FUNC_RE.finditer(source):
        kind = "method" if match.group("receiver") else "function"
        symbols.append(_symbol(file_fact.path, match.group("name"), kind, f"({match.group('args').strip()})", match.start(), line_starts))
    for match in GO_TYPE_RE.finditer(source):
        kind = "interface" if match.group("kind") == "interface" else "type"
        symbols.append(_symbol(file_fact.path, match.group("name"), kind, "", match.start(), line_starts))
    return imports, symbols


def _extract_rust(file_fact: FileFact, source: str, line_starts: list[int]) -> tuple[list[ImportFact], list[SymbolFact]]:
    imports = [
        _import(file_fact.path, _clean_module(match.group("module")), [], "rust-use", match.start(), line_starts)
        for match in RUST_IMPORT_RE.finditer(source)
    ]
    imports.extend(
        _import(file_fact.path, match.group("name"), [], "rust-mod", match.start(), line_starts)
        for match in RUST_MOD_RE.finditer(source)
    )
    symbols: list[SymbolFact] = []
    for match in RUST_FN_RE.finditer(source):
        symbols.append(_symbol(file_fact.path, match.group("name"), "function", f"({match.group('args').strip()})", match.start(), line_starts))
    for match in RUST_TYPE_RE.finditer(source):
        symbols.append(_symbol(file_fact.path, match.group("name"), match.group("kind"), "", match.start(), line_starts))
    return imports, symbols


def _extract_csharp(file_fact: FileFact, source: str, line_starts: list[int]) -> tuple[list[ImportFact], list[SymbolFact]]:
    imports = [
        _import(file_fact.path, match.group("module"), [], "csharp-using", match.start(), line_starts)
        for match in CSHARP_USING_RE.finditer(source)
    ]
    symbols: list[SymbolFact] = []
    for match in CSHARP_TYPE_RE.finditer(source):
        symbols.append(_symbol(file_fact.path, match.group("name"), match.group("kind"), "", match.start(), line_starts))
    for match in CSHARP_METHOD_RE.finditer(source):
        symbols.append(_symbol(file_fact.path, match.group("name"), "method", f"({match.group('args').strip()})", match.start(), line_starts))
    return imports, symbols


def _extract_php(file_fact: FileFact, source: str, line_starts: list[int]) -> tuple[list[ImportFact], list[SymbolFact]]:
    imports = [
        _import(file_fact.path, match.group("module"), [], "php-use", match.start(), line_starts)
        for match in PHP_IMPORT_RE.finditer(source)
    ]
    imports.extend(
        _import(file_fact.path, match.group("module"), [], "php-include", match.start(), line_starts)
        for match in PHP_REQUIRE_RE.finditer(source)
    )
    symbols: list[SymbolFact] = []
    for match in PHP_TYPE_RE.finditer(source):
        symbols.append(_symbol(file_fact.path, match.group("name"), match.group("kind"), "", match.start(), line_starts))
    for match in PHP_FUNCTION_RE.finditer(source):
        symbols.append(_symbol(file_fact.path, match.group("name"), "function", f"({match.group('args').strip()})", match.start(), line_starts))
    return imports, symbols


def _extract_ruby(file_fact: FileFact, source: str, line_starts: list[int]) -> tuple[list[ImportFact], list[SymbolFact]]:
    imports = [
        _import(file_fact.path, match.group("module"), [], f"ruby-{match.group('kind')}", match.start(), line_starts)
        for match in RUBY_REQUIRE_RE.finditer(source)
    ]
    symbols: list[SymbolFact] = []
    for match in RUBY_TYPE_RE.finditer(source):
        symbols.append(_symbol(file_fact.path, match.group("name"), match.group("kind"), "", match.start(), line_starts))
    for match in RUBY_DEF_RE.finditer(source):
        symbols.append(_symbol(file_fact.path, match.group("name"), "method", match.group("args").strip(), match.start(), line_starts))
    return imports, symbols


def _extract_kotlin(file_fact: FileFact, source: str, line_starts: list[int]) -> tuple[list[ImportFact], list[SymbolFact]]:
    imports = [
        _import(file_fact.path, match.group("module"), [], "kotlin-import", match.start(), line_starts)
        for match in KOTLIN_IMPORT_RE.finditer(source)
    ]
    symbols: list[SymbolFact] = []
    for match in KOTLIN_TYPE_RE.finditer(source):
        symbols.append(_symbol(file_fact.path, match.group("name"), match.group("kind"), "", match.start(), line_starts))
    for match in KOTLIN_FUN_RE.finditer(source):
        symbols.append(_symbol(file_fact.path, match.group("name"), "function", f"({match.group('args').strip()})", match.start(), line_starts))
    return imports, symbols


def _extract_dart(file_fact: FileFact, source: str, line_starts: list[int]) -> tuple[list[ImportFact], list[SymbolFact]]:
    imports = [
        _import(file_fact.path, match.group("module"), [], f"dart-{match.group('kind')}", match.start(), line_starts)
        for match in DART_IMPORT_RE.finditer(source)
    ]
    symbols: list[SymbolFact] = []
    for match in DART_TYPE_RE.finditer(source):
        symbols.append(_symbol(file_fact.path, match.group("name"), match.group("kind"), "", match.start(), line_starts))
    for match in DART_FUNCTION_RE.finditer(source):
        if match.group("name") in SKIPPED_DART_FUNCTIONS:
            continue
        symbols.append(_symbol(file_fact.path, match.group("name"), "function", f"({match.group('args').strip()})", match.start(), line_starts))
    return imports, symbols


def _extract_elixir(file_fact: FileFact, source: str, line_starts: list[int]) -> tuple[list[ImportFact], list[SymbolFact]]:
    imports = [
        _import(file_fact.path, match.group("module"), [], f"elixir-{match.group('kind')}", match.start(), line_starts)
        for match in ELIXIR_IMPORT_RE.finditer(source)
    ]
    symbols: list[SymbolFact] = []
    for match in ELIXIR_MODULE_RE.finditer(source):
        symbols.append(_symbol(file_fact.path, match.group("name"), "module", "", match.start(), line_starts))
    for match in ELIXIR_DEF_RE.finditer(source):
        signature = match.group("args") or ""
        symbols.append(_symbol(file_fact.path, match.group("name"), "function", signature, match.start(), line_starts))
    return imports, symbols


def _extract_clojure(file_fact: FileFact, source: str, line_starts: list[int]) -> tuple[list[ImportFact], list[SymbolFact]]:
    imports = [
        _import(file_fact.path, match.group("module"), [], "clojure-namespace", match.start(), line_starts)
        for match in CLOJURE_NS_RE.finditer(source)
    ]
    imports.extend(
        _import(file_fact.path, match.group("module"), [], "clojure-require", match.start(), line_starts)
        for match in CLOJURE_REQUIRE_RE.finditer(source)
        if "." in match.group("module")
    )
    symbols = [
        _symbol(file_fact.path, match.group("name"), match.group("kind"), "", match.start(), line_starts)
        for match in CLOJURE_DEF_RE.finditer(source)
    ]
    return imports, symbols


def _extract_scala(file_fact: FileFact, source: str, line_starts: list[int]) -> tuple[list[ImportFact], list[SymbolFact]]:
    imports = [
        _import(file_fact.path, _clean_scala_import(match.group("module")), [], "scala-import", match.start(), line_starts)
        for match in SCALA_IMPORT_RE.finditer(source)
    ]
    symbols: list[SymbolFact] = []
    for match in SCALA_TYPE_RE.finditer(source):
        kind = "case class" if match.group("case") else match.group("kind")
        symbols.append(_symbol(file_fact.path, match.group("name"), kind, "", match.start(), line_starts))
    for match in SCALA_DEF_RE.finditer(source):
        symbols.append(_symbol(file_fact.path, match.group("name"), "method", (match.group("args") or "").strip(), match.start(), line_starts))
    return imports, symbols


def _clean_scala_import(value: str) -> str:
    cleaned = value.strip()
    cleaned = re.sub(r"\s+", "", cleaned)
    return cleaned.rstrip("._")


def _extract_svelte(file_fact: FileFact, source: str, line_starts: list[int]) -> tuple[list[ImportFact], list[SymbolFact]]:
    imports: list[ImportFact] = []
    for script in SVELTE_SCRIPT_RE.finditer(source):
        for match in SVELTE_IMPORT_RE.finditer(script.group("body")):
            offset = script.start("body") + match.start()
            imports.append(_import(file_fact.path, match.group("module"), _parse_import_names(match.group("names")), "svelte-import", offset, line_starts))
    name = _svelte_component_name(file_fact.path)
    return imports, [_symbol(file_fact.path, name, "component", "", 0, line_starts)]


def _import(
    path: str,
    module: str | None,
    names: list[str],
    kind: str,
    offset: int,
    line_starts: list[int],
) -> ImportFact:
    line = _line_for_offset(offset, line_starts)
    return ImportFact(
        path=path,
        module=module,
        names=names,
        kind=kind,
        level=0,
        evidence=Evidence(file=path, kind=kind, line_start=line, line_end=line),
    )


def _symbol(
    path: str,
    name: str,
    kind: str,
    signature: str,
    offset: int,
    line_starts: list[int],
) -> SymbolFact:
    line = _line_for_offset(offset, line_starts)
    return SymbolFact(
        path=path,
        name=name,
        qualname=name,
        kind=kind,
        parent=None,
        line_start=line,
        line_end=line,
        signature=signature,
        decorators=[],
        docstring=None,
        evidence=Evidence(file=path, kind="polyglot-symbol", line_start=line, line_end=line),
    )


def _line_starts(source: str) -> list[int]:
    starts = [0]
    starts.extend(index + 1 for index, char in enumerate(source) if char == "\n")
    return starts


def _line_for_offset(offset: int, line_starts: list[int]) -> int:
    return max(1, bisect_right(line_starts, offset))


def _clean_module(module: str) -> str:
    return " ".join(module.strip().split())


def _parse_import_names(raw: str) -> list[str]:
    cleaned = raw.strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        cleaned = cleaned[1:-1]
    if cleaned.startswith("* as "):
        return [cleaned.removeprefix("* as ").strip()]
    if "," not in cleaned and "{" not in cleaned:
        return [cleaned.strip()]
    return [
        item.strip().split(" as ")[0].strip()
        for item in cleaned.replace("{", "").replace("}", "").split(",")
        if item.strip()
    ]


def _svelte_component_name(path: str) -> str:
    normalized = path.replace("\\", "/")
    stem = Path(normalized).stem
    if not stem.startswith("+"):
        return _pascal_case(stem) or "SvelteComponent"
    parent = Path(normalized).parent.name
    suffix = {
        "+page": "Page",
        "+layout": "Layout",
        "+error": "Error",
    }.get(stem, "Component")
    return f"{_pascal_case(parent) or 'Route'}{suffix}"


def _pascal_case(value: str) -> str:
    words = re.split(r"[^A-Za-z0-9]+", value)
    return "".join(word[:1].upper() + word[1:] for word in words if word)


def _dedupe_imports(imports: list[ImportFact]) -> list[ImportFact]:
    seen: set[tuple[str, str | None, tuple[str, ...], str, int | None]] = set()
    result: list[ImportFact] = []
    for item in imports:
        key = (item.path, item.module, tuple(item.names), item.kind, item.evidence.line_start)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _dedupe_symbols(symbols: list[SymbolFact]) -> list[SymbolFact]:
    seen: set[tuple[str, str, str, int]] = set()
    result: list[SymbolFact] = []
    for item in symbols:
        key = (item.path, item.name, item.kind, item.line_start)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return sorted(result, key=lambda item: (item.path, item.line_start, item.name))
