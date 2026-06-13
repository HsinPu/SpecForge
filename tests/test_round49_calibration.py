from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round49StrapiCalibrationTests(unittest.TestCase):
    def test_strapi_core_routes_schema_models_contracts_and_frontend_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "api").mkdir()
            (root / "client").mkdir()
            (root / "api" / "package.json").write_text(
                '{"dependencies":{"@strapi/strapi":"4.13.5","@strapi/plugin-i18n":"4.13.5"}}\n',
                encoding="utf-8",
            )
            (root / "client" / "package.json").write_text(
                '{"dependencies":{"next":"^13.0.0","react":"^18.0.0"}}\n',
                encoding="utf-8",
            )
            article_dir = root / "api" / "src" / "api" / "article"
            global_dir = root / "api" / "src" / "api" / "global"
            (article_dir / "routes").mkdir(parents=True)
            (article_dir / "content-types" / "article").mkdir(parents=True)
            (global_dir / "routes").mkdir(parents=True)
            (global_dir / "content-types" / "global").mkdir(parents=True)

            (article_dir / "routes" / "article.js").write_text(
                """
const { createCoreRouter } = require("@strapi/strapi").factories;

module.exports = createCoreRouter("api::article.article");
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (article_dir / "routes" / "custom-article.js").write_text(
                """
module.exports = {
  routes: [
    {
      method: "GET",
      path: "/articles/:id/stats",
      handler: "article.stats"
    }
  ]
};
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (article_dir / "content-types" / "article" / "schema.json").write_text(
                """
{
  "kind": "collectionType",
  "collectionName": "articles",
  "info": {
    "singularName": "article",
    "pluralName": "articles",
    "displayName": "Article"
  },
  "options": {
    "draftAndPublish": true
  },
  "attributes": {
    "title": {
      "type": "string",
      "required": true
    },
    "slug": {
      "type": "uid",
      "targetField": "title"
    },
    "category": {
      "type": "relation",
      "relation": "manyToOne",
      "target": "api::category.category",
      "inversedBy": "articles"
    },
    "seo": {
      "type": "component",
      "component": "shared.seo"
    },
    "blocks": {
      "type": "dynamiczone",
      "components": ["blocks.faq", "blocks.cta"]
    }
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (global_dir / "routes" / "global.js").write_text(
                """
const { createCoreRouter } = require("@strapi/strapi").factories;

module.exports = createCoreRouter("api::global.global");
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (global_dir / "content-types" / "global" / "schema.json").write_text(
                """
{
  "kind": "singleType",
  "info": {
    "singularName": "global",
    "pluralName": "globals",
    "displayName": "Global"
  },
  "attributes": {
    "siteName": {
      "type": "string"
    }
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "client" / "utils.js").write_text(
                """
export function getStrapiURL(path = "") {
  return `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:1337"}/api${path}`;
}

export async function loadArticles() {
  const url = getStrapiURL("/articles?populate=*");
  return fetch(url);
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "client" / "pages" / "api").mkdir(parents=True)
            (root / "client" / "pages" / "api" / "preview.js").write_text(
                """
export default async function handler(req, res) {
  return res.status(200).json({ ok: true });
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("strapi", frameworks)

            routes = {(route.framework, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("strapi", "GET", "/api/articles", "article.find"), routes)
            self.assertIn(("strapi", "POST", "/api/articles", "article.create"), routes)
            self.assertIn(("strapi", "GET", "/api/articles/{id}", "article.findOne"), routes)
            self.assertIn(("strapi", "PUT", "/api/articles/{id}", "article.update"), routes)
            self.assertIn(("strapi", "DELETE", "/api/articles/{id}", "article.delete"), routes)
            self.assertIn(("strapi", "GET", "/api/global", "global.find"), routes)
            self.assertIn(("strapi", "GET", "/api/articles/{id}/stats", "article.stats"), routes)
            self.assertIn(("next", "ANY", "/api/preview", None), routes)
            self.assertNotIn(("astro", "ANY", "/api/preview", None), routes)

            post_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "strapi" and contract.method == "POST" and contract.path == "/api/articles"
            )
            self.assertIn("body:data", post_contract.request_hints)
            self.assertIn("return:article", post_contract.response_hints)

            list_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "strapi" and contract.method == "GET" and contract.path == "/api/articles"
            )
            self.assertIn("query:filters", list_contract.request_hints)
            self.assertIn("query:populate", list_contract.request_hints)

            models_by_name = {model.name: model for model in facts.data_models}
            self.assertEqual("strapi-content-type", models_by_name["article"].kind)
            self.assertIn("title:string", models_by_name["article"].fields)
            self.assertIn("category:relation<api::category.category>", models_by_name["article"].fields)
            self.assertIn("seo:component<shared.seo>", models_by_name["article"].fields)
            self.assertIn("required:title", models_by_name["article"].annotations)
            self.assertIn("relation:category:manyToOne:api::category.category", models_by_name["article"].annotations)

            data_layer = {(layer.kind, layer.name) for layer in facts.data_layers}
            self.assertIn(("strapi-schema", "article"), data_layer)
            self.assertIn(("code-model:strapi-content-type", "article"), data_layer)

            api_calls = {(call.client, call.endpoint) for call in facts.api_calls}
            self.assertIn(("strapi-client", "/api/articles"), api_calls)
            self.assertTrue(
                any(
                    link.endpoint == "/api/articles"
                    and link.matched_route == "/api/articles"
                    and link.matched_framework == "strapi"
                    for link in facts.api_links
                )
            )

            self.assertTrue(all(route.evidence.file and route.evidence.line_start for route in facts.api_routes if route.framework == "strapi"))


if __name__ == "__main__":
    unittest.main()
