from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round153PanelCalibrationTests(unittest.TestCase):
    def test_panel_app_entrypoint_page_components_commands_and_test_map_are_extracted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "requirements.txt").write_text("panel>=1.0.0\npytest\n", encoding="utf-8")
            (root / "thumbnail.png").write_bytes(b"fake png")
            (root / "app.py").write_text(
                """
import panel as pn

pn.extension(sizing_mode="stretch_width", template="fast")

pn.state.template.param.update(
    site="Awesome Panel",
    title="Hello World",
)

variable = pn.widgets.RadioBoxGroup(
    name="Variable",
    value="Temperature",
    options=["Temperature", "Humidity"],
).servable(area="sidebar")
window = pn.widgets.IntSlider(name="Window", value=20, start=1, end=60).servable(area="sidebar")

pn.panel("Hello and welcome to Panel").servable()
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "app_tests.py").write_text(
                """
from app import variable


def test_widget_exists():
    assert variable is not None
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("panel", "frontend"), frameworks)

            entrypoints = {(item.path, item.kind, item.command) for item in facts.entrypoints}
            self.assertIn(("app.py", "panel-app", "panel serve app.py"), entrypoints)

            commands = {item.name for item in facts.commands}
            self.assertIn("panel serve app.py", commands)
            self.assertIn("pytest", commands)

            pages_by_path = {page.path: page for page in facts.pages}
            self.assertEqual(pages_by_path["app.py"].route, "/")
            self.assertEqual(pages_by_path["app.py"].title, "Hello World")
            self.assertEqual(pages_by_path["app.py"].kind, "panel-app")
            self.assertEqual(pages_by_path["app.py"].template_engine, "panel")

            routes = {(route.route, route.path, route.framework, route.kind) for route in facts.frontend_routes}
            self.assertIn(("/", "app.py", "panel", "panel-app-route"), routes)

            components = {(item.name, item.framework) for item in facts.components}
            self.assertIn(("RadioBoxGroup:Variable", "panel"), components)
            self.assertIn(("IntSlider:Window", "panel"), components)
            self.assertIn(("Panel:Hello and welcome to Panel", "panel"), components)

            maps_by_page = {frontend_map.page: frontend_map for frontend_map in facts.frontend_maps}
            self.assertIn("Panel:Hello and welcome to Panel", maps_by_page["app.py"].components)

            test_targets = {
                (test_map.test_path, test_map.target_kind, test_map.target)
                for test_map in facts.test_maps
            }
            self.assertIn(("app_tests.py", "cli-command", "panel serve app.py"), test_targets)


if __name__ == "__main__":
    unittest.main()
