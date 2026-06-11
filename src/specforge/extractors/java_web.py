from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from specforge.models import (
    DataModelFact,
    Evidence,
    FileFact,
    JavaWebSurfaceFact,
    JspPageFact,
    RepositoryFact,
    ServiceFact,
    ServletFact,
)


JAVA_TYPE_RE = re.compile(
    r"\b(?:(?:public|protected|private|abstract|final|static)\s+)*"
    r"(?P<kind>class|interface|enum)\s+"
    r"(?P<name>[A-Za-z_]\w*)"
    r"(?P<rest>[^{;]*)",
    re.MULTILINE,
)
JAVA_FIELD_RE = re.compile(
    r"^\s*(?:private|protected|public)\s+"
    r"(?:(?:static|final|transient|volatile)\s+)*"
    r"(?P<type>[\w<>, ?\[\].]+)\s+"
    r"(?P<name>[A-Za-z_]\w*)\s*(?:=|;)",
    re.MULTILINE,
)
JAVA_METHOD_RE = re.compile(
    r"\b(?:public|protected|private)\s+"
    r"(?:(?:static|final|synchronized)\s+)*"
    r"[\w<>, ?\[\].]+\s+"
    r"(?P<name>[A-Za-z_]\w*)\s*\(",
    re.MULTILINE,
)
REPOSITORY_EXTENDS_RE = re.compile(
    r"\binterface\s+(?P<name>[A-Za-z_]\w*)\s+extends\s+"
    r"(?P<base>[\w.]*Repository|CrudRepository|JpaRepository|PagingAndSortingRepository)"
    r"\s*<\s*(?P<entity>[\w.]+)",
    re.MULTILINE,
)
WEB_SERVLET_RE = re.compile(r"@WebServlet(?:\s*\((?P<args>.*?)\))?", re.DOTALL)
QUOTED_PATH_RE = re.compile(r"""["'](?P<path>/[^"']*)["']""")
ANNOTATION_NAME_RE = re.compile(r"@(?P<name>[A-Za-z_]\w*)")
JSP_FORM_RE = re.compile(r"<form\b[^>]*\saction\s*=\s*['\"](?P<value>[^'\"]+)['\"]", re.IGNORECASE)
JSP_LINK_RE = re.compile(r"<a\b[^>]*\shref\s*=\s*['\"](?P<value>[^'\"]+)['\"]", re.IGNORECASE)
JSP_INCLUDE_RE = re.compile(
    r"(?:<%@\s*include\b[^>]*\sfile|<jsp:include\b[^>]*\spage|"
    r"<script\b[^>]*\ssrc|<link\b[^>]*\shref)"
    r"\s*=\s*['\"](?P<value>[^'\"]+)['\"]",
    re.IGNORECASE,
)


def extract_java_web_facts(
    root: Path,
    files: list[FileFact],
) -> tuple[
    list[JavaWebSurfaceFact],
    list[ServletFact],
    list[JspPageFact],
    list[DataModelFact],
    list[RepositoryFact],
    list[ServiceFact],
]:
    spring_controller_count = 0
    servlets: list[ServletFact] = []
    jsp_pages: list[JspPageFact] = []
    data_models: list[DataModelFact] = []
    repositories: list[RepositoryFact] = []
    services: list[ServiceFact] = []

    for file_fact in files:
        if file_fact.role == "test":
            continue
        normalized = file_fact.path.replace("\\", "/")
        if file_fact.language == "java":
            source = _read(root, file_fact)
            spring_controller_count += _count_spring_controllers(source)
            servlets.extend(_extract_web_servlet_annotations(file_fact, source))
            data_models.extend(_extract_data_models(file_fact, source))
            repositories.extend(_extract_repositories(file_fact, source))
            services.extend(_extract_services(file_fact, source))
        elif file_fact.language == "xml" and normalized.endswith("WEB-INF/web.xml"):
            servlets.extend(_extract_web_xml_servlets(root, file_fact))
        elif file_fact.language == "jsp":
            jsp_pages.append(_extract_jsp_page(root, file_fact))

    evidence = [
        *(item.evidence for item in servlets[:3]),
        *(item.evidence for item in jsp_pages[:3]),
        *(item.evidence for item in data_models[:3]),
        *(item.evidence for item in repositories[:3]),
        *(item.evidence for item in services[:3]),
    ]
    if (
        spring_controller_count
        or servlets
        or jsp_pages
        or data_models
        or repositories
        or services
    ):
        surfaces = [
            JavaWebSurfaceFact(
                spring_controller_count=spring_controller_count,
                servlet_count=len(servlets),
                jsp_page_count=len(jsp_pages),
                data_model_count=len(data_models),
                repository_count=len(repositories),
                service_count=len(services),
                evidence=evidence,
            )
        ]
    else:
        surfaces = []

    return surfaces, servlets, jsp_pages, data_models, repositories, services


def _extract_web_servlet_annotations(file_fact: FileFact, source: str) -> list[ServletFact]:
    facts: list[ServletFact] = []
    for match in WEB_SERVLET_RE.finditer(source):
        args = match.group("args") or ""
        paths = _dedupe(item.group("path") for item in QUOTED_PATH_RE.finditer(args))
        if not paths:
            continue
        class_match = re.search(r"\bclass\s+([A-Za-z_]\w*)", source[match.end() : match.end() + 500])
        class_name = class_match.group(1) if class_match else None
        name_match = re.search(r"\bname\s*=\s*['\"]([^'\"]+)['\"]", args)
        name = name_match.group(1) if name_match else class_name or Path(file_fact.path).stem
        line = _line_for_offset(source, match.start())
        facts.append(
            ServletFact(
                name=name,
                class_name=class_name,
                url_patterns=paths,
                source="@WebServlet",
                evidence=Evidence(file=file_fact.path, kind="servlet", line_start=line, line_end=line),
            )
        )
    return facts


def _extract_web_xml_servlets(root: Path, file_fact: FileFact) -> list[ServletFact]:
    path = root / file_fact.path
    source = path.read_text(encoding="utf-8")
    try:
        document = ET.fromstring(source)
    except ET.ParseError:
        return []
    namespace = _namespace(document.tag)
    classes_by_name: dict[str, str | None] = {}
    for servlet in document.findall(f".//{namespace}servlet"):
        name = _find_text(servlet, namespace, "servlet-name")
        class_name = _find_text(servlet, namespace, "servlet-class")
        if name:
            classes_by_name[name] = class_name

    patterns_by_name: dict[str, list[str]] = {}
    for mapping in document.findall(f".//{namespace}servlet-mapping"):
        name = _find_text(mapping, namespace, "servlet-name")
        patterns = [
            item.text.strip()
            for item in mapping.findall(f"{namespace}url-pattern")
            if item.text and item.text.strip()
        ]
        if name and patterns:
            patterns_by_name.setdefault(name, []).extend(patterns)

    facts: list[ServletFact] = []
    for name, patterns in sorted(patterns_by_name.items()):
        line = _line_for_text(source, patterns[0])
        facts.append(
            ServletFact(
                name=name,
                class_name=classes_by_name.get(name),
                url_patterns=_dedupe(patterns),
                source="web.xml",
                evidence=Evidence(file=file_fact.path, kind="servlet", line_start=line, line_end=line),
            )
        )
    return facts


def _extract_jsp_page(root: Path, file_fact: FileFact) -> JspPageFact:
    source = _read(root, file_fact)
    return JspPageFact(
        path=file_fact.path,
        route=_jsp_route(file_fact.path),
        form_actions=_dedupe(match.group("value") for match in JSP_FORM_RE.finditer(source)),
        links=_dedupe(match.group("value") for match in JSP_LINK_RE.finditer(source)),
        includes=_dedupe(match.group("value") for match in JSP_INCLUDE_RE.finditer(source)),
        uses_jstl="<%@ taglib" in source or "<c:" in source or "</c:" in source,
        uses_el="${" in source,
        evidence=Evidence(file=file_fact.path, kind="jsp-page", line_start=1, line_end=1),
    )


def _extract_data_models(file_fact: FileFact, source: str) -> list[DataModelFact]:
    facts: list[DataModelFact] = []
    fields = [f"{match.group('type').strip()} {match.group('name')}" for match in JAVA_FIELD_RE.finditer(source)]
    annotations = _dedupe(match.group("name") for match in ANNOTATION_NAME_RE.finditer(source))
    for match in JAVA_TYPE_RE.finditer(source):
        name = match.group("name")
        block = _annotation_block_before(source, match.start())
        kind = _data_model_kind(name, block, annotations)
        if kind is None:
            continue
        line = _line_for_offset(source, match.start())
        facts.append(
            DataModelFact(
                name=name,
                path=file_fact.path,
                kind=kind,
                fields=fields,
                annotations=annotations,
                evidence=Evidence(file=file_fact.path, kind="data-model", line_start=line, line_end=line),
            )
        )
    return facts


def _extract_repositories(file_fact: FileFact, source: str) -> list[RepositoryFact]:
    facts: list[RepositoryFact] = []
    seen: set[str] = set()
    for match in REPOSITORY_EXTENDS_RE.finditer(source):
        name = match.group("name")
        seen.add(name)
        line = _line_for_offset(source, match.start())
        facts.append(
            RepositoryFact(
                name=name,
                path=file_fact.path,
                entity=match.group("entity").split(".")[-1],
                base_interface=match.group("base").split(".")[-1],
                evidence=Evidence(file=file_fact.path, kind="repository", line_start=line, line_end=line),
            )
        )

    for match in JAVA_TYPE_RE.finditer(source):
        name = match.group("name")
        if name in seen or not name.endswith("Repository"):
            continue
        line = _line_for_offset(source, match.start())
        facts.append(
            RepositoryFact(
                name=name,
                path=file_fact.path,
                entity=None,
                base_interface=None,
                evidence=Evidence(file=file_fact.path, kind="repository", line_start=line, line_end=line),
            )
        )
    return facts


def _extract_services(file_fact: FileFact, source: str) -> list[ServiceFact]:
    facts: list[ServiceFact] = []
    methods = _dedupe(match.group("name") for match in JAVA_METHOD_RE.finditer(source))
    for match in JAVA_TYPE_RE.finditer(source):
        name = match.group("name")
        block = _annotation_block_before(source, match.start())
        if "@Service" not in block and not name.endswith("Service"):
            continue
        line = _line_for_offset(source, match.start())
        facts.append(
            ServiceFact(
                name=name,
                path=file_fact.path,
                methods=methods,
                evidence=Evidence(file=file_fact.path, kind="service", line_start=line, line_end=line),
            )
        )
    return facts


def _count_spring_controllers(source: str) -> int:
    count = 0
    for match in JAVA_TYPE_RE.finditer(source):
        block = _annotation_block_before(source, match.start())
        if "@RestController" in block or "@Controller" in block:
            count += 1
    return count


def _data_model_kind(name: str, annotation_block: str, annotations: list[str]) -> str | None:
    if "@Entity" in annotation_block or name.endswith("Entity"):
        return "entity"
    if name.endswith(("DTO", "Dto", "Request", "Response")):
        return "dto"
    if name.endswith("Model"):
        return "model"
    if {"Table", "Column", "Id"} & set(annotations):
        return "model"
    return None


def _annotation_block_before(source: str, offset: int) -> str:
    prefix = source[max(0, offset - 800) : offset]
    lines = prefix.splitlines()
    collected: list[str] = []
    for line in reversed(lines):
        stripped = line.strip()
        if not stripped:
            if collected:
                break
            continue
        if stripped.startswith("@"):
            collected.append(stripped)
            continue
        if collected and (stripped.endswith(")") or stripped.endswith("}")):
            collected.append(stripped)
            continue
        break
    return "\n".join(reversed(collected))


def _jsp_route(path: str) -> str:
    normalized = path.replace("\\", "/")
    for prefix in ("src/main/webapp/", "webapp/"):
        if normalized.startswith(prefix):
            normalized = normalized.removeprefix(prefix)
            break
    if normalized == "index.jsp":
        return "/"
    return "/" + normalized.lstrip("/")


def _namespace(tag: str) -> str:
    match = re.match(r"\{.*\}", tag)
    return match.group(0) if match else ""


def _find_text(element: ET.Element, namespace: str, name: str) -> str | None:
    value = element.findtext(f"{namespace}{name}")
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _read(root: Path, file_fact: FileFact) -> str:
    return (root / file_fact.path).read_text(encoding="utf-8")


def _line_for_offset(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _line_for_text(source: str, text: str) -> int:
    index = source.find(text)
    return _line_for_offset(source, index) if index >= 0 else 1


def _dedupe(values: object) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(str(value))
    return result
