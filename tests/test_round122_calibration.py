from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round122VueApiServiceCalibrationTests(unittest.TestCase):

    def test_vue_api_service_wrapper_calls_are_extracted_without_path_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            common = src / "common"
            store = src / "store"
            common.mkdir(parents=True)
            store.mkdir(parents=True)
            (root / "package.json").write_text(
                '{"dependencies":{"vue":"^3.0.0","vue-router":"^4.0.0","pinia":"^3.0.0","vite":"^6.0.0"}}\n',
                encoding="utf-8",
            )
            (common / "api.service.js").write_text(
                """
async function request(method, path, body) {
  return fetch(`${API_URL}/${path}`, { method, body });
}

const ApiService = {
  get(resource, slug = "") {
    const path = slug ? `${resource}/${slug}` : resource;
    return request("GET", path);
  },
  query(resource, config) {
    return request("GET", resource);
  },
  post(resource, params) {
    return request("POST", resource, params);
  },
  update(resource, slug, params) {
    return request("PUT", `${resource}/${slug}`, params);
  },
  delete(resource) {
    return request("DELETE", resource);
  }
};

export const ArticlesService = {
  query(type, params) {
    return ApiService.query("articles" + (type === "feed" ? "/feed" : ""), { params });
  },
  get(slug) {
    return ApiService.get("articles", slug);
  },
  update(slug, params) {
    return ApiService.update("articles", slug, { article: params });
  },
  destroy(slug) {
    return ApiService.delete(`articles/${slug}`);
  }
};
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (store / "profile.js").write_text(
                """
import ApiService from "@/common/api.service";

export async function fetchProfile(username) {
  return ApiService.get("profiles", username);
}

export async function follow(username) {
  return ApiService.post(`profiles/${username}/follow`);
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            calls = {(call.method, call.endpoint, call.client, call.context) for call in facts.api_calls}
            self.assertIn(("GET", "/articles", "ApiService", "api-service-wrapper"), calls)
            self.assertIn(("GET", "/articles/feed", "ApiService", "api-service-wrapper"), calls)
            self.assertIn(("GET", "/articles/:slug", "ApiService", "api-service-wrapper"), calls)
            self.assertIn(("PUT", "/articles/:slug", "ApiService", "api-service-wrapper"), calls)
            self.assertIn(("DELETE", "/articles/:slug", "ApiService", "api-service-wrapper"), calls)
            self.assertIn(("GET", "/profiles/:username", "ApiService", "api-service-wrapper"), calls)
            self.assertIn(("POST", "/profiles/:username/follow", "ApiService", "api-service-wrapper"), calls)
            self.assertFalse(any(call.endpoint == "/:path" for call in facts.api_calls))


if __name__ == "__main__":
    unittest.main()
