from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round154ShinyCalibrationTests(unittest.TestCase):
    def test_shiny_app_entrypoint_page_components_state_commands_and_test_map_are_extracted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "requirements.txt").write_text("shiny\npytest\n", encoding="utf-8")
            (root / "app.py").write_text(
                """
from shiny import App, reactive, render, ui

app_ui = ui.page_fluid(
    ui.h2("Pygwalker Shiny"),
    ui.input_select("dataset", "Dataset", choices=["airbnb", "sales"]),
    ui.output_ui("walker"),
)


def server(input, output, session):
    @reactive.Calc
    def selected_dataset():
        return input.dataset()

    @render.ui
    def walker():
        return ui.HTML(selected_dataset())


app = App(app_ui, server)
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "tests").mkdir()
            (root / "tests" / "test_app.py").write_text(
                """
from app import app


def test_app_exists():
    assert app is not None
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("shiny", "frontend"), frameworks)

            entrypoints = {(item.path, item.kind, item.command) for item in facts.entrypoints}
            self.assertIn(("app.py", "shiny-app", "shiny run app.py"), entrypoints)

            commands = {item.name for item in facts.commands}
            self.assertIn("shiny run app.py", commands)
            self.assertIn("pytest", commands)

            pages_by_path = {page.path: page for page in facts.pages}
            self.assertEqual(pages_by_path["app.py"].route, "/")
            self.assertEqual(pages_by_path["app.py"].title, "Pygwalker Shiny")
            self.assertEqual(pages_by_path["app.py"].kind, "shiny-app")
            self.assertEqual(pages_by_path["app.py"].template_engine, "shiny")

            routes = {(route.route, route.path, route.framework, route.kind) for route in facts.frontend_routes}
            self.assertIn(("/", "app.py", "shiny", "shiny-app-route"), routes)

            components = {(item.name, item.framework) for item in facts.components}
            self.assertIn(("H2:Pygwalker Shiny", "shiny"), components)
            self.assertIn(("InputSelect:dataset", "shiny"), components)
            self.assertIn(("OutputUi:walker", "shiny"), components)
            self.assertIn(("HTML", "shiny"), components)

            state_usages = {
                (state.source, state.library, state.usage, state.name)
                for state in facts.state_usages
            }
            self.assertIn(("app.py", "shiny", "input", "dataset"), state_usages)
            self.assertIn(("app.py", "shiny", "reactive", "Calc"), state_usages)
            self.assertIn(("app.py", "shiny", "render", "ui"), state_usages)

            maps_by_page = {frontend_map.page: frontend_map for frontend_map in facts.frontend_maps}
            self.assertIn("InputSelect:dataset", maps_by_page["app.py"].components)
            self.assertIn("shiny:dataset", maps_by_page["app.py"].state)

            test_targets = {
                (test_map.test_path, test_map.target_kind, test_map.target)
                for test_map in facts.test_maps
            }
            self.assertIn(("tests/test_app.py", "cli-command", "shiny run app.py"), test_targets)


if __name__ == "__main__":
    unittest.main()
