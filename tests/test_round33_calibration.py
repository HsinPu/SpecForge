from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round33AstroCalibrationTests(unittest.TestCase):
    def test_astro_pages_components_api_routes_and_fetch_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"dependencies":{"astro":"^6.0.0","@astrojs/rss":"^4.0.0"}}\n',
                encoding="utf-8",
            )
            (root / "astro.config.mjs").write_text("export default {};\n", encoding="utf-8")
            pages = root / "src" / "pages"
            api = pages / "api" / "v1" / "items"
            components = root / "src" / "components"
            hidden = pages / "_components"
            details = pages / "themes" / "details"
            api.mkdir(parents=True)
            components.mkdir(parents=True)
            hidden.mkdir(parents=True)
            details.mkdir(parents=True)
            (pages / "index.astro").write_text("---\n---\n<h1>Home</h1>\n", encoding="utf-8")
            (details / "[slug].astro").write_text(
                """
---
import Card from '../../../components/Card.astro';
const API_URL = 'https://api.example.test';
const slug = Astro.params.slug;
const res = await fetch(`${API_URL}/api/themes/details?slug=${slug}`);
---
<Card title="Theme" />
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (hidden / "Helper.astro").write_text("---\n---\n<div />\n", encoding="utf-8")
            (components / "Card.astro").write_text(
                """
---
const { title, href = '/' } = Astro.props;
---
<a href={href}>{title}</a>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (api / "[...page].ts").write_text(
                """
import type { APIRoute } from 'astro';

export const prerender = false;

export const GET: APIRoute = async () => Response.json({});
export const HEAD: APIRoute = () => new Response(null);
export const ALL: APIRoute = () => Response.json({}, { status: 405 });
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("astro", frameworks)
            self.assertNotIn("next", frameworks)

            frontend_routes = {(route.framework, route.kind, route.route, route.path) for route in facts.frontend_routes}
            self.assertIn(("astro", "astro-page-route", "/", "src/pages/index.astro"), frontend_routes)
            self.assertIn(("astro", "astro-page-route", "/themes/details/:slug", "src/pages/themes/details/[slug].astro"), frontend_routes)
            self.assertNotIn(("astro", "astro-page-route", "/_components/helper", "src/pages/_components/Helper.astro"), frontend_routes)
            self.assertNotIn(("astro", "template-page-route", "/", "src/pages/index.astro"), frontend_routes)

            pages = {(page.template_engine, page.route, page.path) for page in facts.pages}
            self.assertIn(("astro", "/", "src/pages/index.astro"), pages)
            self.assertIn(("astro", "/themes/details/:slug", "src/pages/themes/details/[slug].astro"), pages)

            components = {(component.framework, component.name, tuple(component.props), component.path) for component in facts.components}
            self.assertIn(("astro", "Card", ("title", "href"), "src/components/Card.astro"), components)

            api_routes = {(route.framework, route.kind, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("astro", "astro-api-route", "GET", "/api/v1/items/:page*", "GET"), api_routes)
            self.assertIn(("astro", "astro-api-route", "HEAD", "/api/v1/items/:page*", "HEAD"), api_routes)
            self.assertIn(("astro", "astro-api-route", "ANY", "/api/v1/items/:page*", "ALL"), api_routes)

            api_calls = {(call.method, call.endpoint, call.path) for call in facts.api_calls}
            self.assertIn(("GET", "https://api.example.test/api/themes/details", "src/pages/themes/details/[slug].astro"), api_calls)


if __name__ == "__main__":
    unittest.main()
