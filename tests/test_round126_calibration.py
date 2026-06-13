from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round126ReactReduxAgentCalibrationTests(unittest.TestCase):

    def test_requests_plural_client_del_calls_are_delete_api_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            src.mkdir()
            (root / "package.json").write_text(
                '{"dependencies":{"react":"^18.0.0","react-redux":"^9.0.0","redux":"^5.0.0","react-router-dom":"^6.0.0"}}\n',
                encoding="utf-8",
            )
            (src / "agent.js").write_text(
                """
const requests = {
  get: url => superagent.get(`${API_ROOT}${url}`),
  del: url => superagent.del(`${API_ROOT}${url}`)
};

const Comments = {
  delete: (slug, commentId) =>
    requests.del(`/articles/${slug}/comments/${commentId}`),
  forArticle: slug =>
    requests.get(`/articles/${slug}/comments`)
};
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            calls = {(call.method, call.endpoint, call.client, call.context) for call in facts.api_calls}
            self.assertIn(("DELETE", "/articles/:slug/comments/:commentId", "requests", "source"), calls)
            self.assertIn(("GET", "/articles/:slug/comments", "requests", "source"), calls)


if __name__ == "__main__":
    unittest.main()
