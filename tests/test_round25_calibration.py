from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round25CalibrationTests(unittest.TestCase):

    def test_scan_project_reads_split_rails_route_files_and_links_mastodon_api_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                json.dumps({"dependencies": {"react": "^19.0.0"}}),
                encoding="utf-8",
            )
            config = root / "config"
            routes_dir = config / "routes"
            routes_dir.mkdir(parents=True)
            (config / "routes.rb").write_text(
                """
Rails.application.routes.draw do
  scope path: '.well-known' do
    get 'webfinger', to: 'well_known/webfinger#show'
  end

  draw(:api)
end
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (routes_dir / "api.rb").write_text(
                """
namespace :api, format: false do
  namespace :v1 do
    resources :statuses, only: [:show] do
      scope module: :statuses do
        resource :favourite, only: :create
      end
    end

    namespace :accounts do
      resource :lookup, only: :show, controller: :lookup
    end

    resources :accounts, only: [:index, :create, :show] do
      member do
        post :follow
      end
    end

    resources :announcements, only: [:index] do
      scope module: :announcements do
        resources :reactions, only: [:update, :destroy]
      end
    end

    get '/streaming/(*any)', to: 'streaming#index'
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )
            js_dir = root / "app" / "javascript" / "mastodon" / "actions"
            js_dir.mkdir(parents=True)
            (js_dir / "accounts.js").write_text(
                """
import api from '../api';

export const lookup = () => api.get('/api/v1/accounts/lookup');
export const show = id => api.get(`/api/v1/accounts/${id}`);
export const follow = id => api.post(`/api/v1/accounts/${id}/follow`);
export const favourite = status => api().post(`/api/v1/statuses/${status.get('id')}/favourite`);
export const react = (announcementId, name) =>
  api.put(`/api/v1/announcements/${announcementId}/reactions/${name}`);
""".strip()
                + "\n",
                encoding="utf-8",
            )
            stream_dir = root / "app" / "javascript" / "mastodon"
            (stream_dir / "stream.js").write_text(
                """
export const subscribe = (streamingAPIBaseURL, channelName, params) =>
  new EventSource(`${streamingAPIBaseURL}/api/v1/streaming/${channelName}?${params.join('&')}`);
""".strip()
                + "\n",
                encoding="utf-8",
            )
            worker_dir = root / "app" / "javascript" / "mastodon" / "service_worker"
            worker_dir.mkdir(parents=True)
            (worker_dir / "caching.ts").write_text(
                """
export const cacheRoot = cache => {
  cache.put('/', new Response());
  cache.delete('/');
  return GET('/packs-dev/emoji/en.json');
};
""".strip()
                + "\n",
                encoding="utf-8",
            )
            streaming = root / "streaming"
            streaming.mkdir()
            (streaming / "index.js").write_text(
                """
import express from 'express';

const api = express.Router();
api.get('/api/v1/streaming/*splat', (_req, res) => res.end());
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.framework, route.method, route.path) for route in facts.api_routes}
            self.assertIn(("rails", "GET", "/.well-known/webfinger"), routes)
            self.assertNotIn(("rails", "GET", "/path/webfinger"), routes)
            self.assertIn(("rails", "GET", "/api/v1/accounts/lookup"), routes)
            self.assertIn(("rails", "POST", "/api/v1/statuses/{id}/favourite"), routes)
            self.assertIn(("rails", "GET", "/api/v1/accounts/{id}"), routes)
            self.assertIn(("rails", "POST", "/api/v1/accounts/{id}/follow"), routes)
            self.assertIn(("rails", "PUT", "/api/v1/announcements/{id}/reactions/{id}"), routes)
            self.assertIn(("rails", "DELETE", "/api/v1/announcements/{id}/reactions/{id}"), routes)
            self.assertIn(("rails", "GET", "/api/v1/streaming/(*any)"), routes)
            endpoints = {call.endpoint for call in facts.api_calls}
            calls = {(call.client, call.method, call.endpoint) for call in facts.api_calls}
            self.assertIn(("EventSource", "STREAM", "/api/v1/streaming/:channelName"), calls)
            self.assertNotIn("/", endpoints)
            self.assertNotIn("/packs-dev/emoji/en.json", endpoints)
            self.assertNotIn("/api/v1/streaming/*splat", endpoints)

            links = {
                (link.method, link.endpoint): link.matched_route
                for link in facts.api_links
                if link.matched_route
            }
            self.assertEqual("/api/v1/accounts/lookup", links[("GET", "/api/v1/accounts/lookup")])
            self.assertEqual("/api/v1/accounts/{id}", links[("GET", "/api/v1/accounts/:id")])
            self.assertEqual("/api/v1/accounts/{id}/follow", links[("POST", "/api/v1/accounts/:id/follow")])
            self.assertEqual("/api/v1/statuses/{id}/favourite", links[("POST", "/api/v1/statuses/:param/favourite")])
            self.assertEqual(
                "/api/v1/announcements/{id}/reactions/{id}",
                links[("PUT", "/api/v1/announcements/:announcementId/reactions/:name")],
            )
            self.assertEqual("/api/v1/streaming/(*any)", links[("STREAM", "/api/v1/streaming/:channelName")])


if __name__ == "__main__":
    unittest.main()
