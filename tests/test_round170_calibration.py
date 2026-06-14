from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round170RailsCollectionResourceCalibrationTests(unittest.TestCase):
    def test_rails_empty_routes_and_collection_nested_resources_link_admin_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'rails'\n", encoding="utf-8")
            (root / "config").mkdir()
            (root / "config" / "routes.rb").write_text(
                """
Rails.application.routes.draw do
  namespace :admin do
    get "" => "admin#index"

    resources :site_settings, only: %i[index update]

    resources :api, only: [:index] do
      collection do
        resources :keys, controller: "api", only: %i[index create update destroy] do
          collection { get "scopes" => "api#scopes" }
        end
      end
    end

    resources :backups, only: %i[index] do
      member do
        put "" => "backups#email"
        delete "" => "backups#destroy"
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

ajax("/admin");
ajax("/admin/site_settings/welcome_banner_image", { type: "PUT" });
ajax("/admin/api/keys/scopes.json");
ajax("/admin/backups/:filename", { type: "PUT" });
ajax("/admin/backups/:filename", { type: "DELETE" });
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("GET", "/admin", "admin#index"), routes)
            self.assertIn(("PUT", "/admin/site_settings/{id}", "site_settings#update"), routes)
            self.assertIn(("GET", "/admin/api/keys/scopes", "api#scopes"), routes)
            self.assertIn(("PUT", "/admin/backups/{id}", "backups#email"), routes)
            self.assertIn(("DELETE", "/admin/backups/{id}", "backups#destroy"), routes)
            self.assertNotIn(("GET", "/admin/api/{id}/keys/scopes", "api#scopes"), routes)

            calls = {(call.method, call.endpoint, call.matched_route) for call in facts.api_calls}
            self.assertIn(("GET", "/admin", "GET /admin"), calls)
            self.assertIn(("PUT", "/admin/site_settings/welcome_banner_image", "PUT /admin/site_settings/{id}"), calls)
            self.assertIn(("GET", "/admin/api/keys/scopes.json", "GET /admin/api/keys/scopes"), calls)
            self.assertIn(("PUT", "/admin/backups/:filename", "PUT /admin/backups/{id}"), calls)
            self.assertIn(("DELETE", "/admin/backups/:filename", "DELETE /admin/backups/{id}"), calls)


if __name__ == "__main__":
    unittest.main()
