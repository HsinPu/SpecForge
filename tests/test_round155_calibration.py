from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round155OpenApiYamlCalibrationTests(unittest.TestCase):
    def test_quoted_openapi_yaml_paths_are_not_attached_to_previous_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "openapi").mkdir()
            (root / "openapi" / "api-docs.yaml").write_text(
                """
openapi: 3.0.0
info:
  title: Demo API
  version: 1.0.0
paths:
  /api/v1/activities:
    get:
      operationId: getActivities
      responses:
        200:
          description: OK
  "/api/v1/activities/download_entity/{activity_id}":
    get:
      operationId: getActivityHistoricalEntityPdf
      parameters:
        - name: activity_id
          in: path
          required: true
      responses:
        200:
          description: PDF File
        404:
          description: Not found
        5XX:
          description: Server error
  '/api/v1/bank_integrations/{bank_integration}':
    put:
      operationId: updateBankIntegration
      parameters:
        - name: bank_integration
          in: path
          required: true
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/BankIntegration'
      responses:
        200:
          description: Updated
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {
                (route.method, route.path, route.handler): route
                for route in facts.api_routes
                if route.framework == "openapi"
            }

            self.assertIn(("GET", "/api/v1/activities", "getActivities"), routes)
            self.assertIn(
                (
                    "GET",
                    "/api/v1/activities/download_entity/{activity_id}",
                    "getActivityHistoricalEntityPdf",
                ),
                routes,
            )
            self.assertIn(
                (
                    "PUT",
                    "/api/v1/bank_integrations/{bank_integration}",
                    "updateBankIntegration",
                ),
                routes,
            )

            pdf_route = routes[
                (
                    "GET",
                    "/api/v1/activities/download_entity/{activity_id}",
                    "getActivityHistoricalEntityPdf",
                )
            ]
            self.assertEqual(["activity_id"], [param.name for param in pdf_route.parameters])
            self.assertEqual("responses:200,404,5XX", pdf_route.response_type)
            pdf_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "openapi"
                and contract.path == "/api/v1/activities/download_entity/{activity_id}"
            )
            self.assertEqual(["200", "404", "5XX"], pdf_contract.status_codes)

            update_route = routes[
                (
                    "PUT",
                    "/api/v1/bank_integrations/{bank_integration}",
                    "updateBankIntegration",
                )
            ]
            self.assertEqual("requestBody", update_route.request_body)
            self.assertEqual(["bank_integration"], [param.name for param in update_route.parameters])


if __name__ == "__main__":
    unittest.main()
