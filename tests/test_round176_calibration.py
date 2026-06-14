from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.extractors.api_links import build_api_links
from specforge.models import ApiCallFact, ApiRouteFact, Evidence
from specforge.scanner import scan_project


class Round176RailsApiLinkTailCalibrationTests(unittest.TestCase):
    def test_rails_format_params_and_optional_segments_link_frontend_calls(self) -> None:
        routes = [
            ApiRouteFact(
                method="GET",
                path="/admin/users/:id.json",
                handler="users#show",
                framework="rails",
                kind="rails-route",
                evidence=Evidence(file="config/routes.rb", kind="backend-route", line_start=167),
            ),
            ApiRouteFact(
                method="DELETE",
                path="/admin/email/templates/(:id)",
                handler="email_templates#revert",
                framework="rails",
                kind="rails-route",
                evidence=Evidence(file="config/routes.rb", kind="backend-route", line_start=193),
            ),
            ApiRouteFact(
                method="PUT",
                path="/t/:id/reset-bump-date/(:post_id)",
                handler="topics#reset_bump_date",
                framework="rails",
                kind="rails-route",
                evidence=Evidence(file="config/routes.rb", kind="backend-route", line_start=1449),
            ),
            ApiRouteFact(
                method="POST",
                path="/admin/plugins/data/queries/:id/run",
                handler="query#run",
                framework="rails",
                kind="rails-route",
                evidence=Evidence(file="config/routes.rb", kind="backend-route", line_start=17),
            ),
        ]
        calls = [
            ApiCallFact(
                path="admin-user.js",
                endpoint="/admin/users/:user_id.json",
                method="GET",
                client="ajax",
                evidence=Evidence(file="admin-user.js", kind="frontend-api-call", line_start=21),
            ),
            ApiCallFact(
                path="email-template.js",
                endpoint="/admin/email/templates/:id",
                method="DELETE",
                client="ajax",
                evidence=Evidence(file="email-template.js", kind="frontend-api-call", line_start=7),
            ),
            ApiCallFact(
                path="topic.js",
                endpoint="/t/:id/reset-bump-date",
                method="PUT",
                client="ajax",
                evidence=Evidence(file="topic.js", kind="frontend-api-call", line_start=11),
            ),
            ApiCallFact(
                path="admin-user.js",
                endpoint="/admin/users/current.json",
                method="GET",
                client="ajax",
                evidence=Evidence(file="admin-user.js", kind="frontend-api-call", line_start=30),
            ),
            ApiCallFact(
                path="poll.gjs",
                endpoint="/admin/plugins/data/queries/:queryID/run.csv",
                method="POST",
                client="ajax",
                evidence=Evidence(file="poll.gjs", kind="frontend-api-call", line_start=42),
            ),
        ]

        links, linked_calls = build_api_links(calls, routes)

        by_endpoint = {link.endpoint: link for link in links}
        self.assertEqual("/admin/users/:id.json", by_endpoint["/admin/users/:user_id.json"].matched_route)
        self.assertEqual("param-format-suffix", by_endpoint["/admin/users/:user_id.json"].match_type)

        self.assertEqual(
            "/admin/email/templates/(:id)",
            by_endpoint["/admin/email/templates/:id"].matched_route,
        )
        self.assertEqual("param", by_endpoint["/admin/email/templates/:id"].match_type)

        self.assertEqual(
            "/t/:id/reset-bump-date/(:post_id)",
            by_endpoint["/t/:id/reset-bump-date"].matched_route,
        )
        self.assertEqual("param", by_endpoint["/t/:id/reset-bump-date"].match_type)

        self.assertEqual(
            "/admin/plugins/data/queries/:id/run",
            by_endpoint["/admin/plugins/data/queries/:queryID/run.csv"].matched_route,
        )
        self.assertEqual(
            "param-format-suffix",
            by_endpoint["/admin/plugins/data/queries/:queryID/run.csv"].match_type,
        )

        self.assertIsNone(by_endpoint["/admin/users/current.json"].matched_route)
        self.assertEqual("unmatched", by_endpoint["/admin/users/current.json"].match_type)

        linked_by_endpoint = {call.endpoint: call for call in linked_calls}
        self.assertEqual(
            "GET /admin/users/:id.json",
            linked_by_endpoint["/admin/users/:user_id.json"].matched_route,
        )
        self.assertEqual(
            "DELETE /admin/email/templates/(:id)",
            linked_by_endpoint["/admin/email/templates/:id"].matched_route,
        )

    def test_rails_inline_collection_symbol_routes_are_scanned_and_linked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'rails'\n", encoding="utf-8")
            (root / "config").mkdir()
            (root / "config" / "routes.rb").write_text(
                """
Rails.application.routes.draw do
  scope "/admin/plugins/demo-ai" do
    resources :ai_llms,
              only: %i[index create update destroy],
              path: "ai-llms",
              controller: "admin/ai_llms" do
      collection { post :test }
    end
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            assets = root / "app" / "assets" / "javascripts"
            assets.mkdir(parents=True)
            (assets / "ai-llm.js").write_text(
                """
import { ajax } from "discourse/lib/ajax";

ajax("/admin/plugins/demo-ai/ai-llms/test.json", { type: "POST" });
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("POST", "/admin/plugins/demo-ai/ai-llms/test", "admin/ai_llms#test"), routes)

            calls = {(call.method, call.endpoint, call.matched_route) for call in facts.api_calls}
            self.assertIn(
                (
                    "POST",
                    "/admin/plugins/demo-ai/ai-llms/test.json",
                    "POST /admin/plugins/demo-ai/ai-llms/test",
                ),
                calls,
            )


if __name__ == "__main__":
    unittest.main()
