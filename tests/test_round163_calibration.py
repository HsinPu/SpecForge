from __future__ import annotations

import unittest

from specforge.extractors.api_links import build_api_links
from specforge.models import ApiCallFact, ApiRouteFact, Evidence


class Round163ApiLinkParamCalibrationTests(unittest.TestCase):
    def test_param_links_keep_static_overlap_and_reject_broad_all_param_catch_alls(self) -> None:
        routes = [
            ApiRouteFact(
                method="ANY",
                path="/{lang}/{seName}",
                handler="Catalog#Seo",
                framework="aspnetcore",
                kind="aspnet-route",
                evidence=Evidence(file="RouteProvider.cs", kind="backend-route", line_start=10),
            ),
            ApiRouteFact(
                method="POST",
                path="/Admin/FacebookAuthentication/Configure",
                handler="FacebookAuthentication#Configure",
                framework="aspnetcore",
                kind="aspnet-route",
                evidence=Evidence(file="FacebookAuthenticationController.cs", kind="backend-route", line_start=20),
            ),
            ApiRouteFact(
                method="GET",
                path="/api/users/{id}",
                handler="Users#get",
                framework="express",
                kind="express-route",
                evidence=Evidence(file="server.js", kind="backend-route", line_start=30),
            ),
            ApiRouteFact(
                method="GET",
                path="/{id}",
                handler="Short#get",
                framework="aspnetcore",
                kind="aspnet-route",
                evidence=Evidence(file="ShortController.cs", kind="backend-route", line_start=40),
            ),
        ]
        calls = [
            ApiCallFact(
                path="Views/Configure.cshtml",
                endpoint="/FacebookAuthentication/Configure",
                method="POST",
                client="form",
                trigger="form-submit",
                context="form-submit",
                evidence=Evidence(file="Views/Configure.cshtml", kind="frontend-api-call", line_start=5),
            ),
            ApiCallFact(
                path="src/User.tsx",
                endpoint="/api/users/123",
                method="GET",
                client="fetch",
                evidence=Evidence(file="src/User.tsx", kind="frontend-api-call", line_start=7),
            ),
            ApiCallFact(
                path="src/Short.tsx",
                endpoint="/42",
                method="GET",
                client="fetch",
                evidence=Evidence(file="src/Short.tsx", kind="frontend-api-call", line_start=9),
            ),
        ]

        links, linked_calls = build_api_links(calls, routes)

        by_endpoint = {link.endpoint: link for link in links}
        self.assertIsNone(by_endpoint["/FacebookAuthentication/Configure"].matched_route)
        self.assertEqual("unmatched", by_endpoint["/FacebookAuthentication/Configure"].match_type)

        self.assertEqual("/api/users/{id}", by_endpoint["/api/users/123"].matched_route)
        self.assertEqual("param", by_endpoint["/api/users/123"].match_type)
        self.assertEqual("medium", by_endpoint["/api/users/123"].confidence)

        self.assertEqual("/{id}", by_endpoint["/42"].matched_route)
        self.assertEqual("param", by_endpoint["/42"].match_type)

        linked_by_endpoint = {call.endpoint: call for call in linked_calls}
        self.assertIsNone(linked_by_endpoint["/FacebookAuthentication/Configure"].matched_route)
        self.assertEqual("GET /api/users/{id}", linked_by_endpoint["/api/users/123"].matched_route)


if __name__ == "__main__":
    unittest.main()
