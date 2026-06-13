from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round151GradioCalibrationTests(unittest.TestCase):
    def test_gradio_app_entrypoint_page_route_commands_and_components_are_extracted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "requirements.txt").write_text(
                "gradio>=5.0.0\npytest>=8.0.0\n",
                encoding="utf-8",
            )
            (root / "app.py").write_text(
                """
import gradio as gr


def calculate(operation, num1, num2):
    return num1 + num2


with gr.Blocks(title="Calculator App") as demo:
    gr.Markdown("# Simple Calculator")
    num1 = gr.Number(label="First Number", value=0)
    operation = gr.Dropdown(choices=["Add", "Subtract"], label="Operation", value="Add")
    num2 = gr.Number(label="Second Number (ignored for Square)", value=0)
    calculate_btn = gr.Button("Calculate", variant="primary")
    result = gr.Textbox(label="Result", interactive=False)
    calculate_btn.click(fn=calculate, inputs=[operation, num1, num2], outputs=result)
    gr.Examples(examples=[["Add", 1, 2]], inputs=[operation, num1, num2])

if __name__ == "__main__":
    demo.launch()
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "backend_tests.py").write_text(
                """
from app import calculate


def test_calculate():
    assert calculate("Add", 1, 2) == 3
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            entrypoints = {(item.path, item.kind, item.command) for item in facts.entrypoints}
            self.assertIn(("app.py", "gradio-app", "python app.py"), entrypoints)

            commands = {item.name for item in facts.commands}
            self.assertIn("python app.py", commands)
            self.assertIn("gradio app.py", commands)
            self.assertIn("pytest", commands)

            pages_by_path = {page.path: page for page in facts.pages}
            self.assertEqual(pages_by_path["app.py"].route, "/")
            self.assertEqual(pages_by_path["app.py"].title, "Calculator App")
            self.assertEqual(pages_by_path["app.py"].kind, "gradio-app")
            self.assertEqual(pages_by_path["app.py"].template_engine, "gradio")
            self.assertNotIn("backend_tests.py", pages_by_path)

            routes = {(route.route, route.path, route.framework, route.kind) for route in facts.frontend_routes}
            self.assertIn(("/", "app.py", "gradio", "gradio-app-route"), routes)

            components = {(item.name, item.framework) for item in facts.components}
            self.assertIn(("Blocks:Calculator App", "gradio"), components)
            self.assertIn(("Number:First Number", "gradio"), components)
            self.assertIn(("Number:Second Number (ignored for Square)", "gradio"), components)
            self.assertIn(("Dropdown:Operation", "gradio"), components)
            self.assertIn(("Button:Calculate", "gradio"), components)
            self.assertIn(("Textbox:Result", "gradio"), components)
            self.assertIn(("Examples", "gradio"), components)
            self.assertNotIn(("Examples:Add", "gradio"), components)

            maps_by_route = {frontend_map.route: frontend_map for frontend_map in facts.frontend_maps}
            self.assertIn("Blocks:Calculator App", maps_by_route["/"].components)
            self.assertIn("Button:Calculate", maps_by_route["/"].components)

            test_targets = {
                (test_map.test_path, test_map.target_kind, test_map.target)
                for test_map in facts.test_maps
            }
            self.assertTrue(
                any(
                    test_path == "backend_tests.py"
                    and target_kind == "cli-command"
                    and target in {"python app.py", "gradio app.py"}
                    for test_path, target_kind, target in test_targets
                )
            )


if __name__ == "__main__":
    unittest.main()
