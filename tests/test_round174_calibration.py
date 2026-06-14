from __future__ import annotations

import unittest

from specforge.extractors.api_links import build_api_links
from specforge.extractors.relationship_insights import build_contract_gaps
from specforge.gaps import detect_gaps
from specforge.models import ApiCallFact, ApiRouteFact, Evidence, ProjectFacts
from specforge.renderers.backend import render_api_links
from specforge.renderers.frontend import render_api_calls
from specforge.renderers.rebuild import render_quality_report


class Round174ExternalApiClassificationCalibrationTests(unittest.TestCase):
    def test_external_dynamic_and_helper_calls_are_not_backend_route_gaps(self) -> None:
        call_evidence = Evidence("src/client.js", "api-call", 10, 10)
        route_evidence = Evidence("src/routes.js", "backend-route", 3, 3)
        calls = [
            ApiCallFact(
                path="src/client.js",
                endpoint="https://api.openai.com/v1/images/generations",
                method="POST",
                client="fetch",
                evidence=call_evidence,
            ),
            ApiCallFact(
                path="src/client.js",
                endpoint="dynamic:url",
                method="GET",
                client="fetch",
                evidence=Evidence("src/client.js", "api-call", 11, 11),
            ),
            ApiCallFact(
                path="src/client.js",
                endpoint="/message-bus/${clientId}/poll",
                method="POST",
                client="fetch",
                evidence=Evidence("src/client.js", "api-call", 12, 12),
            ),
            ApiCallFact(
                path="src/template.html.erb",
                endpoint="rails-helper:session_path",
                method="DELETE",
                client="rails-ujs",
                evidence=Evidence("src/template.html.erb", "api-call", 4, 4),
            ),
            ApiCallFact(
                path="src/client.js",
                endpoint="/api/users/123",
                method="GET",
                client="fetch",
                evidence=Evidence("src/client.js", "api-call", 13, 13),
            ),
            ApiCallFact(
                path="src/client.js",
                endpoint="/api/missing",
                method="GET",
                client="fetch",
                evidence=Evidence("src/client.js", "api-call", 14, 14),
            ),
        ]
        routes = [
            ApiRouteFact(
                method="GET",
                path="/api/users/{id}",
                handler="users#show",
                framework="rails",
                kind="rails-route",
                evidence=route_evidence,
            )
        ]

        links, linked_calls = build_api_links(calls, routes)
        by_endpoint = {link.endpoint: link for link in links}
        linked_by_endpoint = {call.endpoint: call for call in linked_calls}

        self.assertEqual("external-api", by_endpoint["https://api.openai.com/v1/images/generations"].target_kind)
        self.assertEqual("external-url", by_endpoint["https://api.openai.com/v1/images/generations"].match_type)
        self.assertEqual("api.openai.com", by_endpoint["https://api.openai.com/v1/images/generations"].matched_framework)
        self.assertIsNone(by_endpoint["https://api.openai.com/v1/images/generations"].matched_route)

        self.assertEqual("dynamic-endpoint", by_endpoint["dynamic:url"].target_kind)
        self.assertEqual("dynamic-endpoint", by_endpoint["/message-bus/${clientId}/poll"].target_kind)
        self.assertEqual("framework-helper", by_endpoint["rails-helper:session_path"].target_kind)
        self.assertEqual("backend-route", by_endpoint["/api/users/123"].target_kind)
        self.assertEqual("/api/users/{id}", by_endpoint["/api/users/123"].matched_route)
        self.assertEqual("backend-route", by_endpoint["/api/missing"].target_kind)
        self.assertIsNone(by_endpoint["/api/missing"].matched_route)

        self.assertEqual("external-api", linked_by_endpoint["https://api.openai.com/v1/images/generations"].target_kind)
        self.assertEqual("dynamic-endpoint", linked_by_endpoint["dynamic:url"].target_kind)
        self.assertEqual("framework-helper", linked_by_endpoint["rails-helper:session_path"].target_kind)
        self.assertEqual("GET /api/users/{id}", linked_by_endpoint["/api/users/123"].matched_route)

        facts = ProjectFacts(
            root=".",
            name="external-demo",
            api_routes=routes,
            api_calls=linked_calls,
            api_links=links,
            contract_gaps=build_contract_gaps([], links, routes),
        )

        gaps = detect_gaps(facts)
        api_gap = next(gap for gap in gaps if gap.gap_id == "GAP-012")
        self.assertIn("1 local frontend API call", api_gap.detail)
        self.assertEqual(
            [("unmatched-api-call", "GET /api/missing")],
            [(gap.gap_type, gap.contract) for gap in facts.contract_gaps],
        )

        api_links_md = render_api_links(facts)
        self.assertIn("| Source | Method | Endpoint | Target | Matched Route |", api_links_md)
        self.assertIn("external-api | `external-api` | api.openai.com | external-url | high", api_links_md)
        self.assertIn("dynamic-endpoint | `dynamic-endpoint` | dynamic | dynamic-endpoint | medium", api_links_md)

        api_calls_md = render_api_calls(facts)
        self.assertIn("| Method | Endpoint | Target | Client |", api_calls_md)
        self.assertIn("`https://api.openai.com/v1/images/generations` | external-api |", api_calls_md)

        quality = render_quality_report(facts)
        self.assertIn("- Backend API links unmatched: 1", quality)
        self.assertIn("- External API calls: 1", quality)
        self.assertIn("- Dynamic API endpoints: 2", quality)


if __name__ == "__main__":
    unittest.main()
