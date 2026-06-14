from __future__ import annotations

import unittest

from specforge.extractors.api_links import build_api_links
from specforge.models import ApiCallFact, ApiRouteFact, Evidence


class Round166RailsAnchoredParamLinkCalibrationTests(unittest.TestCase):
    def test_rails_text_id_params_require_static_anchors_before_and_after(self) -> None:
        routes = [
            ApiRouteFact(
                method="PUT",
                path="/admin/site_settings/{id}/user_count",
                handler="site_settings#user_count",
                framework="rails",
                kind="rails-route",
                evidence=Evidence(file="config/routes.rb", kind="backend-route", line_start=10),
            ),
            ApiRouteFact(
                method="GET",
                path="/admin/users/{id}",
                handler="users#show",
                framework="rails",
                kind="rails-route",
                evidence=Evidence(file="config/routes.rb", kind="backend-route", line_start=20),
            ),
            ApiRouteFact(
                method="GET",
                path="/admin/users/:id/:username",
                handler="users#show",
                framework="rails",
                kind="rails-route",
                evidence=Evidence(file="config/routes.rb", kind="backend-route", line_start=25),
            ),
            ApiRouteFact(
                method="PUT",
                path="/admin/users/{id}/anonymize",
                handler="users#anonymize",
                framework="rails",
                kind="rails-route",
                evidence=Evidence(file="config/routes.rb", kind="backend-route", line_start=26),
            ),
            ApiRouteFact(
                method="GET",
                path="/{id}/details",
                handler="short#details",
                framework="rails",
                kind="rails-route",
                evidence=Evidence(file="config/routes.rb", kind="backend-route", line_start=30),
            ),
        ]
        calls = [
            ApiCallFact(
                path="admin-fonts-form.gjs",
                endpoint="/admin/site_settings/default_text_size/user_count.json",
                method="PUT",
                client="ajax",
                evidence=Evidence(file="admin-fonts-form.gjs", kind="frontend-api-call", line_start=5),
            ),
            ApiCallFact(
                path="admin-user.js",
                endpoint="/admin/users/current.json",
                method="GET",
                client="ajax",
                evidence=Evidence(file="admin-user.js", kind="frontend-api-call", line_start=6),
            ),
            ApiCallFact(
                path="admin-user.js",
                endpoint="/admin/users/:id/anonymize.json",
                method="PUT",
                client="ajax",
                evidence=Evidence(file="admin-user.js", kind="frontend-api-call", line_start=8),
            ),
            ApiCallFact(
                path="short.js",
                endpoint="/current/details.json",
                method="GET",
                client="ajax",
                evidence=Evidence(file="short.js", kind="frontend-api-call", line_start=9),
            ),
        ]

        links, linked_calls = build_api_links(calls, routes)

        by_endpoint = {link.endpoint: link for link in links}
        site_setting_link = by_endpoint["/admin/site_settings/default_text_size/user_count.json"]
        self.assertEqual("/admin/site_settings/{id}/user_count", site_setting_link.matched_route)
        self.assertEqual("rails-anchored-param-format-suffix", site_setting_link.match_type)
        self.assertEqual("low", site_setting_link.confidence)

        self.assertIsNone(by_endpoint["/admin/users/current.json"].matched_route)
        self.assertEqual("unmatched", by_endpoint["/admin/users/current.json"].match_type)
        user_action_link = by_endpoint["/admin/users/:id/anonymize.json"]
        self.assertEqual("/admin/users/{id}/anonymize", user_action_link.matched_route)
        self.assertEqual("param-format-suffix", user_action_link.match_type)
        self.assertIsNone(by_endpoint["/current/details.json"].matched_route)
        self.assertEqual("unmatched", by_endpoint["/current/details.json"].match_type)

        linked_by_endpoint = {call.endpoint: call for call in linked_calls}
        self.assertEqual(
            "PUT /admin/site_settings/{id}/user_count",
            linked_by_endpoint["/admin/site_settings/default_text_size/user_count.json"].matched_route,
        )


if __name__ == "__main__":
    unittest.main()
