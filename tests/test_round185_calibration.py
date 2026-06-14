from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round185RailsHashRouteCalibrationTests(unittest.TestCase):
    def test_rails_hash_style_verb_routes_expand_loop_variables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'rails'\n", encoding="utf-8")
            (root / "config").mkdir()
            (root / "config" / "routes.rb").write_text(
                """
Rails.application.routes.draw do
  %w[users u].each_with_index do |root_path, index|
    put(
      {
        "#{root_path}/activate-account/:token" => "users#perform_account_activation",
        :constraints => {
          token: /[0-9a-f]+/,
        },
      }.merge(index == 1 ? { as: "perform_activate_account" } : {}),
    )
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            assets = root / "app" / "assets" / "javascripts"
            assets.mkdir(parents=True)
            (assets / "activate-account.js").write_text(
                """
import { ajax } from "discourse/lib/ajax";

ajax(`/u/activate-account/${token}.json`, { type: "PUT" });
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("PUT", "/users/activate-account/:token", "users#perform_account_activation"), routes)
            self.assertIn(("PUT", "/u/activate-account/:token", "users#perform_account_activation"), routes)

            calls = {(call.method, call.endpoint, call.matched_route) for call in facts.api_calls}
            self.assertIn(("PUT", "/u/activate-account/:token.json", "PUT /u/activate-account/:token"), calls)


if __name__ == "__main__":
    unittest.main()
