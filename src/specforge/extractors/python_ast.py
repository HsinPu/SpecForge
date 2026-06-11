from __future__ import annotations

import ast
from pathlib import Path

from specforge.models import CommandFact, Evidence, ExtractionIssue, FileFact, ImportFact, SymbolFact


def extract_python_facts(
    root: Path,
    files: list[FileFact],
) -> tuple[list[ImportFact], list[SymbolFact], list[CommandFact], list[ExtractionIssue]]:
    imports: list[ImportFact] = []
    symbols: list[SymbolFact] = []
    commands: list[CommandFact] = []
    issues: list[ExtractionIssue] = []

    for file_fact in files:
        if file_fact.language != "python":
            continue
        path = root / file_fact.path
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=file_fact.path)
        except (OSError, SyntaxError, UnicodeDecodeError) as error:
            issues.append(
                ExtractionIssue(
                    path=file_fact.path,
                    extractor="python-ast",
                    message=str(error),
                    evidence=Evidence(file=file_fact.path, kind="python-ast"),
                )
            )
            continue

        imports.extend(_extract_imports(file_fact.path, tree))
        symbols.extend(_extract_symbols(file_fact.path, tree))
        commands.extend(_extract_commands(file_fact.path, tree))

    return imports, symbols, commands, issues


def _extract_imports(path: str, tree: ast.AST) -> list[ImportFact]:
    imports: list[ImportFact] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.append(
                ImportFact(
                    path=path,
                    module=None,
                    names=[alias.name for alias in node.names],
                    kind="import",
                    level=0,
                    evidence=Evidence(
                        file=path,
                        kind="python-import",
                        line_start=node.lineno,
                        line_end=getattr(node, "end_lineno", node.lineno),
                    ),
                )
            )
        elif isinstance(node, ast.ImportFrom):
            imports.append(
                ImportFact(
                    path=path,
                    module=node.module,
                    names=[alias.name for alias in node.names],
                    kind="from-import",
                    level=node.level,
                    evidence=Evidence(
                        file=path,
                        kind="python-import",
                        line_start=node.lineno,
                        line_end=getattr(node, "end_lineno", node.lineno),
                    ),
                )
            )
    return imports


def _extract_symbols(path: str, tree: ast.AST) -> list[SymbolFact]:
    visitor = _SymbolVisitor(path)
    visitor.visit(tree)
    return visitor.symbols


def _extract_commands(path: str, tree: ast.AST) -> list[CommandFact]:
    visitor = _CommandVisitor(path)
    visitor.visit(tree)
    return visitor.commands()


class _SymbolVisitor(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.stack: list[str] = []
        self.symbols: list[SymbolFact] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._record(node, "class")
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._record(node, "method" if self.stack else "function")
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._record(node, "async-method" if self.stack else "async-function")
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def _record(
        self,
        node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
        kind: str,
    ) -> None:
        parent = ".".join(self.stack) if self.stack else None
        qualname = ".".join([*self.stack, node.name]) if self.stack else node.name
        self.symbols.append(
            SymbolFact(
                path=self.path,
                name=node.name,
                qualname=qualname,
                kind=kind,
                parent=parent,
                line_start=node.lineno,
                line_end=getattr(node, "end_lineno", None),
                signature=_signature(node) if not isinstance(node, ast.ClassDef) else "",
                decorators=[_decorator_name(item) for item in node.decorator_list],
                docstring=_summary(ast.get_docstring(node)),
                evidence=Evidence(
                    file=self.path,
                    kind="python-symbol",
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", node.lineno),
                ),
            )
        )


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    parts: list[str] = []
    args = list(node.args.posonlyargs) + list(node.args.args)
    defaults_offset = len(args) - len(node.args.defaults)
    for index, arg in enumerate(args):
        value = arg.arg
        if arg.annotation is not None:
            value += f": {_unparse(arg.annotation)}"
        if index >= defaults_offset and node.args.defaults:
            default = node.args.defaults[index - defaults_offset]
            value += f" = {_unparse(default)}"
        parts.append(value)

    if node.args.vararg is not None:
        parts.append(f"*{node.args.vararg.arg}")
    elif node.args.kwonlyargs:
        parts.append("*")

    for index, arg in enumerate(node.args.kwonlyargs):
        value = arg.arg
        if arg.annotation is not None:
            value += f": {_unparse(arg.annotation)}"
        default = node.args.kw_defaults[index]
        if default is not None:
            value += f" = {_unparse(default)}"
        parts.append(value)

    if node.args.kwarg is not None:
        parts.append(f"**{node.args.kwarg.arg}")

    result = f"({', '.join(parts)})"
    if node.returns is not None:
        result += f" -> {_unparse(node.returns)}"
    return result


def _decorator_name(node: ast.AST) -> str:
    return _unparse(node)


def _unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return node.__class__.__name__


def _summary(docstring: str | None) -> str | None:
    if not docstring:
        return None
    first_line = docstring.strip().splitlines()[0].strip()
    return first_line or None


class _CommandVisitor(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self._commands_by_var: dict[str, dict[str, object]] = {}

    def visit_Assign(self, node: ast.Assign) -> None:
        if isinstance(node.value, ast.Call) and _is_method_call(node.value, "add_parser"):
            name = _first_string_arg(node.value)
            if name:
                description = _keyword_string(node.value, "help") or _keyword_string(node.value, "description")
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self._commands_by_var[target.id] = {
                            "name": name,
                            "description": description,
                            "arguments": [],
                            "options": [],
                            "line": node.lineno,
                            "end_line": getattr(node, "end_lineno", node.lineno),
                        }
        self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr) -> None:
        if isinstance(node.value, ast.Call):
            self._record_add_argument(node.value)
        self.generic_visit(node)

    def _record_add_argument(self, call: ast.Call) -> None:
        if not _is_method_call(call, "add_argument"):
            return
        receiver = call.func.value
        if not isinstance(receiver, ast.Name):
            return
        command = self._commands_by_var.get(receiver.id)
        if command is None:
            return
        names = _string_args(call)
        if not names:
            return
        bucket = "options" if any(name.startswith("-") for name in names) else "arguments"
        command[bucket].extend(names)  # type: ignore[index, union-attr]

    def commands(self) -> list[CommandFact]:
        result: list[CommandFact] = []
        for command in self._commands_by_var.values():
            name = str(command["name"])
            line = int(command["line"])
            result.append(
                CommandFact(
                    path=self.path,
                    name=name,
                    description=command.get("description"),  # type: ignore[arg-type]
                    arguments=list(dict.fromkeys(command["arguments"])),  # type: ignore[arg-type]
                    options=list(dict.fromkeys(command["options"])),  # type: ignore[arg-type]
                    evidence=Evidence(
                        file=self.path,
                        kind="python-cli-command",
                        line_start=line,
                        line_end=int(command["end_line"]),
                    ),
                )
            )
        return sorted(result, key=lambda item: item.name)


def _is_method_call(call: ast.Call, method_name: str) -> bool:
    return isinstance(call.func, ast.Attribute) and call.func.attr == method_name


def _first_string_arg(call: ast.Call) -> str | None:
    args = _string_args(call)
    return args[0] if args else None


def _string_args(call: ast.Call) -> list[str]:
    values: list[str] = []
    for arg in call.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            values.append(arg.value)
    return values


def _keyword_string(call: ast.Call, name: str) -> str | None:
    for keyword in call.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant):
            if isinstance(keyword.value.value, str):
                return keyword.value.value
    return None
