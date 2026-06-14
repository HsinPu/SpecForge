from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round159DiscourseAjaxCalibrationTests(unittest.TestCase):
    def test_discourse_ajax_literal_calls_link_to_rails_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'rails'\n", encoding="utf-8")
            (root / "package.json").write_text('{"dependencies":{"ember-source":"^6.0.0"}}\n', encoding="utf-8")

            config = root / "config"
            config.mkdir()
            (config / "routes.rb").write_text(
                """
Rails.application.routes.draw do
  post "/uploads/lookup-urls", to: "uploads#lookup_urls"
  get "/onebox", to: "onebox#show"
  post "/chat/api/direct-message-channels.json", to: "chat/direct_message_channels#create"
  get "/chat/direct_messages.json", to: "chat/direct_messages#index"
  get "/admin/config/site_settings", to: "admin/config#site_settings"
  get "/posts/:id", to: "posts#show"
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            frontend = root / "frontend" / "discourse" / "app"
            frontend.mkdir(parents=True)
            (frontend / "api.gjs").write_text(
                """
import { ajax } from "discourse/lib/ajax";

export function lookupUploads(urls) {
  return ajax("/uploads/lookup-urls", {
    type: "POST",
    data: { short_urls: urls },
  });
}

export function onebox(url) {
  return ajax("/onebox", {
    dataType: "html",
    data: { url },
  });
}

export function createDmChannel(targets) {
  return ajax("/chat/api/direct-message-channels.json", {
    method: "POST",
    data: { target_usernames: targets.usernames },
  });
}

export function directMessages() {
  return ajax("/chat/direct_messages.json", {
    data: { usernames: "sam" },
  });
}

export function siteSettings() {
  return ajax("/admin/config/site_settings.json");
}

export function post(postModel) {
  return ajax(`/posts/${postModel.id}`);
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            calls = {(call.client, call.method, call.endpoint, call.matched_route) for call in facts.api_calls}
            self.assertIn(("ajax", "POST", "/uploads/lookup-urls", "POST /uploads/lookup-urls"), calls)
            self.assertIn(("ajax", "GET", "/onebox", "GET /onebox"), calls)
            self.assertIn(("ajax", "POST", "/chat/api/direct-message-channels.json", "POST /chat/api/direct-message-channels.json"), calls)
            self.assertIn(("ajax", "GET", "/chat/direct_messages.json", "GET /chat/direct_messages.json"), calls)
            self.assertIn(("ajax", "GET", "/admin/config/site_settings.json", "GET /admin/config/site_settings"), calls)
            self.assertIn(("ajax", "GET", "/posts/:id", "GET /posts/:id"), calls)

            links = {(link.method, link.endpoint, link.matched_route, link.match_type, link.confidence) for link in facts.api_links}
            self.assertIn(("POST", "/uploads/lookup-urls", "/uploads/lookup-urls", "exact", "high"), links)
            self.assertIn(("GET", "/onebox", "/onebox", "exact", "high"), links)
            self.assertIn(("POST", "/chat/api/direct-message-channels.json", "/chat/api/direct-message-channels.json", "exact", "high"), links)
            self.assertIn(("GET", "/admin/config/site_settings.json", "/admin/config/site_settings", "format-suffix", "medium"), links)
            self.assertIn(("GET", "/posts/:id", "/posts/:id", "exact", "high"), links)


if __name__ == "__main__":
    unittest.main()
