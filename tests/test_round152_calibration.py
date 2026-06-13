from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round152DashCalibrationTests(unittest.TestCase):
    def test_dash_entrypoint_page_components_commands_and_test_map_are_extracted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "requirements.txt").write_text("dash[dev]>=2.0.0\npytest\n", encoding="utf-8")
            (root / "index.html").write_text(
                "<html><head><title>Static Shell</title></head><body></body></html>\n",
                encoding="utf-8",
            )
            (root / "usage.py").write_text(
                """
import dash
from dash.dependencies import Input, Output, State
import dash_html_components as html
import dash_core_components as dcc
import dash_mqtt

app = dash.Dash(__name__)

app.layout = html.Div([
    dash_mqtt.DashMqtt(id="mqtt", topics=["testtopic"]),
    html.H1("MQTT echo"),
    dcc.Input(id="message_to_send", placeholder="message to send", debounce=True),
    html.Button("Send", id="send"),
    html.Div(id="return_message"),
])


@app.callback(Output("return_message", "children"), Input("mqtt", "incoming"))
def display_incoming_message(incoming_message):
    return incoming_message


if __name__ == "__main__":
    app.run_server(debug=True)
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "usage_tests.py").write_text(
                """
from usage import app


def test_app_exists():
    assert app is not None
""".strip()
                + "\n",
                encoding="utf-8",
            )
            generated = root / "dash_pkg"
            generated.mkdir()
            (generated / "output.js").write_text(
                "export class InternalBundleNoise {}\n",
                encoding="utf-8",
            )
            (generated / "230a278-main-wps-hmr.js").write_text(
                "export class HotReloadNoise {}\n",
                encoding="utf-8",
            )
            deps = root / "inst" / "deps"
            deps.mkdir(parents=True)
            (deps / "output.js").write_text(
                "export class RPackageBundleNoise {}\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("dash", "frontend"), frameworks)

            entrypoints = {(item.path, item.kind, item.command) for item in facts.entrypoints}
            self.assertIn(("usage.py", "dash-app", "python usage.py"), entrypoints)

            commands = {item.name for item in facts.commands}
            self.assertIn("python usage.py", commands)
            self.assertIn("pytest", commands)

            pages_by_path = {page.path: page for page in facts.pages}
            self.assertEqual(pages_by_path["usage.py"].route, "/")
            self.assertEqual(pages_by_path["usage.py"].title, "MQTT echo")
            self.assertEqual(pages_by_path["usage.py"].kind, "dash-app")
            self.assertEqual(pages_by_path["usage.py"].template_engine, "dash")

            routes = {(route.route, route.path, route.framework, route.kind) for route in facts.frontend_routes}
            self.assertIn(("/", "usage.py", "dash", "dash-app-route"), routes)

            components = {(item.name, item.framework) for item in facts.components}
            self.assertIn(("DashMqtt:mqtt", "dash"), components)
            self.assertIn(("H1:MQTT echo", "dash"), components)
            self.assertIn(("Input:message_to_send", "dash"), components)
            self.assertIn(("Button:send", "dash"), components)
            self.assertIn(("Div:return_message", "dash"), components)
            self.assertNotIn(("InternalBundleNoise", "react"), components)
            self.assertNotIn(("HotReloadNoise", "react"), components)
            self.assertNotIn(("RPackageBundleNoise", "react"), components)

            dash_map = next(frontend_map for frontend_map in facts.frontend_maps if frontend_map.page == "usage.py")
            static_map = next(frontend_map for frontend_map in facts.frontend_maps if frontend_map.page == "index.html")
            self.assertIn("DashMqtt:mqtt", dash_map.components)
            self.assertIn("Input:message_to_send", dash_map.components)
            self.assertNotIn("DashMqtt:mqtt", static_map.components)

            test_targets = {
                (test_map.test_path, test_map.target_kind, test_map.target)
                for test_map in facts.test_maps
            }
            self.assertIn(("usage_tests.py", "cli-command", "python usage.py"), test_targets)


if __name__ == "__main__":
    unittest.main()
