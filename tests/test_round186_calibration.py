from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round186FlaskAppBuilderModelRestGeneratedRoutesTests(unittest.TestCase):
    def test_model_rest_api_include_route_methods_generate_framework_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"dependencies":{"@superset-ui/core":"^0.20.0","react":"^18.0.0"}}\n',
                encoding="utf-8",
            )

            api_dir = root / "superset" / "charts"
            api_dir.mkdir(parents=True)
            (api_dir / "api.py").write_text(
                """
from superset.constants import RouteMethod
from superset.views.base_api import BaseSupersetModelRestApi


class ChartRestApi(BaseSupersetModelRestApi):
    resource_name = "chart"
    include_route_methods = RouteMethod.REST_MODEL_VIEW_CRUD_SET | {
        RouteMethod.RELATED,
        RouteMethod.DISTINCT,
    }
""".lstrip(),
                encoding="utf-8",
            )

            frontend = root / "superset-frontend" / "src"
            frontend.mkdir(parents=True)
            (frontend / "chart.ts").write_text(
                """
import { SupersetClient } from "@superset-ui/core";

SupersetClient.get({ endpoint: "/api/v1/chart/42" });
SupersetClient.post({ endpoint: "/api/v1/chart/" });
SupersetClient.put({ endpoint: "/api/v1/chart/42" });
SupersetClient.delete({ endpoint: "/api/v1/chart/42" });
SupersetClient.get({ endpoint: "/api/v1/chart/related/owners" });
SupersetClient.get({ endpoint: "/api/v1/chart/distinct/slice_name" });
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.method, route.path, route.handler, route.kind) for route in facts.api_routes}
            self.assertIn(("GET", "/api/v1/chart/<pk>", "get", "flask-appbuilder-model-rest-generated"), routes)
            self.assertIn(("GET", "/api/v1/chart", "get_list", "flask-appbuilder-model-rest-generated"), routes)
            self.assertIn(("POST", "/api/v1/chart", "post", "flask-appbuilder-model-rest-generated"), routes)
            self.assertIn(("PUT", "/api/v1/chart/<pk>", "put", "flask-appbuilder-model-rest-generated"), routes)
            self.assertIn(("DELETE", "/api/v1/chart/<pk>", "delete", "flask-appbuilder-model-rest-generated"), routes)
            self.assertIn(
                ("GET", "/api/v1/chart/related/<column_name>", "related", "flask-appbuilder-model-rest-generated"),
                routes,
            )
            self.assertIn(
                ("GET", "/api/v1/chart/distinct/<column_name>", "distinct", "flask-appbuilder-model-rest-generated"),
                routes,
            )

            calls = {(call.method, call.endpoint, call.matched_route) for call in facts.api_calls}
            self.assertIn(("GET", "/api/v1/chart/42", "GET /api/v1/chart/<pk>"), calls)
            self.assertIn(("POST", "/api/v1/chart/", "POST /api/v1/chart"), calls)
            self.assertIn(("PUT", "/api/v1/chart/42", "PUT /api/v1/chart/<pk>"), calls)
            self.assertIn(("DELETE", "/api/v1/chart/42", "DELETE /api/v1/chart/<pk>"), calls)
            self.assertIn(("GET", "/api/v1/chart/related/owners", "GET /api/v1/chart/related/<column_name>"), calls)
            self.assertIn(
                ("GET", "/api/v1/chart/distinct/slice_name", "GET /api/v1/chart/distinct/<column_name>"),
                calls,
            )


if __name__ == "__main__":
    unittest.main()
