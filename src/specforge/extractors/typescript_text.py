from __future__ import annotations

import re
from pathlib import Path

from specforge.models import CommandFact, Evidence, ExtractionIssue, FileFact, ImportFact, SymbolFact


IMPORT_FROM_RE = re.compile(
    r"^\s*import\s+(?P<names>.+?)\s+from\s+['\"](?P<module>[^'\"]+)['\"]",
    re.MULTILINE,
)
IMPORT_SIDE_EFFECT_RE = re.compile(
    r"^\s*import\s+['\"](?P<module>[^'\"]+)['\"]",
    re.MULTILINE,
)
CLASS_RE = re.compile(r"\b(?:export\s+)?(?:abstract\s+)?class\s+(?P<name>[A-Za-z_$][\w$]*)")
INTERFACE_RE = re.compile(r"\b(?:export\s+)?interface\s+(?P<name>[A-Za-z_$][\w$]*)")
TYPE_RE = re.compile(r"\b(?:export\s+)?type\s+(?P<name>[A-Za-z_$][\w$]*)\s*=")
FUNCTION_RE = re.compile(
    r"\b(?:export\s+)?(?:async\s+)?function\s+(?P<name>[A-Za-z_$][\w$]*)\s*"
    r"\((?P<args>[^)]*)\)\s*(?::\s*(?P<returns>[^{;]+))?",
    re.MULTILINE,
)
CONST_FUNCTION_RE = re.compile(
    r"\b(?:export\s+)?const\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*"
    r"(?:async\s*)?(?:\((?P<args>[^)]*)\)|(?P<single_arg>[A-Za-z_$][\w$]*))\s*"
    r"(?::\s*(?P<returns>[^=]+?))?\s*=>",
    re.MULTILINE,
)
COMMAND_RE = re.compile(r"\.command\(\s*['\"](?P<command>[^'\"]+)['\"]", re.MULTILINE)
DESCRIPTION_RE = re.compile(r"\.description\(\s*['\"](?P<description>[^'\"]+)['\"]", re.DOTALL)
OPTION_RE = re.compile(r"\.option\(\s*['\"](?P<option>[^'\"]+)['\"]", re.DOTALL)


def extract_typescript_facts(
    root: Path,
    files: list[FileFact],
) -> tuple[list[ImportFact], list[SymbolFact], list[CommandFact], list[ExtractionIssue]]:
    imports: list[ImportFact] = []
    symbols: list[SymbolFact] = []
    commands: list[CommandFact] = []
    issues: list[ExtractionIssue] = []

    for file_fact in files:
        if file_fact.role in {"generated", "sample"}:
            continue
        if file_fact.language not in {"typescript", "javascript"}:
            continue
        path = root / file_fact.path
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            issues.append(
                ExtractionIssue(
                    path=file_fact.path,
                    extractor="typescript-text",
                    message=str(error),
                    evidence=Evidence(file=file_fact.path, kind="typescript-text"),
                )
            )
            continue

        line_starts = _line_starts(source)
        imports.extend(_extract_imports(file_fact.path, source, line_starts))
        symbols.extend(_extract_symbols(file_fact.path, source, line_starts))
        commands.extend(_extract_commands(file_fact.path, source, line_starts))

    return imports, symbols, commands, issues


def _extract_imports(path: str, source: str, line_starts: list[int]) -> list[ImportFact]:
    imports: list[ImportFact] = []
    for match in IMPORT_FROM_RE.finditer(source):
        imports.append(
            ImportFact(
                path=path,
                module=match.group("module"),
                names=_parse_import_names(match.group("names")),
                kind="from-import",
                level=0,
                evidence=_evidence(path, "typescript-import", match, line_starts),
            )
        )
    for match in IMPORT_SIDE_EFFECT_RE.finditer(source):
        imports.append(
            ImportFact(
                path=path,
                module=match.group("module"),
                names=[],
                kind="side-effect-import",
                level=0,
                evidence=_evidence(path, "typescript-import", match, line_starts),
            )
        )
    return imports


def _extract_symbols(path: str, source: str, line_starts: list[int]) -> list[SymbolFact]:
    symbols: list[SymbolFact] = []
    patterns = [
        (CLASS_RE, "class"),
        (INTERFACE_RE, "interface"),
        (TYPE_RE, "type"),
        (FUNCTION_RE, "function"),
        (CONST_FUNCTION_RE, "function"),
    ]
    for pattern, kind in patterns:
        for match in pattern.finditer(source):
            signature = ""
            if kind == "function":
                args = match.groupdict().get("args") or match.groupdict().get("single_arg") or ""
                returns = (match.groupdict().get("returns") or "").strip()
                signature = f"({args.strip()})"
                if returns:
                    signature += f" -> {returns}"
            line = _line_for_offset(match.start(), line_starts)
            symbols.append(
                SymbolFact(
                    path=path,
                    name=match.group("name"),
                    qualname=match.group("name"),
                    kind=kind,
                    parent=None,
                    line_start=line,
                    line_end=line,
                    signature=signature,
                    decorators=[],
                    docstring=None,
                    evidence=Evidence(
                        file=path,
                        kind="typescript-symbol",
                        line_start=line,
                        line_end=line,
                    ),
                )
            )
    return sorted(symbols, key=lambda item: (item.path, item.line_start, item.name))


def _extract_commands(path: str, source: str, line_starts: list[int]) -> list[CommandFact]:
    commands: list[CommandFact] = []
    for match in COMMAND_RE.finditer(source):
        block = _statement_block(source, match.start())
        declaration = match.group("command")
        name = declaration.split()[0]
        arguments = _arguments_from_command_declaration(declaration)
        options = [item.group("option").split(",")[0].strip() for item in OPTION_RE.finditer(block)]
        description_match = DESCRIPTION_RE.search(block)
        line = _line_for_offset(match.start(), line_starts)
        commands.append(
            CommandFact(
                path=path,
                name=name,
                description=description_match.group("description") if description_match else None,
                arguments=arguments,
                options=list(dict.fromkeys(options)),
                evidence=Evidence(
                    file=path,
                    kind="typescript-cli-command",
                    line_start=line,
                    line_end=_line_for_offset(match.end(), line_starts),
                ),
            )
        )
    return commands


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


def _arguments_from_command_declaration(declaration: str) -> list[str]:
    return [
        token.strip("[]<>")
        for token in declaration.split()[1:]
        if token.startswith("[") or token.startswith("<")
    ]


def _statement_block(source: str, start: int) -> str:
    end = source.find(";", start)
    if end == -1:
        end = source.find("\n\n", start)
    if end == -1:
        end = min(len(source), start + 1200)
    return source[start:end]


def _line_starts(source: str) -> list[int]:
    starts = [0]
    starts.extend(index + 1 for index, char in enumerate(source) if char == "\n")
    return starts


def _line_for_offset(offset: int, line_starts: list[int]) -> int:
    line = 1
    for index, start in enumerate(line_starts, start=1):
        if start > offset:
            break
        line = index
    return line


def _evidence(path: str, kind: str, match: re.Match[str], line_starts: list[int]) -> Evidence:
    return Evidence(
        file=path,
        kind=kind,
        line_start=_line_for_offset(match.start(), line_starts),
        line_end=_line_for_offset(match.end(), line_starts),
    )
