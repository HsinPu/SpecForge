from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round141SupersetFlaskAppBuilderCalibrationTests(unittest.TestCase):
    def test_flask_appbuilder_expose_routes_use_resource_name_and_route_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            api_dir = root / "superset" / "charts"
            views_dir = root / "superset" / "views"
            api_dir.mkdir(parents=True)
            views_dir.mkdir(parents=True)

            (api_dir / "api.py").write_text(
                """
from flask_appbuilder import expose
from superset.views.base_api import BaseSupersetModelRestApi


class ChartRestApi(BaseSupersetModelRestApi):
    resource_name = "chart"

    @expose("/<id_or_uuid>", methods=["GET"])
    def get(self, id_or_uuid):
        return self.response(200)

    @expose("/", methods=("POST",))
    def post(self):
        return self.response(201)
""".lstrip(),
                encoding="utf-8",
            )
            (views_dir / "sqllab.py").write_text(
                """
from flask_appbuilder import expose
from superset.views.base import BaseSupersetView


class SupersetSqllabView(BaseSupersetView):
    route_base = "/sqllab"

    @expose("/history/", methods=("GET",))
    def history(self):
        return self.render_template("superset/history.html")


class TabStateView(BaseSupersetView):
    @expose("<int:tab_state_id>/activate", methods=("POST",))
    def activate(self, tab_state_id):
        return self.json_response({"ok": True})
""".lstrip(),
                encoding="utf-8",
            )
            (api_dir / "data_api.py").write_text(
                """
from flask_appbuilder.api import expose
from superset.charts.api import ChartRestApi


class ChartDataRestApi(ChartRestApi):
    @expose(
        "/<int:pk>/data/",
        methods=("GET",),
    )
    @event_logger.log_this_with_context(
        action=lambda self, *args, **kwargs: (
            "ChartDataRestApi.get_data.has.a.long.decorator.chain.to.keep.handler.lookup.wide"
        ),
        log_to_statsd=False,
        allow_extra_payload=True,
    )
    def get_data(self, pk):
        return self.response(200)
""".lstrip(),
                encoding="utf-8",
            )
            (root / "superset" / "initialization").mkdir(parents=True)
            (root / "superset" / "initialization" / "__init__.py").write_text(
                """
from flask_appbuilder import expose, IndexView


class SupersetIndexView(IndexView):
    @expose("/")
    def index(self):
        return "ok"

    @expose("/lang/<string:locale>")
    def patch_flask_locale(self, locale):
        return "ok"
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)
            routes = {(route.method, route.path): route for route in facts.api_routes}

            self.assertIn(("GET", "/api/v1/chart/<id_or_uuid>"), routes)
            get_route = routes[("GET", "/api/v1/chart/<id_or_uuid>")]
            self.assertEqual("flask-appbuilder", get_route.framework)
            self.assertEqual("get", get_route.handler)
            self.assertEqual("ChartRestApi", get_route.class_prefix)
            self.assertEqual("superset/charts/api.py", get_route.evidence.file)
            self.assertEqual(["id_or_uuid"], [param.name for param in get_route.parameters])

            self.assertIn(("POST", "/api/v1/chart"), routes)
            self.assertEqual("post", routes[("POST", "/api/v1/chart")].handler)

            self.assertIn(("GET", "/sqllab/history/"), routes)
            sqllab_route = routes[("GET", "/sqllab/history/")]
            self.assertEqual("flask-appbuilder", sqllab_route.framework)
            self.assertEqual("history", sqllab_route.handler)
            self.assertEqual("SupersetSqllabView", sqllab_route.class_prefix)

            self.assertIn(("GET", "/api/v1/chart/<int:pk>/data/"), routes)
            self.assertEqual("get_data", routes[("GET", "/api/v1/chart/<int:pk>/data/")].handler)
            self.assertIn(("POST", "/tabstateview/<int:tab_state_id>/activate"), routes)
            self.assertEqual("activate", routes[("POST", "/tabstateview/<int:tab_state_id>/activate")].handler)
            self.assertIn(("GET", "/"), routes)
            self.assertIn(("GET", "/lang/<string:locale>"), routes)


if __name__ == "__main__":
    unittest.main()
