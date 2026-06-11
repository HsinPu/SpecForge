from __future__ import annotations

from pathlib import Path


def create_project(root: Path, name: str = "project") -> Path:
    project = root / name
    project.mkdir()
    write_file(project, "README.md", "# Demo\n")
    return project


def write_file(root: Path, relative_path: str, content: str) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
