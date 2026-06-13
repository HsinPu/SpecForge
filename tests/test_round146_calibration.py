from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round146SvelteKitPageCalibrationTests(unittest.TestCase):
    def test_sveltekit_page_components_are_static_pages_with_route_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "devDependencies": {
    "@sveltejs/kit": "^2.0.0",
    "svelte": "^5.0.0",
    "vite": "^7.0.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            routes = root / "src" / "routes"
            product = routes / "products" / "[id]"
            grouped = routes / "(marketing)" / "about"
            api = routes / "api" / "[param1]" / "[...catcher]"
            product.mkdir(parents=True)
            grouped.mkdir(parents=True)
            api.mkdir(parents=True)

            (routes / "+page.svelte").write_text(
                """
<svelte:head>
  <title>Home</title>
</svelte:head>
<h1>Home</h1>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (routes / "+layout.svelte").write_text("<slot />\n", encoding="utf-8")
            (product / "+page.svelte").write_text("<h1>Product</h1>\n", encoding="utf-8")
            (grouped / "+page.svelte").write_text("<h1>About</h1>\n", encoding="utf-8")
            (api / "+server.ts").write_text(
                """
export function GET() {
  return Response.json({ ok: true });
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            pages = {(page.route, page.path, page.kind, page.template_engine, page.title) for page in facts.pages}
            self.assertIn(("/", "src/routes/+page.svelte", "sveltekit-page", "svelte", "Home"), pages)
            self.assertIn(("/products/:id", "src/routes/products/[id]/+page.svelte", "sveltekit-page", "svelte", None), pages)
            self.assertIn(("/about", "src/routes/(marketing)/about/+page.svelte", "sveltekit-page", "svelte", None), pages)
            self.assertNotIn("src/routes/+layout.svelte", {page.path for page in facts.pages})

            route_sources = {(route.route, route.path, route.kind) for route in facts.frontend_routes}
            self.assertIn(("/products/:id", "src/routes/products/[id]/+page.svelte", "sveltekit-route"), route_sources)

            backend_routes = {(route.method, route.path, route.kind) for route in facts.api_routes}
            self.assertIn(("GET", "/api/:param1/:catcher*", "sveltekit-endpoint"), backend_routes)


if __name__ == "__main__":
    unittest.main()
