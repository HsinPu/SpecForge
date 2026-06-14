from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round168RailsResourcePathAliasCalibrationTests(unittest.TestCase):
    def test_rails_resource_path_aliases_keep_controller_and_link_frontend_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'rails'\n", encoding="utf-8")
            (root / "config").mkdir()
            (root / "config" / "routes.rb").write_text(
                """
Rails.application.routes.draw do
  namespace :admin do
    resources :email_logs, only: :index, path: "/email-logs" do
      collection do
        get "incoming/:id" => "email_logs#incoming"
      end
    end

    scope "/customize" do
      resources :form_templates, path: "/form-templates" do
        collection { get "preview" => "form_templates#preview" }
      end
    end
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            assets = root / "app" / "assets" / "javascripts"
            assets.mkdir(parents=True)
            (assets / "admin.js").write_text(
                """
import { ajax } from "discourse/lib/ajax";

ajax("/admin/email-logs/incoming/:id.json");
ajax("/admin/customize/form-templates.json");
ajax("/admin/customize/form-templates.json", { type: "POST" });
ajax("/admin/customize/form-templates/:id.json", { type: "PUT" });
ajax("/admin/customize/form-templates/:id.json", { type: "DELETE" });
ajax("/admin/customize/form-templates/preview.json");
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("GET", "/admin/email-logs", "email_logs#index"), routes)
            self.assertIn(("GET", "/admin/email-logs/incoming/:id", "email_logs#incoming"), routes)
            self.assertIn(("GET", "/admin/customize/form-templates", "form_templates#index"), routes)
            self.assertIn(("POST", "/admin/customize/form-templates", "form_templates#create"), routes)
            self.assertIn(("PUT", "/admin/customize/form-templates/{id}", "form_templates#update"), routes)
            self.assertIn(("DELETE", "/admin/customize/form-templates/{id}", "form_templates#destroy"), routes)
            self.assertIn(("GET", "/admin/customize/form-templates/preview", "form_templates#preview"), routes)

            calls = {(call.method, call.endpoint, call.matched_route) for call in facts.api_calls}
            self.assertIn(("GET", "/admin/email-logs/incoming/:id.json", "GET /admin/email-logs/incoming/:id"), calls)
            self.assertIn(("GET", "/admin/customize/form-templates.json", "GET /admin/customize/form-templates"), calls)
            self.assertIn(("POST", "/admin/customize/form-templates.json", "POST /admin/customize/form-templates"), calls)
            self.assertIn(("PUT", "/admin/customize/form-templates/:id.json", "PUT /admin/customize/form-templates/{id}"), calls)
            self.assertIn(("DELETE", "/admin/customize/form-templates/:id.json", "DELETE /admin/customize/form-templates/{id}"), calls)
            self.assertIn(("GET", "/admin/customize/form-templates/preview.json", "GET /admin/customize/form-templates/preview"), calls)


if __name__ == "__main__":
    unittest.main()
