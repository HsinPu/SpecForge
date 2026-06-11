from __future__ import annotations

from pathlib import Path

from specforge.models import DependencyFact, Evidence, FileFact, FrameworkFact, ImportFact


FRONTEND_FRAMEWORKS = {
    "bootstrap",
    "css-modules",
    "ejs",
    "freemarker",
    "handlebars",
    "html",
    "jsp",
    "mustache",
    "next",
    "pug",
    "pinia",
    "react",
    "react-router",
    "redux",
    "sass",
    "static-site",
    "tailwind",
    "thymeleaf",
    "vite",
    "vue",
    "vue-router",
    "zustand",
}
BACKEND_FRAMEWORKS = {"express", "fastapi", "flask", "java-web", "servlet", "spring"}


def detect_frameworks(
    root: Path,
    files: list[FileFact],
    dependencies: list[DependencyFact],
    imports: list[ImportFact],
) -> list[FrameworkFact]:
    detected: dict[tuple[str, str], FrameworkFact] = {}

    for dependency in dependencies:
        name = dependency.name.lower()
        candidates = [
            ("react", "frontend", name == "react" or name.startswith("react@")),
            ("next", "frontend", name == "next" or name.startswith("next@")),
            ("vue", "frontend", name == "vue" or name.startswith("vue@")),
            ("vite", "frontend", name == "vite" or name.startswith("vite@")),
            ("react-router", "frontend", "react-router" in name),
            ("vue-router", "frontend", name == "vue-router"),
            ("redux", "frontend", name in {"redux", "react-redux", "@reduxjs/toolkit"} or "redux" in name),
            ("zustand", "frontend", name == "zustand"),
            ("pinia", "frontend", name == "pinia"),
            ("tailwind", "frontend", name == "tailwindcss" or "tailwind" in name),
            ("bootstrap", "frontend", name == "bootstrap" or name.startswith("bootstrap@")),
            ("sass", "frontend", name in {"sass", "node-sass"} or name.startswith("sass@")),
            ("handlebars", "frontend", name in {"handlebars", "hbs", "express-handlebars"}),
            ("mustache", "frontend", name == "mustache"),
            ("ejs", "frontend", name == "ejs"),
            ("pug", "frontend", name == "pug"),
            ("thymeleaf", "frontend", "thymeleaf" in name),
            ("freemarker", "frontend", "freemarker" in name),
            ("express", "backend", name == "express" or name.startswith("express@")),
            ("fastapi", "backend", name == "fastapi" or name.startswith("fastapi")),
            ("flask", "backend", name == "flask" or name.startswith("flask")),
            ("spring", "backend", "spring-boot" in name or "springframework" in name),
            ("servlet", "backend", "servlet-api" in name or "jakarta.servlet" in name or "javax.servlet" in name),
            ("java-web", "backend", "servlet-api" in name or "jakarta.servlet" in name or "javax.servlet" in name),
            ("jsp", "frontend", "jsp-api" in name or "jakarta.servlet.jsp" in name or "javax.servlet.jsp" in name),
        ]
        for framework, category, matched in candidates:
            if matched:
                _add(
                    detected,
                    framework,
                    category,
                    "dependency",
                    1.0,
                    dependency.evidence,
                )

    for file_fact in files:
        path = file_fact.path.replace("\\", "/")
        name = Path(path).name
        lower = path.lower()
        config_matches = [
            ("next", "frontend", name.startswith("next.config")),
            ("vite", "frontend", name.startswith("vite.config")),
            ("tailwind", "frontend", name.startswith("tailwind.config")),
            ("sass", "frontend", lower.endswith((".scss", ".sass"))),
            ("css-modules", "frontend", ".module." in name and lower.endswith((".css", ".scss", ".sass"))),
            ("spring", "backend", name in {"application.properties", "application.yml", "application.yaml"}),
            ("java-web", "backend", lower.endswith("web-inf/web.xml")),
            ("servlet", "backend", lower.endswith("web-inf/web.xml")),
        ]
        path_matches = [
            ("next", "frontend", lower.startswith("pages/") or lower.startswith("app/")),
            ("vue", "frontend", lower.endswith(".vue")),
            ("react", "frontend", lower.endswith(".tsx") or lower.endswith(".jsx")),
            ("static-site", "frontend", lower.endswith((".html", ".htm")) or lower.startswith(("public/", "static/"))),
            ("html", "frontend", lower.endswith((".html", ".htm"))),
            ("freemarker", "frontend", lower.endswith(".ftl")),
            ("handlebars", "frontend", lower.endswith((".hbs", ".handlebars"))),
            ("mustache", "frontend", lower.endswith(".mustache")),
            ("ejs", "frontend", lower.endswith(".ejs")),
            ("pug", "frontend", lower.endswith(".pug")),
            ("spring", "backend", "/src/main/java/" in f"/{lower}"),
            ("java-web", "backend", "/src/main/webapp/" in f"/{lower}"),
            ("jsp", "frontend", lower.endswith(".jsp")),
        ]
        for framework, category, matched in [*config_matches, *path_matches]:
            if matched:
                _add(detected, framework, category, "path", 0.75, file_fact.evidence)
        if lower.endswith((".html", ".htm")):
            source = (root / file_fact.path).read_text(encoding="utf-8")
            if "th:" in source or "xmlns:th=" in source:
                _add(detected, "thymeleaf", "frontend", "template", 0.9, file_fact.evidence)
            if "bootstrap" in source.lower():
                _add(detected, "bootstrap", "frontend", "template", 0.75, file_fact.evidence)
            if "tailwind" in source.lower():
                _add(detected, "tailwind", "frontend", "template", 0.75, file_fact.evidence)

    pom_path = root / "pom.xml"
    if pom_path.exists() and "<packaging>war</packaging>" in pom_path.read_text(encoding="utf-8"):
        _add(
            detected,
            "java-web",
            "backend",
            "packaging",
            0.85,
            Evidence(file="pom.xml", kind="framework", note="Maven packaging is war"),
        )

    for import_fact in imports:
        module = (import_fact.module or "").lower()
        if module.startswith("react"):
            _add(detected, "react", "frontend", "import", 0.85, import_fact.evidence)
        if module.startswith("next"):
            _add(detected, "next", "frontend", "import", 0.85, import_fact.evidence)
        if module.startswith("vue"):
            _add(detected, "vue", "frontend", "import", 0.85, import_fact.evidence)
        if module.startswith("react-router"):
            _add(detected, "react-router", "frontend", "import", 0.85, import_fact.evidence)
        if module == "vue-router":
            _add(detected, "vue-router", "frontend", "import", 0.85, import_fact.evidence)
        if module in {"redux", "react-redux", "@reduxjs/toolkit"} or module.startswith("@reduxjs"):
            _add(detected, "redux", "frontend", "import", 0.85, import_fact.evidence)
        if module == "zustand":
            _add(detected, "zustand", "frontend", "import", 0.85, import_fact.evidence)
        if module == "pinia":
            _add(detected, "pinia", "frontend", "import", 0.85, import_fact.evidence)
        if module == "express":
            _add(detected, "express", "backend", "import", 0.85, import_fact.evidence)
        if module == "fastapi":
            _add(detected, "fastapi", "backend", "import", 0.85, import_fact.evidence)
        if module == "flask":
            _add(detected, "flask", "backend", "import", 0.85, import_fact.evidence)

    return sorted(detected.values(), key=lambda item: (item.category, item.name, item.source))


def _add(
    detected: dict[tuple[str, str], FrameworkFact],
    name: str,
    category: str,
    source: str,
    confidence: float,
    evidence: Evidence,
) -> None:
    key = (category, name)
    current = detected.get(key)
    if current is None or confidence > current.confidence:
        detected[key] = FrameworkFact(
            name=name,
            category=category,
            source=source,
            confidence=confidence,
            evidence=evidence,
        )
