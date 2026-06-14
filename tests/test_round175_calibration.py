from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round175RailsMultilineScopeCalibrationTests(unittest.TestCase):
    def test_rails_multiline_quoted_scope_prefixes_nested_json_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'rails'\n", encoding="utf-8")

            plugin = root / "plugins" / "demo-workflows"
            config = plugin / "config"
            config.mkdir(parents=True)
            (config / "routes.rb").write_text(
                """
# frozen_string_literal: true

DemoWorkflows::Engine.routes.draw do
  scope "/admin/plugins/demo-workflows",
        as: "admin_demo_workflows",
        constraints: AdminConstraint.new do
    scope format: :json do
      get "/workflows" => "workflows#index"
      post "/workflows" => "workflows#create"
      put "/workflows/:id" => "workflows#update"
      post "/workflows/:id/discard-draft" => "workflows#discard_draft"
      get "/variables" => "variables#index"
    end
  end
end

Discourse::Application.routes.draw { mount ::DemoWorkflows::Engine, at: "/" }
""".strip()
                + "\n",
                encoding="utf-8",
            )

            assets = root / "app" / "assets" / "javascripts"
            assets.mkdir(parents=True)
            (assets / "demo-workflows.js").write_text(
                """
fetch("/admin/plugins/demo-workflows/workflows.json");
fetch("/admin/plugins/demo-workflows/workflows.json", { method: "POST" });
fetch("/admin/plugins/demo-workflows/workflows/:id.json", { method: "PUT" });
fetch("/admin/plugins/demo-workflows/workflows/:id/discard-draft.json", { method: "POST" });
fetch("/admin/plugins/demo-workflows/variables.json");
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("GET", "/admin/plugins/demo-workflows/workflows", "workflows#index"), routes)
            self.assertIn(("POST", "/admin/plugins/demo-workflows/workflows", "workflows#create"), routes)
            self.assertIn(("PUT", "/admin/plugins/demo-workflows/workflows/:id", "workflows#update"), routes)
            self.assertIn(
                ("POST", "/admin/plugins/demo-workflows/workflows/:id/discard-draft", "workflows#discard_draft"),
                routes,
            )
            self.assertIn(("GET", "/admin/plugins/demo-workflows/variables", "variables#index"), routes)
            self.assertNotIn(("GET", "/workflows", "workflows#index"), routes)

            calls = {(call.method, call.endpoint, call.matched_route) for call in facts.api_calls}
            self.assertIn(
                (
                    "GET",
                    "/admin/plugins/demo-workflows/workflows.json",
                    "GET /admin/plugins/demo-workflows/workflows",
                ),
                calls,
            )
            self.assertIn(
                (
                    "POST",
                    "/admin/plugins/demo-workflows/workflows.json",
                    "POST /admin/plugins/demo-workflows/workflows",
                ),
                calls,
            )
            self.assertIn(
                (
                    "PUT",
                    "/admin/plugins/demo-workflows/workflows/:id.json",
                    "PUT /admin/plugins/demo-workflows/workflows/:id",
                ),
                calls,
            )
            self.assertIn(
                (
                    "POST",
                    "/admin/plugins/demo-workflows/workflows/:id/discard-draft.json",
                    "POST /admin/plugins/demo-workflows/workflows/:id/discard-draft",
                ),
                calls,
            )


if __name__ == "__main__":
    unittest.main()
