from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge import writers as writer_facade
from specforge.cli import main
from specforge.renderers import write_fact_bundle, write_spec_bundle

from fixtures import create_project, write_file


class ScannerTests(unittest.TestCase):

    def test_writer_facade_reexports_renderer_entrypoints(self) -> None:
        self.assertIs(writer_facade.write_fact_bundle, write_fact_bundle)
        self.assertIs(writer_facade.write_spec_bundle, write_spec_bundle)

    def test_cli_init_and_update_write_defaults_under_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = create_project(Path(tmp))

            self.assertEqual(main(["init", str(project)]), 0)
            self.assertTrue((project / ".specforge" / "facts.json").exists())
            self.assertTrue((project / "specforge-output" / "overview.md").exists())

            with self.assertRaises(SystemExit):
                main(["init", str(project)])

            self.assertEqual(main(["init", "--force", str(project)]), 0)

            write_file(project, "src/app.py", "def main():\n    return 0\n")

            self.assertEqual(main(["update", str(project)]), 0)
            facts = json.loads((project / ".specforge" / "facts.json").read_text(encoding="utf-8"))
            self.assertIn("python", {file_fact["language"] for file_fact in facts["files"]})
            self.assertFalse(
                any(
                    file_fact["path"].startswith((".specforge/", "specforge-output/"))
                    for file_fact in facts["files"]
                )
            )

    def test_cli_scan_render_and_forge_commands_still_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = create_project(root)
            write_file(project, "src/app.py", "def main():\n    return 0\n")
            facts_dir = root / "facts"
            rendered_dir = root / "rendered"
            work_dir = root / "work"
            forged_dir = root / "forged"

            self.assertEqual(main(["scan", str(project), "--out", str(facts_dir)]), 0)
            self.assertTrue((facts_dir / "facts.json").exists())

            self.assertEqual(main(["render", str(facts_dir), "--out", str(rendered_dir)]), 0)
            self.assertTrue((rendered_dir / "overview.md").exists())

            self.assertEqual(
                main(
                    [
                        "forge",
                        str(project),
                        "--work-dir",
                        str(work_dir),
                        "--out",
                        str(forged_dir),
                    ]
                ),
                0,
            )
            self.assertTrue((work_dir / "facts.json").exists())
            self.assertTrue((forged_dir / "llm-handoff.md").exists())


if __name__ == "__main__":
    unittest.main()
