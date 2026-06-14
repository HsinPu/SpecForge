from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round178RailsHelperLinkCalibrationTests(unittest.TestCase):
    def test_rails_form_helpers_link_to_routes_by_handler_and_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'rails'\n", encoding="utf-8")
            (root / "config").mkdir()
            (root / "config" / "routes.rb").write_text(
                """
Rails.application.routes.draw do
  post "/safe-mode" => "safe_mode#enter", :as => "safe_mode_enter"
  post "email/unsubscribe/:key" => "email#perform_unsubscribe", :as => "email_perform_unsubscribe"
  resources :session, only: %i[create destroy]
  put "/u/admin-login" => "users#admin_login"
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            views = root / "app" / "views"
            (views / "safe_mode").mkdir(parents=True)
            (views / "email").mkdir(parents=True)
            (views / "users").mkdir(parents=True)
            (views / "safe_mode" / "index.html.erb").write_text(
                """
<%= form_tag(safe_mode_enter_path) do %>
  <%= check_box_tag 'no_plugins' %>
<% end %>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (views / "email" / "unsubscribe.html.erb").write_text(
                """
<%= form_tag(session_path(id: current_user.username_lower), method: :delete) do %>
  <%= hidden_field_tag(:return_url, @return_url) %>
<% end %>
<%= form_tag(email_perform_unsubscribe_path(key: params[:key])) do %>
  <%= check_box_tag 'unsubscribe_all' %>
<% end %>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (views / "users" / "admin_login.html.erb").write_text(
                """
<%= form_tag(u_admin_login_path, method: :put) do %>
  <%= text_field_tag(:email) %>
<% end %>
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            calls = {(call.method, call.endpoint, call.matched_route, call.target_kind) for call in facts.api_calls}
            self.assertIn(("POST", "rails-helper:safe_mode_enter_path", "POST /safe-mode", "backend-route"), calls)
            self.assertIn(
                (
                    "POST",
                    "rails-helper:email_perform_unsubscribe_path",
                    "POST /email/unsubscribe/:key",
                    "backend-route",
                ),
                calls,
            )
            self.assertIn(("DELETE", "rails-helper:session_path", "DELETE /session/{id}", "backend-route"), calls)
            self.assertIn(("PUT", "rails-helper:u_admin_login_path", "PUT /u/admin-login", "backend-route"), calls)

            links = {(link.method, link.endpoint, link.matched_route, link.match_type) for link in facts.api_links}
            self.assertIn(("POST", "rails-helper:safe_mode_enter_path", "/safe-mode", "rails-helper"), links)
            self.assertIn(
                (
                    "POST",
                    "rails-helper:email_perform_unsubscribe_path",
                    "/email/unsubscribe/:key",
                    "rails-helper",
                ),
                links,
            )
            self.assertIn(("DELETE", "rails-helper:session_path", "/session/{id}", "rails-helper"), links)
            self.assertIn(("PUT", "rails-helper:u_admin_login_path", "/u/admin-login", "rails-helper"), links)


if __name__ == "__main__":
    unittest.main()
