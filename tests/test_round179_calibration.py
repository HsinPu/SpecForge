from __future__ import annotations

import unittest

from specforge.extractors.api_links import build_api_links
from specforge.models import ApiCallFact, ApiRouteFact, Evidence


class Round179StaticChoiceParamCalibrationTests(unittest.TestCase):
    def test_dynamic_frontend_choice_segments_link_to_static_route_families(self) -> None:
        call_evidence = Evidence("app/client.js", "frontend-api-call", 10, 10)
        route_evidence = Evidence("config/routes.rb", "backend-route", 3, 3)
        calls = [
            ApiCallFact(
                path="app/client.js",
                endpoint="/captcha/:captchaRoute/create.json",
                method="POST",
                client="fetch",
                evidence=call_evidence,
            ),
            ApiCallFact(
                path="app/client.js",
                endpoint="/policy/:policyAction",
                method="PUT",
                client="fetch",
                evidence=Evidence("app/client.js", "frontend-api-call", 11, 11),
            ),
            ApiCallFact(
                path="app/client.js",
                endpoint="/admin/email-logs/:status.json",
                method="GET",
                client="fetch",
                evidence=Evidence("app/client.js", "frontend-api-call", 12, 12),
            ),
            ApiCallFact(
                path="app/client.js",
                endpoint="/posts/:id/:field",
                method="PUT",
                client="fetch",
                evidence=Evidence("app/client.js", "frontend-api-call", 13, 13),
            ),
            ApiCallFact(
                path="app/client.js",
                endpoint="/users/:id",
                method="GET",
                client="fetch",
                evidence=Evidence("app/client.js", "frontend-api-call", 14, 14),
            ),
        ]
        routes = [
            ApiRouteFact("POST", "/captcha/hcaptcha/create", "hcaptcha#create", "rails", "rails-route", route_evidence),
            ApiRouteFact("POST", "/captcha/recaptcha/create", "recaptcha#create", "rails", "rails-route", route_evidence),
            ApiRouteFact("PUT", "/policy/accept", "policy#accept", "rails", "rails-route", route_evidence),
            ApiRouteFact("PUT", "/policy/unaccept", "policy#unaccept", "rails", "rails-route", route_evidence),
            ApiRouteFact("GET", "/admin/email-logs/sent", "email_logs#sent", "rails", "rails-route", route_evidence),
            ApiRouteFact("GET", "/admin/email-logs/bounced", "email_logs#bounced", "rails", "rails-route", route_evidence),
            ApiRouteFact("PUT", "/posts/{id}/wiki", "posts#wiki", "rails", "rails-route", route_evidence),
            ApiRouteFact("PUT", "/posts/{id}/post_type", "posts#post_type", "rails", "rails-route", route_evidence),
            ApiRouteFact("GET", "/users/current", "users#current", "rails", "rails-route", route_evidence),
            ApiRouteFact("GET", "/users/self", "users#self", "rails", "rails-route", route_evidence),
        ]

        links, linked_calls = build_api_links(calls, routes)

        by_endpoint = {link.endpoint: link for link in links}
        self.assertEqual("/captcha/hcaptcha/create", by_endpoint["/captcha/:captchaRoute/create.json"].matched_route)
        self.assertEqual("static-choice-param", by_endpoint["/captcha/:captchaRoute/create.json"].match_type)
        self.assertEqual("low", by_endpoint["/captcha/:captchaRoute/create.json"].confidence)

        self.assertEqual("/policy/accept", by_endpoint["/policy/:policyAction"].matched_route)
        self.assertEqual("static-choice-param", by_endpoint["/policy/:policyAction"].match_type)

        self.assertEqual("/admin/email-logs/sent", by_endpoint["/admin/email-logs/:status.json"].matched_route)
        self.assertEqual("static-choice-param", by_endpoint["/admin/email-logs/:status.json"].match_type)

        self.assertEqual("/posts/{id}/wiki", by_endpoint["/posts/:id/:field"].matched_route)
        self.assertEqual("static-choice-param", by_endpoint["/posts/:id/:field"].match_type)

        self.assertIsNone(by_endpoint["/users/:id"].matched_route)
        self.assertEqual("unmatched", by_endpoint["/users/:id"].match_type)

        linked_by_endpoint = {call.endpoint: call for call in linked_calls}
        self.assertEqual("POST /captcha/hcaptcha/create", linked_by_endpoint["/captcha/:captchaRoute/create.json"].matched_route)
        self.assertEqual("PUT /posts/{id}/wiki", linked_by_endpoint["/posts/:id/:field"].matched_route)


if __name__ == "__main__":
    unittest.main()
