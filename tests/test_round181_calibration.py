from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round181RailsEngineFileCalibrationTests(unittest.TestCase):
    def test_rails_engine_rb_routes_are_scanned_and_linked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'rails'\n", encoding="utf-8")

            engine_dir = root / "plugins" / "zendesk-plugin" / "lib" / "zendesk_plugin"
            engine_dir.mkdir(parents=True)
            (engine_dir / "engine.rb").write_text(
                """
# frozen_string_literal: true

module ZendeskPlugin
  class Engine < ::Rails::Engine
    config.after_initialize do
      Discourse::Application.routes.append do
        post "/zendesk-plugin/issues" => "zendesk_plugin/issues#create",
             :constraints => StaffConstraint.new
        put "/zendesk-plugin/sync" => "zendesk_plugin/sync#webhook"
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
            (assets / "zendesk.js").write_text(
                """
import { ajax } from "discourse/lib/ajax";

ajax("/zendesk-plugin/issues", { type: "POST" });
ajax("/zendesk-plugin/sync", { type: "PUT" });
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.method, route.path, route.handler, route.evidence.file) for route in facts.api_routes}
            self.assertIn(
                (
                    "POST",
                    "/zendesk-plugin/issues",
                    "zendesk_plugin/issues#create",
                    "plugins/zendesk-plugin/lib/zendesk_plugin/engine.rb",
                ),
                routes,
            )
            self.assertIn(("PUT", "/zendesk-plugin/sync", "zendesk_plugin/sync#webhook", "plugins/zendesk-plugin/lib/zendesk_plugin/engine.rb"), routes)

            calls = {(call.method, call.endpoint, call.matched_route) for call in facts.api_calls}
            self.assertIn(("POST", "/zendesk-plugin/issues", "POST /zendesk-plugin/issues"), calls)
            self.assertIn(("PUT", "/zendesk-plugin/sync", "PUT /zendesk-plugin/sync"), calls)


if __name__ == "__main__":
    unittest.main()
