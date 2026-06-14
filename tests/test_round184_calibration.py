from __future__ import annotations

import unittest

from specforge.extractors.api_links import build_api_links
from specforge.models import ApiCallFact, ApiRouteFact, Evidence


class Round184StaticPageFamilyCalibrationTests(unittest.TestCase):
    def test_static_page_html_dynamic_path_links_to_static_show_family(self) -> None:
        call = ApiCallFact(
            path="frontend/discourse/app/models/static-page.js",
            endpoint="/:path.html",
            method="GET",
            client="ajax",
            context="source",
            evidence=Evidence("frontend/discourse/app/models/static-page.js", "frontend-api-call", 15, 15),
        )
        routes = [
            ApiRouteFact(
                method="GET",
                path="/privacy",
                handler="static#show",
                framework="rails",
                kind="rails-route",
                evidence=Evidence("config/routes.rb", "backend-route", 598, 598),
            ),
            ApiRouteFact(
                method="GET",
                path="/tos",
                handler="static#show",
                framework="rails",
                kind="rails-route",
                evidence=Evidence("config/routes.rb", "backend-route", 599, 599),
            ),
            ApiRouteFact(
                method="GET",
                path="/users/:id",
                handler="users#show",
                framework="rails",
                kind="rails-route",
                evidence=Evidence("config/routes.rb", "backend-route", 700, 700),
            ),
        ]

        links, linked_calls = build_api_links([call], routes)

        self.assertEqual("/privacy", links[0].matched_route)
        self.assertEqual("static-page-family", links[0].match_type)
        self.assertEqual("low", links[0].confidence)
        self.assertEqual("GET /privacy", linked_calls[0].matched_route)


if __name__ == "__main__":
    unittest.main()
