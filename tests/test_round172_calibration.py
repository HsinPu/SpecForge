from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round172RailsAbsoluteEngineCalibrationTests(unittest.TestCase):
    def test_rails_absolute_engine_mount_prefixes_nested_namespace_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'rails'\n", encoding="utf-8")

            plugin = root / "plugins" / "chat"
            plugin.mkdir(parents=True)
            (plugin / "plugin.rb").write_text(
                """
# frozen_string_literal: true

Discourse::Application.routes.append do
  mount ::Chat::Engine, at: "/chat"
  get "/admin/plugins/chat/hooks" => "chat/admin/incoming_webhooks#index"
  put "u/:username/preferences/chat" => "users#preferences"
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            config = plugin / "config"
            config.mkdir()
            (config / "routes.rb").write_text(
                """
# frozen_string_literal: true

Chat::Engine.routes.draw do
  namespace :api, defaults: { format: :json } do
    get "/chatables" => "chatables#index"
    get "/channels" => "channels#index"
    post "/direct-message-channels" => "direct_messages#create"
  end

  post "/dismiss-retention-reminder" => "chat#dismiss_retention_reminder"
  put ":chat_channel_id/react/:message_id" => "chat#react"
  post "/:chat_channel_id" => "api/channel_messages#create"
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            assets = root / "app" / "assets" / "javascripts"
            assets.mkdir(parents=True)
            (assets / "chat.js").write_text(
                """
fetch("/chat/api/chatables");
fetch("/chat/api/channels");
fetch("/chat/api/direct-message-channels.json", { method: "POST" });
fetch("/chat/dismiss-retention-reminder", { method: "POST" });
fetch("/chat/:channelId/react/:messageId", { method: "PUT" });
fetch("/chat/:channelId", { method: "POST" });
fetch("/admin/plugins/chat/hooks");
fetch("/u/:username/preferences/chat", { method: "PUT" });
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("GET", "/chat/api/chatables", "chatables#index"), routes)
            self.assertIn(("GET", "/chat/api/channels", "channels#index"), routes)
            self.assertIn(("POST", "/chat/api/direct-message-channels", "direct_messages#create"), routes)
            self.assertIn(("POST", "/chat/dismiss-retention-reminder", "chat#dismiss_retention_reminder"), routes)
            self.assertIn(("PUT", "/chat/:chat_channel_id/react/:message_id", "chat#react"), routes)
            self.assertIn(("POST", "/chat/:chat_channel_id", "api/channel_messages#create"), routes)
            self.assertIn(("GET", "/admin/plugins/chat/hooks", "chat/admin/incoming_webhooks#index"), routes)
            self.assertIn(("PUT", "/u/:username/preferences/chat", "users#preferences"), routes)
            self.assertNotIn(("GET", "/api/chatables", "chatables#index"), routes)
            self.assertFalse(any(route.framework == "sinatra" for route in facts.api_routes))

            calls = {(call.method, call.endpoint, call.matched_route) for call in facts.api_calls}
            self.assertIn(("GET", "/chat/api/chatables", "GET /chat/api/chatables"), calls)
            self.assertIn(("GET", "/chat/api/channels", "GET /chat/api/channels"), calls)
            self.assertIn(("POST", "/chat/api/direct-message-channels.json", "POST /chat/api/direct-message-channels"), calls)
            self.assertIn(("POST", "/chat/dismiss-retention-reminder", "POST /chat/dismiss-retention-reminder"), calls)
            self.assertIn(("PUT", "/chat/:channelId/react/:messageId", "PUT /chat/:chat_channel_id/react/:message_id"), calls)
            self.assertIn(("POST", "/chat/:channelId", "POST /chat/:chat_channel_id"), calls)
            self.assertIn(("GET", "/admin/plugins/chat/hooks", "GET /admin/plugins/chat/hooks"), calls)
            self.assertIn(("PUT", "/u/:username/preferences/chat", "PUT /u/:username/preferences/chat"), calls)


if __name__ == "__main__":
    unittest.main()
