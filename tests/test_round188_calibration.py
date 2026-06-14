from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round188SupersetLocationSearchCalibrationTests(unittest.TestCase):
    def test_location_search_template_segment_is_not_treated_as_route_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"dependencies":{"@superset-ui/core":"^0.20.0","react":"^18.0.0"}}\n',
                encoding="utf-8",
            )

            api_dir = root / "superset" / "sqllab"
            api_dir.mkdir(parents=True)
            (api_dir / "api.py").write_text(
                """
from flask_appbuilder import expose
from superset.views.base_api import BaseSupersetApi


class SqlLabRestApi(BaseSupersetApi):
    route_base = "/api/v1/sqllab"

    @expose("/execute/", methods=("POST",))
    def execute_sql_query(self):
        pass
""".lstrip(),
                encoding="utf-8",
            )

            frontend = root / "superset-frontend" / "src"
            frontend.mkdir(parents=True)
            (frontend / "sqlLab.ts").write_text(
                """
import { SupersetClient } from "@superset-ui/core";

export function runQuery() {
  const search = window.location.search || "";
  return SupersetClient.post({
    endpoint: `/api/v1/sqllab/execute/${search}`,
    body: "{}",
  });
}
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            calls = {(call.method, call.endpoint, call.matched_route) for call in facts.api_calls}
            self.assertIn(("POST", "/api/v1/sqllab/execute/", "POST /api/v1/sqllab/execute/"), calls)
            self.assertNotIn(("POST", "/api/v1/sqllab/execute/:search", None), calls)


if __name__ == "__main__":
    unittest.main()
