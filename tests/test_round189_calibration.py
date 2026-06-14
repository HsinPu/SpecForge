from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round189PythonUiFrontendSurfaceCalibrationTests(unittest.TestCase):
    def test_streamlit_and_gradio_pages_are_counted_on_their_framework_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "requirements.txt").write_text("streamlit\ngradio\n", encoding="utf-8")
            (root / "Chatbot.py").write_text(
                """
import streamlit as st

st.set_page_config(page_title="Chatbot")
if "messages" not in st.session_state:
    st.session_state.messages = []
st.title("Chatbot")
""".lstrip(),
                encoding="utf-8",
            )
            (root / "app.py").write_text(
                """
import gradio as gr

with gr.Blocks(title="Calculator App") as demo:
    gr.Markdown("# Simple Calculator")

demo.launch()
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            surfaces = {surface.framework: surface for surface in facts.frontend_surfaces}
            self.assertEqual(1, surfaces["streamlit"].page_count)
            self.assertEqual(1, surfaces["gradio"].page_count)
            self.assertNotIn("static-site", surfaces)

            pages = {(page.template_engine, page.route, page.path) for page in facts.pages}
            self.assertIn(("streamlit", "/", "Chatbot.py"), pages)
            self.assertIn(("gradio", "/", "app.py"), pages)


if __name__ == "__main__":
    unittest.main()
