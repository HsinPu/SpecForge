from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round171RailsEnginePluginCalibrationTests(unittest.TestCase):
    def test_rails_plugin_engine_routes_are_prefixed_from_mounts_and_linked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'rails'\n", encoding="utf-8")

            plugin = root / "plugins" / "demo-plugin"
            plugin.mkdir(parents=True)
            (plugin / "plugin.rb").write_text(
                """
# frozen_string_literal: true

after_initialize do
  Discourse::Application.routes.append { mount DemoPlugin::Engine, at: "demo" }
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            routes_dir = plugin / "config"
            routes_dir.mkdir()
            (routes_dir / "routes.rb").write_text(
                """
# frozen_string_literal: true

DemoPlugin::Engine.routes.draw do
  scope module: :ai_helper, path: "/ai-helper", defaults: { format: :json } do
    post "suggest" => "assistant#suggest"
  end

  namespace :admin do
    resources :plans, only: %i[index show update]
  end

  get "/contributors" => "subscribe#contributors"
  resource :vote
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            assets = root / "app" / "assets" / "javascripts"
            assets.mkdir(parents=True)
            (assets / "demo.js").write_text(
                """
import { ajax } from "discourse/lib/ajax";

ajax("/demo/ai-helper/suggest", { type: "POST" });
ajax("/demo/admin/plans.json");
ajax("/demo/admin/plans/:id.json");
ajax("/demo/admin/plans/:id.json", { type: "PUT" });
ajax("/demo/contributors");
ajax("/demo/vote");
ajax("/demo/vote", { type: "DELETE" });
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("POST", "/demo/ai-helper/suggest", "assistant#suggest"), routes)
            self.assertIn(("GET", "/demo/admin/plans", "plans#index"), routes)
            self.assertIn(("GET", "/demo/admin/plans/{id}", "plans#show"), routes)
            self.assertIn(("PUT", "/demo/admin/plans/{id}", "plans#update"), routes)
            self.assertIn(("GET", "/demo/contributors", "subscribe#contributors"), routes)
            self.assertIn(("GET", "/demo/vote", "vote#show"), routes)
            self.assertIn(("DELETE", "/demo/vote", "vote#destroy"), routes)
            self.assertNotIn(("POST", "/ai-helper/suggest", "assistant#suggest"), routes)

            calls = {(call.method, call.endpoint, call.matched_route) for call in facts.api_calls}
            self.assertIn(("POST", "/demo/ai-helper/suggest", "POST /demo/ai-helper/suggest"), calls)
            self.assertIn(("GET", "/demo/admin/plans.json", "GET /demo/admin/plans"), calls)
            self.assertIn(("GET", "/demo/admin/plans/:id.json", "GET /demo/admin/plans/{id}"), calls)
            self.assertIn(("PUT", "/demo/admin/plans/:id.json", "PUT /demo/admin/plans/{id}"), calls)
            self.assertIn(("GET", "/demo/contributors", "GET /demo/contributors"), calls)
            self.assertIn(("GET", "/demo/vote", "GET /demo/vote"), calls)
            self.assertIn(("DELETE", "/demo/vote", "DELETE /demo/vote"), calls)


if __name__ == "__main__":
    unittest.main()
