from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round165DiscourseRailsRoutesCalibrationTests(unittest.TestCase):
    def test_multiline_resources_and_inline_collection_routes_link_ajax_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'rails'\n", encoding="utf-8")
            (root / "config").mkdir()
            (root / "config" / "routes.rb").write_text(
                """
Rails.application.routes.draw do
  namespace :admin do
    resources :badges,
              only: %i[index new show create update destroy],
              constraints: AdminConstraint.new do
      collection do
        post "badge_groupings" => "badges#save_badge_groupings"
        post "preview" => "badges#preview"
      end
    end

    namespace :config do
      resources :about, only: %i[index] do
        collection { put "/" => "about#update" }
      end
    end
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            frontend = root / "app" / "assets" / "javascripts"
            frontend.mkdir(parents=True)
            (frontend / "admin-badges.js").write_text(
                """
import { ajax } from "discourse/lib/ajax";

ajax("/admin/badges/preview.json", { type: "POST" });
ajax("/admin/badges/badge_groupings", { type: "POST" });
ajax("/admin/config/about.json", { type: "PUT" });
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("POST", "/admin/badges/preview", "badges#preview"), routes)
            self.assertIn(("POST", "/admin/badges/badge_groupings", "badges#save_badge_groupings"), routes)
            self.assertIn(("PUT", "/admin/config/about", "about#update"), routes)

            calls = {(call.method, call.endpoint, call.matched_route) for call in facts.api_calls}
            self.assertIn(("POST", "/admin/badges/preview.json", "POST /admin/badges/preview"), calls)
            self.assertIn(("POST", "/admin/badges/badge_groupings", "POST /admin/badges/badge_groupings"), calls)
            self.assertIn(("PUT", "/admin/config/about.json", "PUT /admin/config/about"), calls)

            links = {(link.method, link.endpoint, link.matched_route, link.match_type) for link in facts.api_links}
            self.assertIn(("POST", "/admin/badges/preview.json", "/admin/badges/preview", "format-suffix"), links)
            self.assertIn(("PUT", "/admin/config/about.json", "/admin/config/about", "format-suffix"), links)


if __name__ == "__main__":
    unittest.main()
