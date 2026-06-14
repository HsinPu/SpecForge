from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round161SupersetClientCalibrationTests(unittest.TestCase):
    def test_superset_client_object_method_calls_link_to_flask_appbuilder_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "@superset-ui/core": "^0.20.0",
    "react": "^18.0.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            api_dir = root / "superset" / "tags"
            api_dir.mkdir(parents=True)
            (api_dir / "api.py").write_text(
                """
from flask_appbuilder.api import expose
from superset.views.base_api import BaseSupersetModelRestApi


class TagRestApi(BaseSupersetModelRestApi):
    resource_name = "tag"

    @expose("/", methods=("GET", "POST"))
    def list(self):
        return self.response(200)

    @expose("/<int:pk>", methods=("GET",))
    def get(self, pk):
        return self.response(200)

    @expose("/get_objects/", methods=("GET",))
    def get_objects(self):
        return self.response(200)

    @expose("/<int:object_type>/<int:object_id>/<tag_name>", methods=("DELETE",))
    def delete_tagged_object(self, object_type, object_id, tag_name):
        return self.response(200)


class ChartDataRestApi(BaseSupersetModelRestApi):
    resource_name = "chart"

    @expose("/data", methods=("POST",))
    def data(self):
        return self.response(200)


class DatasetRestApi(BaseSupersetModelRestApi):
    resource_name = "dataset"

    @expose("/<int:pk>", methods=("GET",))
    def get(self, pk):
        return self.response(200)
""".lstrip(),
                encoding="utf-8",
            )

            frontend = root / "superset-frontend" / "src" / "features" / "tags"
            frontend.mkdir(parents=True)
            (frontend / "tags.ts").write_text(
                """
import { SupersetClient } from "@superset-ui/core";
import rison from "rison";

export function fetchAllTags() {
  return SupersetClient.get({
    endpoint: `/api/v1/tag/?q=${rison.encode({
      filters: [{ col: "type", opr: "custom_tag", value: true }],
    })}`,
  });
}

export function fetchSingleTag(id: number) {
  return SupersetClient.get({ endpoint: `/api/v1/tag/${id}` });
}

export function deleteTaggedObject(objectTypeId: number, objectId: number, tag: { name: string }) {
  return SupersetClient.delete({
    endpoint: `/api/v1/tag/${objectTypeId}/${objectId}/${tag.name}`,
  });
}

export function fetchObjects(tagIds: number[]) {
  const objectsUrl = `/api/v1/tag/get_objects/?tagIds=${tagIds}`;
  return SupersetClient.get({ endpoint: objectsUrl });
}

export function postChartForm(formData: FormData) {
  return SupersetClient.postForm("/api/v1/chart/data", { formData });
}

export function postRedirect(redirectUrl: string, formData: FormData) {
  return SupersetClient.postForm(redirectUrl, { formData });
}

export function fetchDataset(confirmedDataset?: { id?: number }) {
  return SupersetClient.get({
    endpoint: `/api/v1/dataset/${confirmedDataset?.id}`,
  });
}
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            calls = {(call.client, call.method, call.endpoint, call.matched_route, call.context) for call in facts.api_calls}
            self.assertIn(("SupersetClient", "GET", "/api/v1/tag/", "GET /api/v1/tag", "object-method-client"), calls)
            self.assertIn(("SupersetClient", "GET", "/api/v1/tag/:id", "GET /api/v1/tag/<int:pk>", "object-method-client"), calls)
            self.assertIn(
                (
                    "SupersetClient",
                    "DELETE",
                    "/api/v1/tag/:objectTypeId/:objectId/:name",
                    "DELETE /api/v1/tag/<int:object_type>/<int:object_id>/<tag_name>",
                    "object-method-client",
                ),
                calls,
            )
            self.assertIn(("SupersetClient", "GET", "/api/v1/tag/get_objects/", "GET /api/v1/tag/get_objects/", "object-method-client"), calls)
            self.assertIn(("SupersetClient", "POST", "/api/v1/chart/data", "POST /api/v1/chart/data", "object-method-client"), calls)
            self.assertIn(("SupersetClient", "POST", "dynamic:redirectUrl", None, "object-method-client"), calls)
            self.assertIn(("SupersetClient", "GET", "/api/v1/dataset/:id", "GET /api/v1/dataset/<int:pk>", "object-method-client"), calls)


if __name__ == "__main__":
    unittest.main()
