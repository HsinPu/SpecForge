from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round191DashImportAppTestMapCalibrationTests(unittest.TestCase):
    def test_dash_import_app_tests_map_to_python_app_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "requirements.txt").write_text("dash[testing]\npytest\n", encoding="utf-8")
            (root / "usage.py").write_text(
                """
import dash
from dash import html

app = dash.Dash(__name__)
app.layout = html.Div([html.H1("MQTT echo")])

if __name__ == "__main__":
    app.run_server(debug=True)
""".lstrip(),
                encoding="utf-8",
            )
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_usage.py").write_text(
                """
from dash.testing.application_runners import import_app


def test_render_component(dash_duo):
    app = import_app("usage")
    dash_duo.start_server(app)
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            test_maps = {item.test_path: item for item in facts.test_maps}
            self.assertEqual("cli-command", test_maps["tests/test_usage.py"].target_kind)
            self.assertEqual("python usage.py", test_maps["tests/test_usage.py"].target)


if __name__ == "__main__":
    unittest.main()
