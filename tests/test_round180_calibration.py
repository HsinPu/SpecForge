from __future__ import annotations

import unittest

from specforge.extractors.api_links import build_api_links
from specforge.models import ApiCallFact, ApiRouteFact, Evidence


class Round180AdjacentParamOptionalSegmentCalibrationTests(unittest.TestCase):
    def test_adjacent_frontend_params_match_backend_optional_route_segments(self) -> None:
        evidence = Evidence("config/routes.rb", "backend-route", 10, 10)
        routes = [
            ApiRouteFact(
                method="GET",
                path="/color-scheme-stylesheet/:id(/:theme_id)",
                handler="stylesheets#color_scheme",
                framework="rails",
                kind="rails-route",
                evidence=evidence,
            ),
            ApiRouteFact(
                method="GET",
                path="/users/:id",
                handler="users#show",
                framework="rails",
                kind="rails-route",
                evidence=evidence,
            ),
        ]
        calls = [
            ApiCallFact(
                path="app/color.js",
                endpoint="/color-scheme-stylesheet/:colorSchemeId:themeId.json",
                method="GET",
                client="ajax",
                evidence=Evidence("app/color.js", "frontend-api-call", 6, 6),
            ),
            ApiCallFact(
                path="app/users.js",
                endpoint="/users/:id:tab.json",
                method="GET",
                client="ajax",
                evidence=Evidence("app/users.js", "frontend-api-call", 7, 7),
            ),
        ]

        links, linked_calls = build_api_links(calls, routes)

        by_endpoint = {link.endpoint: link for link in links}
        color_link = by_endpoint["/color-scheme-stylesheet/:colorSchemeId:themeId.json"]
        self.assertEqual("/color-scheme-stylesheet/:id(/:theme_id)", color_link.matched_route)
        self.assertEqual("param-format-suffix", color_link.match_type)

        user_link = by_endpoint["/users/:id:tab.json"]
        self.assertIsNone(user_link.matched_route)
        self.assertEqual("unmatched", user_link.match_type)

        linked_by_endpoint = {call.endpoint: call for call in linked_calls}
        self.assertEqual(
            "GET /color-scheme-stylesheet/:id(/:theme_id)",
            linked_by_endpoint["/color-scheme-stylesheet/:colorSchemeId:themeId.json"].matched_route,
        )


if __name__ == "__main__":
    unittest.main()
