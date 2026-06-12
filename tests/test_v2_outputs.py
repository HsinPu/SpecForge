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

from fixtures import create_v2_linked_project


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


if __name__ == "__main__":
    unittest.main()
