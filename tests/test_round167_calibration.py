from __future__ import annotations

import unittest

from specforge.extractors.api_links import build_api_links
from specforge.models import ApiCallFact, ApiRouteFact, Evidence


class Round167RailsOptionalSegmentCalibrationTests(unittest.TestCase):
    def test_rails_optional_route_segments_match_omitted_and_present_paths(self) -> None:
        routes = [
            ApiRouteFact(
                method="GET",
                path="/color-scheme-stylesheet/:id(/:theme_id)",
                handler="stylesheets#color_scheme",
                framework="rails",
                kind="rails-route",
                evidence=Evidence(file="config/routes.rb", kind="backend-route", line_start=1088),
            ),
        ]
        calls = [
            ApiCallFact(
                path="color-scheme-manager.js",
                endpoint="/color-scheme-stylesheet/:id.json",
                method="GET",
                client="ajax",
                evidence=Evidence(file="color-scheme-manager.js", kind="frontend-api-call", line_start=72),
            ),
            ApiCallFact(
                path="theme-preview.js",
                endpoint="/color-scheme-stylesheet/:id/:theme_id.json",
                method="GET",
                client="ajax",
                evidence=Evidence(file="theme-preview.js", kind="frontend-api-call", line_start=14),
            ),
            ApiCallFact(
                path="unrelated.js",
                endpoint="/color-scheme-stylesheet.json",
                method="GET",
                client="ajax",
                evidence=Evidence(file="unrelated.js", kind="frontend-api-call", line_start=5),
            ),
        ]

        links, linked_calls = build_api_links(calls, routes)

        by_endpoint = {link.endpoint: link for link in links}
        omitted_link = by_endpoint["/color-scheme-stylesheet/:id.json"]
        self.assertEqual("/color-scheme-stylesheet/:id(/:theme_id)", omitted_link.matched_route)
        self.assertEqual("param-format-suffix", omitted_link.match_type)
        self.assertEqual("medium", omitted_link.confidence)

        present_link = by_endpoint["/color-scheme-stylesheet/:id/:theme_id.json"]
        self.assertEqual("/color-scheme-stylesheet/:id(/:theme_id)", present_link.matched_route)
        self.assertEqual("param-format-suffix", present_link.match_type)

        self.assertIsNone(by_endpoint["/color-scheme-stylesheet.json"].matched_route)
        self.assertEqual("unmatched", by_endpoint["/color-scheme-stylesheet.json"].match_type)

        linked_by_endpoint = {call.endpoint: call for call in linked_calls}
        self.assertEqual(
            "GET /color-scheme-stylesheet/:id(/:theme_id)",
            linked_by_endpoint["/color-scheme-stylesheet/:id.json"].matched_route,
        )


if __name__ == "__main__":
    unittest.main()
