from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round182PrivateApiWrapperCalibrationTests(unittest.TestCase):
    def test_private_wrapper_base_path_links_to_rails_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'rails'\n", encoding="utf-8")
            (root / "package.json").write_text('{"dependencies":{"ember-source":"^6.0.0"}}\n', encoding="utf-8")

            config = root / "plugins" / "chat" / "config"
            config.mkdir(parents=True)
            (config / "routes.rb").write_text(
                """
Discourse::Application.routes.draw do
  scope "/chat/admin" do
    post "export/messages" => "export#export_messages"
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            frontend = root / "plugins" / "chat" / "assets" / "javascripts" / "discourse" / "services"
            frontend.mkdir(parents=True)
            (frontend / "chat-admin-api.js").write_text(
                """
import Service from "@ember/service";
import { ajax } from "discourse/lib/ajax";

export default class ChatAdminApi extends Service {
  async exportMessages() {
    await this.#post(`/export/messages`);
  }

  get #basePath() {
    return "/chat/admin";
  }

  #post(endpoint, data = {}) {
    return ajax(`${this.#basePath}${endpoint}`, {
      type: "POST",
      data,
    });
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            calls = {(call.method, call.endpoint, call.client, call.context, call.matched_route) for call in facts.api_calls}
            self.assertIn(
                (
                    "POST",
                    "/chat/admin/export/messages",
                    "this.#post",
                    "private-api-service-wrapper",
                    "POST /chat/admin/export/messages",
                ),
                calls,
            )
            self.assertNotIn(
                ("POST", "/export/messages", "legacy-api-method", "source", None),
                calls,
            )

            links = {(link.method, link.endpoint, link.matched_route, link.match_type, link.confidence) for link in facts.api_links}
            self.assertIn(
                ("POST", "/chat/admin/export/messages", "/chat/admin/export/messages", "exact", "high"),
                links,
            )


if __name__ == "__main__":
    unittest.main()
