from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.gaps import detect_gaps
from specforge.renderers import write_spec_bundle
from specforge.scanner import scan_project
from specforge.trace import build_trace_claims

from fixtures import create_project, create_v2_linked_project, write_file


class V2OutputTests(unittest.TestCase):

    def test_v2_rebuild_documents_keep_expected_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = create_v2_linked_project(Path(tmp))
            facts = scan_project(project)
            claims = build_trace_claims(facts)
            gaps = detect_gaps(facts)
            spec_out = Path(tmp) / "spec"

            write_spec_bundle(facts, claims, gaps, spec_out)

            feature_map = (spec_out / "feature-map.md").read_text(encoding="utf-8")
            rebuild_spec = (spec_out / "rebuild-spec.md").read_text(encoding="utf-8")
            contract_gaps = (spec_out / "contract-gaps.md").read_text(encoding="utf-8")
            module_boundaries = (spec_out / "module-boundaries.md").read_text(encoding="utf-8")
            spec_diff = (spec_out / "spec-diff.md").read_text(encoding="utf-8")

            self.assertIn("GET /api/users/123", feature_map)
            self.assertIn("GET /api/users/:id", feature_map)
            self.assertIn("Confidence: medium", feature_map)
            self.assertIn("## Rebuild Order", rebuild_spec)
            self.assertIn("## Feature Targets", rebuild_spec)
            self.assertIn("unknown-error", contract_gaps)
            self.assertIn("Frontend Surface", module_boundaries)
            self.assertIn("Backend API Surface", module_boundaries)
            self.assertIn("No previous fact bundle", spec_diff)

    def test_cli_project_generates_command_rebuild_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = create_project(Path(tmp))
            write_file(
                project,
                "pyproject.toml",
                """
[project]
name = "demo"

[project.scripts]
demo = "demo.cli:main"
""".strip()
                + "\n",
            )
            write_file(
                project,
                "src/demo/cli.py",
                """
import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    scan_parser = subparsers.add_parser("scan", help="scan project")
    scan_parser.add_argument("project")
    scan_parser.add_argument("--out")
    return parser
""".strip()
                + "\n",
            )
            write_file(project, "src/demo/scan.py", "def run_scan():\n    return 0\n")
            write_file(project, "src/demo/scan_helpers.py", "def helper():\n    return 0\n")
            write_file(project, "src/demo/__init__.py", "")
            write_file(project, "tests/test_scan.py", "def test_scan_command(): pass\n")
            facts = scan_project(project)
            claims = build_trace_claims(facts)
            gaps = detect_gaps(facts)
            spec_out = Path(tmp) / "spec"

            write_spec_bundle(facts, claims, gaps, spec_out)

            feature_map = (spec_out / "feature-map.md").read_text(encoding="utf-8")
            rebuild_spec = (spec_out / "rebuild-spec.md").read_text(encoding="utf-8")
            module_boundaries = (spec_out / "module-boundaries.md").read_text(encoding="utf-8")
            llm_handoff = (spec_out / "llm-handoff.md").read_text(encoding="utf-8")

            self.assertIn("CLI command `scan`", feature_map)
            self.assertIn("- Commands: `scan project --out`", feature_map)
            self.assertIn("src/demo/scan.py", feature_map)
            self.assertNotIn("src/demo/scan_helpers.py", feature_map)
            self.assertNotIn("src/demo/__init__.py", feature_map)
            self.assertIn("- CLI: `scan project --out`", rebuild_spec)
            self.assertIn("src/demo/scan.py", rebuild_spec)
            self.assertIn("CLI Surface", module_boundaries)
            self.assertIn("src/demo/scan.py", module_boundaries)
            self.assertNotIn("Paths: `none detected`", module_boundaries)
            self.assertIn("CLI/library-oriented", llm_handoff)

    def test_large_file_refactor_findings_ignore_non_implementation_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = create_project(Path(tmp))
            write_file(project, "docs/large.md", "docs\n" * 6000)
            write_file(project, "assets/large.png", "image-bytes\n" * 3000)
            write_file(project, "package-lock.json", '{"lockfileVersion": 3}\n' * 2000)
            write_file(project, "src/large.ts", "export function work() { return 1; }\n" * 800)

            facts = scan_project(project)
            subjects = {
                finding.subject
                for finding in facts.refactor_findings
                if finding.title == "Large file may need a module boundary"
            }

            self.assertIn("src/large.ts", subjects)
            self.assertNotIn("docs/large.md", subjects)
            self.assertNotIn("assets/large.png", subjects)
            self.assertNotIn("package-lock.json", subjects)

    def test_command_features_include_action_import_match_reasons(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = create_project(Path(tmp))
            write_file(
                project,
                "package.json",
                '{"dependencies":{"commander":"^14.0.0"}}\n',
            )
            write_file(
                project,
                "src/cli.ts",
                """
import { Command } from 'commander';
import { UpdateCommand } from './commands/update';

const program = new Command();

program
  .command('update')
  .description('Update files')
  .action(async () => {
    const command = new UpdateCommand();
    await command.execute();
  });

program
  .command('experimental')
  .description('Alias for init')
  .action(async () => {
    const { InitCommand } = await import('./core/init.js');
    await new InitCommand().execute();
  });
""".strip()
                + "\n",
            )
            write_file(project, "src/commands/update.ts", "export class UpdateCommand {}\n")
            write_file(project, "src/core/init.ts", "export class InitCommand {}\n")

            facts = scan_project(project)
            features = {feature.commands[0].split()[0]: feature for feature in facts.feature_maps}

            self.assertIn("src/commands/update.ts", features["update"].implementation_sources)
            self.assertIn("src/core/init.ts", features["experimental"].implementation_sources)
            self.assertTrue(
                any("UpdateCommand" in reason for reason in features["update"].implementation_reasons)
            )
            self.assertTrue(
                any("dynamically imports" in reason for reason in features["experimental"].implementation_reasons)
            )


if __name__ == "__main__":
    unittest.main()
