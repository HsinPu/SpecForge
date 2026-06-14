from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round183AnchoredStaticChoiceCalibrationTests(unittest.TestCase):
    def test_anchored_dynamic_suffix_links_to_static_route_family(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'rails'\n", encoding="utf-8")
            (root / "package.json").write_text('{"dependencies":{"ember-source":"^6.0.0"}}\n', encoding="utf-8")

            config = root / "config"
            config.mkdir()
            (config / "routes.rb").write_text(
                """
Rails.application.routes.draw do
  get "/categories_and_latest", to: "categories#categories_and_latest"
  get "/categories_and_top", to: "categories#categories_and_top"
  get "/categories_and_hot", to: "categories#categories_and_hot"
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            frontend = root / "frontend" / "discourse" / "app" / "routes" / "discovery"
            frontend.mkdir(parents=True)
            (frontend / "categories.js").write_text(
                """
import { ajax } from "discourse/lib/ajax";

export function loadCategories(filter, data) {
  return ajax(`/categories_and_${filter}`, { data });
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            calls = {(call.method, call.endpoint, call.client, call.context, call.matched_route) for call in facts.api_calls}
            self.assertTrue(
                any(
                    method == "GET"
                    and endpoint == "/categories_and_:filter"
                    and client == "ajax"
                    and context == "source"
                    and matched_route in {
                        "GET /categories_and_latest",
                        "GET /categories_and_top",
                        "GET /categories_and_hot",
                    }
                    for method, endpoint, client, context, matched_route in calls
                )
            )

            links = {(link.method, link.endpoint, link.matched_route, link.match_type, link.confidence) for link in facts.api_links}
            self.assertTrue(
                any(
                    method == "GET"
                    and endpoint == "/categories_and_:filter"
                    and matched_route in {"/categories_and_latest", "/categories_and_top", "/categories_and_hot"}
                    and match_type == "static-choice-param"
                    and confidence == "low"
                    for method, endpoint, matched_route, match_type, confidence in links
                )
            )


if __name__ == "__main__":
    unittest.main()
