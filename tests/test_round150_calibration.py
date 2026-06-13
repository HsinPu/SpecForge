from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round150StreamlitCalibrationTests(unittest.TestCase):
    def test_streamlit_entrypoint_commands_pages_and_routes_are_extracted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "requirements.txt").write_text("streamlit==1.36.0\npytest\n", encoding="utf-8")
            (root / "Chatbot.py").write_text(
                """
import streamlit as st

st.set_page_config(page_title="Chatbot")
st.title("Chatbot")
if "messages" not in st.session_state:
    st.session_state["messages"] = []
""".strip()
                + "\n",
                encoding="utf-8",
            )
            pages = root / "pages"
            pages.mkdir()
            (pages / "1_File_Q&A.py").write_text(
                """
import streamlit as st

st.title("File Q&A")
question = st.text_input("Question")
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "app_test.py").write_text(
                """
def test_smoke():
    assert True
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            entrypoints = {(item.path, item.kind, item.command) for item in facts.entrypoints}
            self.assertIn(("Chatbot.py", "streamlit-app", "streamlit run Chatbot.py"), entrypoints)

            commands = {item.name for item in facts.commands}
            self.assertIn("streamlit run Chatbot.py", commands)
            self.assertIn("pytest", commands)

            pages_by_path = {page.path: page for page in facts.pages}
            self.assertEqual(pages_by_path["Chatbot.py"].route, "/")
            self.assertEqual(pages_by_path["Chatbot.py"].title, "Chatbot")
            self.assertEqual(pages_by_path["Chatbot.py"].kind, "streamlit-page")
            self.assertEqual(pages_by_path["Chatbot.py"].template_engine, "streamlit")
            self.assertEqual(pages_by_path["pages/1_File_Q&A.py"].route, "/file-q-a")
            self.assertEqual(pages_by_path["pages/1_File_Q&A.py"].title, "File Q&A")
            self.assertNotIn("app_test.py", pages_by_path)

            routes = {(route.route, route.path, route.framework, route.kind) for route in facts.frontend_routes}
            self.assertIn(("/", "Chatbot.py", "streamlit", "streamlit-page-route"), routes)
            self.assertIn(("/file-q-a", "pages/1_File_Q&A.py", "streamlit", "streamlit-page-route"), routes)

            state_usages = {(state.source, state.library, state.usage, state.name) for state in facts.state_usages}
            self.assertIn(("Chatbot.py", "streamlit", "session-state", "messages"), state_usages)

            maps_by_route = {frontend_map.route: frontend_map for frontend_map in facts.frontend_maps}
            self.assertIn("streamlit:messages", maps_by_route["/"].state)
            self.assertEqual([], maps_by_route["/file-q-a"].state)


if __name__ == "__main__":
    unittest.main()
