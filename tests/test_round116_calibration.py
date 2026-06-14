from __future__ import annotations

import sys
import tempfile
import unittest
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round116CalibrationTests(unittest.TestCase):

    def test_rails_realworld_resources_devise_and_links_are_method_aware(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'rails'\ngem 'devise'\n", encoding="utf-8")
            (root / "package.json").write_text(json.dumps({"dependencies": {"@rails/webpacker": "^5.0.0"}}), encoding="utf-8")
            config = root / "config"
            config.mkdir()
            (config / "routes.rb").write_text(
                """
Rails.application.routes.draw do
  scope :api, defaults: { format: :json } do
    devise_for :users, controllers: { sessions: :sessions },
                       path_names: { sign_in: :login }

    resource :user, only: [:show, :update]

    resources :profiles, param: :username, only: [:show] do
      resource :follow, only: [:create, :destroy]
    end

    resources :articles, param: :slug, except: [:edit, :new] do
      resource :favorite, only: [:create, :destroy]
      resources :comments, only: [:create, :index, :destroy]
      get :feed, on: :collection
      put "publish"
      delete "comments/:comment_id" => "comments#remove"
      collection do
        get "search" => "articles#search"
      end
    end

    resources :tags, only: [:index]
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )
            frontend = root / "app" / "javascript"
            frontend.mkdir(parents=True)
            (frontend / "api.js").write_text(
                """
export const login = credentials => fetch('/api/users/login', { method: 'POST', body: JSON.stringify(credentials) });
export const article = slug => fetch(`/api/articles/${slug}`);
export const favorite = slug => fetch(`/api/articles/${slug}/favorite`, { method: 'POST' });
export const comment = (slug, body) => fetch(`/api/articles/${slug}/comments`, { method: 'POST', body: JSON.stringify(body) });
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.framework, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("rails", "POST", "/api/users/login", "sessions#create"), routes)
            self.assertIn(("rails", "DELETE", "/api/users/sign_out", "sessions#destroy"), routes)
            self.assertIn(("rails", "GET", "/api/user", "user#show"), routes)
            self.assertIn(("rails", "PATCH", "/api/user", "user#update"), routes)
            self.assertIn(("rails", "GET", "/api/profiles/{username}", "profiles#show"), routes)
            self.assertIn(("rails", "POST", "/api/profiles/{username}/follow", "follow#create"), routes)
            self.assertIn(("rails", "GET", "/api/articles", "articles#index"), routes)
            self.assertIn(("rails", "POST", "/api/articles", "articles#create"), routes)
            self.assertIn(("rails", "GET", "/api/articles/{slug}", "articles#show"), routes)
            self.assertIn(("rails", "PATCH", "/api/articles/{slug}", "articles#update"), routes)
            self.assertIn(("rails", "DELETE", "/api/articles/{slug}", "articles#destroy"), routes)
            self.assertIn(("rails", "POST", "/api/articles/{slug}/favorite", "favorite#create"), routes)
            self.assertIn(("rails", "GET", "/api/articles/{slug}/comments", "comments#index"), routes)
            self.assertIn(("rails", "POST", "/api/articles/{slug}/comments", "comments#create"), routes)
            self.assertIn(("rails", "DELETE", "/api/articles/{slug}/comments/{id}", "comments#destroy"), routes)
            self.assertIn(("rails", "GET", "/api/articles/feed", "articles#feed"), routes)
            self.assertIn(("rails", "PUT", "/api/articles/{slug}/publish", "articles#publish"), routes)
            self.assertIn(("rails", "DELETE", "/api/articles/{slug}/comments/:comment_id", "comments#remove"), routes)
            self.assertIn(("rails", "GET", "/api/articles/search", "articles#search"), routes)
            self.assertIn(("rails", "GET", "/api/tags", "tags#index"), routes)
            self.assertFalse(any(route.framework == "rails" and route.method == "ANY" for route in facts.api_routes))

            article_route = next(route for route in facts.api_routes if route.path == "/api/articles/{slug}" and route.method == "GET")
            self.assertEqual(["slug"], [param.name for param in article_route.parameters])
            create_comment = next(route for route in facts.api_routes if route.path == "/api/articles/{slug}/comments" and route.method == "POST")
            self.assertEqual("params", create_comment.request_body)

            links = {(link.method, link.endpoint): link.matched_route for link in facts.api_links}
            self.assertEqual("/api/users/login", links[("POST", "/api/users/login")])
            self.assertEqual("/api/articles/{slug}", links[("GET", "/api/articles/:slug")])
            self.assertEqual("/api/articles/{slug}/favorite", links[("POST", "/api/articles/:slug/favorite")])
            self.assertEqual("/api/articles/{slug}/comments", links[("POST", "/api/articles/:slug/comments")])


if __name__ == "__main__":
    unittest.main()
