from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round130MastodonRailsHamlCalibrationTests(unittest.TestCase):
    def test_rails_route_files_are_not_sinatra_and_haml_forms_are_extracted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            routes = root / "config" / "routes"
            views = root / "app" / "views" / "auth" / "sessions"
            admin_views = root / "app" / "views" / "admin" / "accounts"
            routes.mkdir(parents=True)
            views.mkdir(parents=True)
            admin_views.mkdir(parents=True)
            (root / "Gemfile").write_text(
                """
source 'https://rubygems.org'
gem 'rails'
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "config" / "routes.rb").write_text(
                """
Rails.application.routes.draw do
  draw :admin
end
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (routes / "admin.rb").write_text(
                """
namespace :admin do
  get 'dashboard', to: 'dashboard#index'
  get 'settings'
end
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (views / "new.html.haml").write_text(
                """
= simple_form_for(resource, as: resource_name, url: session_path(resource_name)) do |f|
  = f.input :email
  = f.input :password
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (admin_views / "index.html.haml").write_text(
                """
= form_with url: admin_accounts_url, method: :get, class: :simple_form do |form|
  = form.select :origin, []
  = form.text_field key
  = hidden_field_tag :page, params[:page]
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("rails", frameworks)
            self.assertNotIn("sinatra", frameworks)
            self.assertFalse(any(route.framework == "sinatra" for route in facts.api_routes))
            self.assertIn(
                ("rails", "GET", "/admin/dashboard", "dashboard#index"),
                {(route.framework, route.method, route.path, route.handler) for route in facts.api_routes},
            )

            forms = {(form.method, form.action, tuple(form.fields), form.source) for form in facts.forms}
            self.assertIn(
                ("POST", "rails-helper:session_path", ("email", "password"), "app/views/auth/sessions/new.html.haml"),
                forms,
            )
            self.assertIn(
                ("GET", "rails-helper:admin_accounts_url", ("origin", "key", "page"), "app/views/admin/accounts/index.html.haml"),
                forms,
            )


if __name__ == "__main__":
    unittest.main()
