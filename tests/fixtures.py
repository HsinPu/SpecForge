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


def create_v2_linked_project(root: Path) -> Path:
    project = create_project(root)
    write_file(
        project,
        "package.json",
        '{"dependencies":{"express":"^4.0.0","react":"^18.0.0"}}\n',
    )
    write_file(
        project,
        "src/server.ts",
        """
import express from 'express';
const app = express();

app.get('/api/users/:id', getUser);
""".strip()
        + "\n",
    )
    write_file(
        project,
        "src/UserCard.tsx",
        """
export function UserCard() {
  fetch('/api/users/123');
  return <div />;
}
""".strip()
        + "\n",
    )
    write_file(project, "tests/UserCard.test.tsx", "import { UserCard } from '../src/UserCard';\n")
    return project
