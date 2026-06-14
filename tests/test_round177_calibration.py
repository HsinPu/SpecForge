from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round177FrontendAjaxMethodCalibrationTests(unittest.TestCase):
    def test_multiline_ajax_method_after_nested_call_is_scanned_and_linked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'rails'\n", encoding="utf-8")
            (root / "package.json").write_text('{"dependencies":{"ember-source":"^6.0.0"}}\n', encoding="utf-8")

            config = root / "config"
            config.mkdir()
            (config / "routes.rb").write_text(
                """
Rails.application.routes.draw do
  put "/admin/color_schemes/:id", to: "admin/color_schemes#update"
  delete "/t/:topic_id/timings", to: "topics#destroy_timings"
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            frontend = root / "frontend" / "discourse" / "admin" / "models"
            frontend.mkdir(parents=True)
            (frontend / "color-scheme.js").write_text(
                """
import { ajax } from "discourse/lib/ajax";

export function updateUserSelectable(colorScheme, value) {
  return ajax(`/admin/color_schemes/${colorScheme.id}.json`, {
    data: JSON.stringify({ color_scheme: { user_selectable: value } }),
    type: "PUT",
    dataType: "json",
    contentType: "application/json",
  });
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            calls = {(call.client, call.method, call.endpoint, call.matched_route) for call in facts.api_calls}
            self.assertIn(
                (
                    "ajax",
                    "PUT",
                    "/admin/color_schemes/:id.json",
                    "PUT /admin/color_schemes/:id",
                ),
                calls,
            )

            links = {(link.method, link.endpoint, link.matched_route, link.match_type) for link in facts.api_links}
            self.assertIn(
                (
                    "PUT",
                    "/admin/color_schemes/:id.json",
                    "/admin/color_schemes/:id",
                    "format-suffix",
                ),
                links,
            )

    def test_ajax_string_concat_endpoint_is_scanned_as_full_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'rails'\n", encoding="utf-8")
            (root / "package.json").write_text('{"dependencies":{"ember-source":"^6.0.0"}}\n', encoding="utf-8")

            config = root / "config"
            config.mkdir()
            (config / "routes.rb").write_text(
                """
Rails.application.routes.draw do
  delete "/t/:topic_id/timings", to: "topics#destroy_timings"
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            frontend = root / "frontend" / "discourse" / "app" / "controllers"
            frontend.mkdir(parents=True)
            (frontend / "topic.js").write_text(
                """
import { ajax } from "discourse/lib/ajax";

export function deferTopic(topic) {
  return ajax("/t/" + topic.get("id") + "/timings.json?last=1", { type: "DELETE" });
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            calls = {(call.client, call.method, call.endpoint, call.matched_route) for call in facts.api_calls}
            self.assertIn(
                (
                    "ajax",
                    "DELETE",
                    "/t/:id/timings.json",
                    "DELETE /t/:topic_id/timings",
                ),
                calls,
            )
            self.assertNotIn(("ajax", "DELETE", "/t/", None), calls)


if __name__ == "__main__":
    unittest.main()
