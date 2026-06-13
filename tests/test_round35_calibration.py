from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round35NuxtCalibrationTests(unittest.TestCase):
    def test_nuxt_nitro_routes_fetch_params_and_graphql_url_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"dependencies":{"nuxt":"^4.0.0","vue":"^3.0.0"}}\n',
                encoding="utf-8",
            )
            page = root / "app" / "pages" / "modules"
            api = root / "server" / "api" / "v1" / "modules"
            feedback = root / "server" / "api" / "feedback"
            routes = root / "server" / "routes"
            utils = root / "server" / "utils"
            page.mkdir(parents=True)
            api.mkdir(parents=True)
            feedback.mkdir(parents=True)
            routes.mkdir(parents=True)
            utils.mkdir(parents=True)

            (page / "[slug].vue").write_text(
                """
<script setup lang="ts">
const route = useRoute()
const { data } = await useFetch(`/api/v1/modules/${route.params.slug}`)
</script>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (api / "[name].get.ts").write_text(
                "export default defineEventHandler(async event => ({ name: getRouterParam(event, 'name') }))\n",
                encoding="utf-8",
            )
            (feedback / "[id].delete.ts").write_text(
                "export default defineEventHandler(async event => ({ id: getRouterParam(event, 'id') }))\n",
                encoding="utf-8",
            )
            (routes / "sitemap.xml.get.ts").write_text(
                "export default defineEventHandler(() => '<xml />')\n",
                encoding="utf-8",
            )
            (utils / "github.ts").write_text(
                """
export async function fetchTeam() {
  return $fetch(`https://api.github.com/graphql`, {
    method: 'POST',
    body: {
      query: `
        query($org: String!) {
          organization(login: $org) { name }
        }`,
      variables: { org: 'nuxt' }
    }
  })
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            api_routes = {(route.framework, route.kind, route.method, route.path, route.path) for route in facts.api_routes}
            self.assertIn(("nuxt", "nuxt-server-route", "GET", "/api/v1/modules/:name", "/api/v1/modules/:name"), api_routes)
            self.assertIn(("nuxt", "nuxt-server-route", "DELETE", "/api/feedback/:id", "/api/feedback/:id"), api_routes)
            self.assertIn(("nuxt", "nuxt-server-route", "GET", "/sitemap.xml", "/sitemap.xml"), api_routes)

            api_calls = {(call.client, call.method, call.endpoint, call.path) for call in facts.api_calls}
            self.assertIn(("useFetch", "GET", "/api/v1/modules/:slug", "app/pages/modules/[slug].vue"), api_calls)
            self.assertFalse(any(call.client == "graphql" for call in facts.api_calls))


if __name__ == "__main__":
    unittest.main()
