from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round190StaticPageSurfaceCalibrationTests(unittest.TestCase):
    def test_static_pages_are_counted_on_static_site_surface_next_to_python_ui_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "requirements.txt").write_text("dash\n", encoding="utf-8")
            (root / "index.html").write_text("<title>Demo shell</title>\n<div id=\"root\"></div>\n", encoding="utf-8")
            (root / "usage.py").write_text(
                """
from dash import Dash, html

app = Dash(__name__)
app.layout = html.Div([html.H1("MQTT echo")])
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            surfaces = {surface.framework: surface for surface in facts.frontend_surfaces}
            self.assertEqual(1, surfaces["dash"].page_count)
            self.assertEqual(1, surfaces["static-site"].page_count)
            self.assertNotIn("static", surfaces)

            pages = {(page.template_engine, page.kind, page.route, page.path) for page in facts.pages}
            self.assertIn(("dash", "dash-app", "/", "usage.py"), pages)
            self.assertIn((None, "static-page", "/", "index.html"), pages)


if __name__ == "__main__":
    unittest.main()
