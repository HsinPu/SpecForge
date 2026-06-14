from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round169RailsLoopTemplateCalibrationTests(unittest.TestCase):
    def test_rails_word_loop_templates_expand_routes_and_link_frontend_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'rails'\n", encoding="utf-8")
            (root / "config").mkdir()
            (root / "config" / "routes.rb").write_text(
                """
Rails.application.routes.draw do
  %w[users u].each_with_index do |root_path, index|
    resources :users, only: %i[create], path: root_path do
      collection do
        get "check_username"
      end
    end

    post "#{root_path}/confirm-session" => "users#confirm_session"
    post "#{root_path}/create_second_factor_security_key" =>
           "users#create_second_factor_security_key"
    get "#{root_path}/:username/user-menu-bookmarks" => "users#user_menu_bookmarks"
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            assets = root / "app" / "assets" / "javascripts"
            assets.mkdir(parents=True)
            (assets / "users.js").write_text(
                """
import { ajax } from "discourse/lib/ajax";

ajax("/u/confirm-session.json", { type: "POST" });
ajax("/u/create_second_factor_security_key.json", { type: "POST" });
ajax("/u/:param/user-menu-bookmarks");
ajax("/users/confirm-session.json", { type: "POST" });
ajax("/u/check_username.json");
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("POST", "/u/confirm-session", "users#confirm_session"), routes)
            self.assertIn(("POST", "/users/confirm-session", "users#confirm_session"), routes)
            self.assertIn(
                ("POST", "/u/create_second_factor_security_key", "users#create_second_factor_security_key"),
                routes,
            )
            self.assertIn(("GET", "/u/:username/user-menu-bookmarks", "users#user_menu_bookmarks"), routes)
            self.assertIn(("GET", "/u/check_username", "users#check_username"), routes)

            calls = {(call.method, call.endpoint, call.matched_route) for call in facts.api_calls}
            self.assertIn(("POST", "/u/confirm-session.json", "POST /u/confirm-session"), calls)
            self.assertIn(
                (
                    "POST",
                    "/u/create_second_factor_security_key.json",
                    "POST /u/create_second_factor_security_key",
                ),
                calls,
            )
            self.assertIn(
                ("GET", "/u/:param/user-menu-bookmarks", "GET /u/:username/user-menu-bookmarks"),
                calls,
            )
            self.assertIn(("POST", "/users/confirm-session.json", "POST /users/confirm-session"), calls)
            self.assertIn(("GET", "/u/check_username.json", "GET /u/check_username"), calls)


if __name__ == "__main__":
    unittest.main()
