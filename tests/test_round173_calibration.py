from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round173RailsMountedEngineCalibrationTests(unittest.TestCase):
    def test_rails_custom_engine_routes_are_prefixed_from_multiline_mounts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'rails'\n", encoding="utf-8")

            routes = root / "plugins" / "demo-plugin" / "app" / "routes"
            routes.mkdir(parents=True)
            (routes / "demo_plugin.rb").write_text(
                """
# frozen_string_literal: true

module DemoPlugin
  AdminEngine.routes.draw do
    get "" => "admin#respond"
    get "/providers" => "admin#providers"
    post "/setup-provider" => "admin#setup_provider"
    put "/channels/:id" => "admin#update_channel"
  end

  PublicEngine.routes.draw { get "/:secret" => "public#show" }
end
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (routes / "discourse.rb").write_text(
                """
# frozen_string_literal: true

Discourse::Application.routes.append do
  mount DemoPlugin::AdminEngine,
        at: "/admin/plugins/demo-plugin",
        constraints: AdminConstraint.new
  mount DemoPlugin::PublicEngine, at: "/demo-transcript/"
  post "/legacy/webhook" => "demo/webhooks#create"
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            assets = root / "app" / "assets" / "javascripts"
            assets.mkdir(parents=True)
            (assets / "demo.js").write_text(
                """
fetch("/admin/plugins/demo-plugin/providers.json");
fetch("/admin/plugins/demo-plugin/setup-provider", { method: "POST" });
fetch("/admin/plugins/demo-plugin/channels/:id", { method: "PUT" });
fetch("/demo-transcript/:secret");
fetch("/legacy/webhook", { method: "POST" });
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            api_routes = {(route.framework, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("rails", "GET", "/admin/plugins/demo-plugin", "admin#respond"), api_routes)
            self.assertIn(("rails", "GET", "/admin/plugins/demo-plugin/providers", "admin#providers"), api_routes)
            self.assertIn(("rails", "POST", "/admin/plugins/demo-plugin/setup-provider", "admin#setup_provider"), api_routes)
            self.assertIn(("rails", "PUT", "/admin/plugins/demo-plugin/channels/:id", "admin#update_channel"), api_routes)
            self.assertIn(("rails", "GET", "/demo-transcript/:secret", "public#show"), api_routes)
            self.assertIn(("rails", "POST", "/legacy/webhook", "demo/webhooks#create"), api_routes)
            self.assertFalse(any(route.framework == "sinatra" for route in facts.api_routes))

            calls = {(call.method, call.endpoint, call.matched_route) for call in facts.api_calls}
            self.assertIn(("GET", "/admin/plugins/demo-plugin/providers.json", "GET /admin/plugins/demo-plugin/providers"), calls)
            self.assertIn(("POST", "/admin/plugins/demo-plugin/setup-provider", "POST /admin/plugins/demo-plugin/setup-provider"), calls)
            self.assertIn(("PUT", "/admin/plugins/demo-plugin/channels/:id", "PUT /admin/plugins/demo-plugin/channels/:id"), calls)
            self.assertIn(("GET", "/demo-transcript/:secret", "GET /demo-transcript/:secret"), calls)
            self.assertIn(("POST", "/legacy/webhook", "POST /legacy/webhook"), calls)


if __name__ == "__main__":
    unittest.main()
