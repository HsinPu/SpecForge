from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.gaps import detect_gaps
from specforge.persistence import load_fact_bundle
from specforge.renderers import write_fact_bundle, write_spec_bundle
from specforge.scanner import scan_project
from specforge.trace import build_trace_claims


class ScannerTests(unittest.TestCase):

    def test_scan_project_detects_python_manifest_and_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text(
                """
[project]
name = "demo"
dependencies = ["requests>=2"]

[project.scripts]
demo = "demo.cli:main"
""".strip(),
                encoding="utf-8",
            )
            (root / "src" / "demo").mkdir(parents=True)
            (root / "src" / "demo" / "cli.py").write_text(
                """
import argparse
from pathlib import Path


class Runner:
    def run(self, target: Path) -> int:
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    scan_parser = subparsers.add_parser("scan", help="scan project")
    scan_parser.add_argument("project")
    scan_parser.add_argument("--out")
    return parser


def main(argv: list[str] | None = None) -> int:
    return Runner().run(Path("."))
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "tests").mkdir()
            (root / "tests" / "test_cli.py").write_text("def test_cli(): pass\n", encoding="utf-8")

            facts = scan_project(root)

            self.assertEqual(facts.name, Path(tmp).name)
            self.assertEqual(facts.schema_version, "2.0")
            self.assertEqual(facts.languages["python"], 2)
            self.assertEqual(len(facts.test_files), 1)
            self.assertEqual(facts.dependencies[0].name, "requests>=2")
            self.assertIn("demo", {entrypoint.command for entrypoint in facts.entrypoints})
            self.assertIn("Runner", {symbol.name for symbol in facts.symbols})
            self.assertIn("main", {symbol.name for symbol in facts.symbols})
            self.assertIn("argparse", {name for item in facts.imports for name in item.names})
            self.assertIn("scan", {command.name for command in facts.commands})

    def test_write_fact_and_spec_bundles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            facts = scan_project(root)
            claims = build_trace_claims(facts)
            gaps = detect_gaps(facts)
            facts_out = Path(tmp) / "facts"
            spec_out = Path(tmp) / "spec"

            write_fact_bundle(facts, claims, gaps, facts_out)
            write_spec_bundle(facts, claims, gaps, spec_out)

            self.assertTrue((facts_out / "facts.json").exists())
            self.assertTrue((facts_out / "gaps.json").exists())
            self.assertTrue((spec_out / "overview.md").exists())
            self.assertTrue((spec_out / "inventory.md").exists())
            self.assertTrue((spec_out / "modules.md").exists())
            self.assertTrue((spec_out / "symbols.md").exists())
            self.assertTrue((spec_out / "imports.md").exists())
            self.assertTrue((spec_out / "commands.md").exists())
            self.assertTrue((spec_out / "java-web.md").exists())
            self.assertTrue((spec_out / "spring.md").exists())
            self.assertTrue((spec_out / "servlets.md").exists())
            self.assertTrue((spec_out / "jsp-pages.md").exists())
            self.assertTrue((spec_out / "data-models.md").exists())
            self.assertTrue((spec_out / "data-layer.md").exists())
            self.assertTrue((spec_out / "api-contracts.md").exists())
            self.assertTrue((spec_out / "api-links.md").exists())
            self.assertTrue((spec_out / "pages.md").exists())
            self.assertTrue((spec_out / "forms.md").exists())
            self.assertTrue((spec_out / "assets.md").exists())
            self.assertTrue((spec_out / "styles.md").exists())
            self.assertTrue((spec_out / "state.md").exists())
            self.assertTrue((spec_out / "frontend-map.md").exists())
            self.assertTrue((spec_out / "runtime-config.md").exists())
            self.assertTrue((spec_out / "test-map.md").exists())
            self.assertTrue((spec_out / "feature-map.md").exists())
            self.assertTrue((spec_out / "rebuild-spec.md").exists())
            self.assertTrue((spec_out / "refactor-plan.md").exists())
            self.assertTrue((spec_out / "module-boundaries.md").exists())
            self.assertTrue((spec_out / "contract-gaps.md").exists())
            self.assertTrue((spec_out / "spec-diff.md").exists())
            self.assertTrue((spec_out / "implementation-guide.md").exists())
            self.assertTrue((spec_out / "llm-handoff.md").exists())
            self.assertTrue((spec_out / "gaps-and-questions.md").exists())
            traceability = json.loads((spec_out / "traceability.json").read_text(encoding="utf-8"))
            self.assertEqual(traceability[0]["claim_id"], "PROJECT-001")

    def test_scan_project_detects_typescript_symbols_and_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "bin": { "demo": "./bin/demo.js" },
  "dependencies": { "commander": "^14.0.0" }
}
""".strip(),
                encoding="utf-8",
            )
            (root / "src").mkdir()
            (root / "src" / "cli.ts").write_text(
                """
import { Command } from 'commander';

class Runner {}

export function main(argv: string[]): void {}

program
  .command('scan <project>')
  .description('Scan project')
  .option('--out <dir>', 'Output directory')
  .action(() => {});
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            self.assertIn("commander", {item.module for item in facts.imports})
            self.assertIn("Runner", {symbol.name for symbol in facts.symbols})
            self.assertIn("main", {symbol.name for symbol in facts.symbols})
            self.assertIn("scan", {command.name for command in facts.commands})

    def test_scan_project_accepts_utf8_bom_package_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '\ufeff{"bin":{"demo":"./bin/demo.js"},"dependencies":{"express":"^4.0.0"}}\n',
                encoding="utf-8",
            )

            facts = scan_project(root)

            self.assertIn("express", {dependency.name for dependency in facts.dependencies})
            self.assertIn("demo", {entrypoint.command for entrypoint in facts.entrypoints})

    def test_render_accepts_legacy_fact_bundle_without_v1_1_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "legacy"
            project.mkdir()
            facts_out = root / "facts"
            facts_out.mkdir()
            (facts_out / "facts.json").write_text(
                json.dumps(
                    {
                        "root": str(project),
                        "name": "legacy",
                        "files": [],
                        "dependencies": [],
                        "entrypoints": [],
                        "commands": [],
                        "frameworks": [],
                        "api_routes": [],
                        "backend_surfaces": [],
                        "frontend_routes": [],
                        "components": [],
                        "api_calls": [],
                        "frontend_surfaces": [],
                        "imports": [],
                        "symbols": [],
                        "extraction_issues": [],
                        "config_files": [],
                        "test_files": [],
                    }
                ),
                encoding="utf-8",
            )
            (facts_out / "traceability.json").write_text("[]", encoding="utf-8")
            (facts_out / "gaps.json").write_text("[]", encoding="utf-8")

            facts, claims, gaps = load_fact_bundle(facts_out)
            spec_out = root / "spec"
            write_spec_bundle(facts, claims, gaps, spec_out)

            self.assertEqual(facts.schema_version, "2.0")
            self.assertEqual(facts.servlets, [])
            self.assertEqual(facts.pages, [])
            self.assertEqual(facts.forms, [])
            self.assertEqual(facts.assets, [])
            self.assertEqual(facts.styles, [])
            self.assertEqual(facts.state_usages, [])
            self.assertEqual(facts.frontend_maps, [])
            self.assertEqual(facts.api_links, [])
            self.assertEqual(facts.contract_details, [])
            self.assertEqual(facts.data_layers, [])
            self.assertEqual(facts.runtime_configs, [])
            self.assertEqual(facts.test_maps, [])
            self.assertEqual(facts.feature_maps, [])
            self.assertEqual(facts.module_boundaries, [])
            self.assertEqual(facts.refactor_findings, [])
            self.assertEqual(facts.contract_gaps, [])
            self.assertTrue((spec_out / "java-web.md").exists())
            self.assertTrue((spec_out / "pages.md").exists())
            self.assertTrue((spec_out / "frontend-map.md").exists())
            self.assertTrue((spec_out / "api-links.md").exists())
            self.assertTrue((spec_out / "data-layer.md").exists())
            self.assertTrue((spec_out / "runtime-config.md").exists())
            self.assertTrue((spec_out / "test-map.md").exists())
            self.assertTrue((spec_out / "feature-map.md").exists())
            self.assertTrue((spec_out / "rebuild-spec.md").exists())
            self.assertTrue((spec_out / "refactor-plan.md").exists())
            self.assertTrue((spec_out / "module-boundaries.md").exists())
            self.assertTrue((spec_out / "contract-gaps.md").exists())
            self.assertTrue((spec_out / "spec-diff.md").exists())


if __name__ == "__main__":
    unittest.main()
