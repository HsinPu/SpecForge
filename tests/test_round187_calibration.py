from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round187SupersetEndpointNormalizationCalibrationTests(unittest.TestCase):
    def test_superset_template_query_builders_and_typescript_casts_are_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"dependencies":{"@superset-ui/core":"^0.20.0","react":"^18.0.0"}}\n',
                encoding="utf-8",
            )

            api_dir = root / "superset"
            api_dir.mkdir()
            (api_dir / "api.py").write_text(
                """
from flask_appbuilder import expose
from superset.views.base_api import BaseSupersetApi


class DatabaseRestApi(BaseSupersetApi):
    route_base = "/api/v1/database"

    @expose("/<int:pk>/table_metadata/", methods=("GET",))
    def table_metadata(self, pk):
        pass

    @expose("/<int:pk>/table_metadata/extra/", methods=("GET",))
    def table_metadata_extra(self, pk):
        pass


class SqlLabPermalinkRestApi(BaseSupersetApi):
    route_base = "/api/v1/sqllab"

    @expose("/permalink/<string:key>", methods=("GET",))
    def get(self, key):
        pass
""".lstrip(),
                encoding="utf-8",
            )

            frontend = root / "superset-frontend" / "src"
            frontend.mkdir(parents=True)
            (frontend / "client.ts").write_text(
                """
import { SupersetClient } from "@superset-ui/core";

SupersetClient.get({
  endpoint: `/api/v1/database/${dbId}/table_metadata/${toQueryString({
    name: table,
    catalog,
    schema,
  })}`,
});

SupersetClient.get({
  endpoint: `/api/v1/database/${dbId}/table_metadata/extra/${toQueryString(
    { name: table, catalog, schema },
  )}`,
});

SupersetClient.get({
  endpoint: `/api/v1/sqllab/permalink/kv:${urlId}`,
});

SupersetClient.postForm(url as string, {
  form_data: "{}",
});
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            calls = {(call.method, call.endpoint, call.matched_route) for call in facts.api_calls}
            self.assertIn(
                (
                    "GET",
                    "/api/v1/database/:dbId/table_metadata/",
                    "GET /api/v1/database/<int:pk>/table_metadata/",
                ),
                calls,
            )
            self.assertIn(
                (
                    "GET",
                    "/api/v1/database/:dbId/table_metadata/extra/",
                    "GET /api/v1/database/<int:pk>/table_metadata/extra/",
                ),
                calls,
            )
            self.assertIn(
                ("GET", "/api/v1/sqllab/permalink/:param", "GET /api/v1/sqllab/permalink/<string:key>"),
                calls,
            )
            self.assertIn(("POST", "dynamic:url", None), calls)

            endpoints = {call.endpoint for call in facts.api_calls}
            self.assertNotIn("/urlasstring", endpoints)
            malformed = [endpoint for endpoint in endpoints if endpoint.endswith(",)}") or endpoint.endswith(")}")]
            self.assertEqual([], malformed)


if __name__ == "__main__":
    unittest.main()
