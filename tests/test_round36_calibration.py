from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round36ReactRouterCalibrationTests(unittest.TestCase):
    def test_react_router_file_routes_data_routes_and_content_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"dependencies":{"react":"^19.0.0","react-router":"^7.0.0","@react-router/dev":"^7.0.0","@remix-run/react":"^2.0.0"}}\n',
                encoding="utf-8",
            )
            routes = root / "app" / "routes"
            blog = routes / "blog_"
            resource = routes / "resources" / "webauthn"
            well_known = routes / "[.]well-known" / "mcp"
            content = root / "content" / "blog" / "example"
            blog.mkdir(parents=True)
            resource.mkdir(parents=True)
            well_known.mkdir(parents=True)
            content.mkdir(parents=True)

            (routes / "index.tsx").write_text(
                "export async function loader() { return null }\nexport default function Index() { return <main /> }\n",
                encoding="utf-8",
            )
            (blog / "$slug.tsx").write_text(
                "export async function loader() { return null }\nexport async function action() { return null }\n",
                encoding="utf-8",
            )
            (resource / "generate-registration-options.ts").write_text(
                "export const loader = async () => null\n",
                encoding="utf-8",
            )
            (well_known / "server-card[.]json.ts").write_text(
                "export async function loader() { return Response.json({}) }\n",
                encoding="utf-8",
            )
            (routes / "mcp.server.ts").write_text(
                "export async function loader() { return null }\n",
                encoding="utf-8",
            )
            (content / "components.jsx").write_text(
                "import { Route } from 'react-router-dom';\n<Route path=\"/example\" />\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("react-router", frameworks)
            self.assertIn("remix", frameworks)

            frontend_routes = {(route.kind, route.route, route.path) for route in facts.frontend_routes}
            self.assertIn(("react-router-file-route", "/", "app/routes/index.tsx"), frontend_routes)
            self.assertIn(("react-router-file-route", "/blog/:slug", "app/routes/blog_/$slug.tsx"), frontend_routes)
            self.assertIn(
                (
                    "react-router-file-route",
                    "/resources/webauthn/generate-registration-options",
                    "app/routes/resources/webauthn/generate-registration-options.ts",
                ),
                frontend_routes,
            )
            self.assertIn(
                ("react-router-file-route", "/.well-known/mcp/server-card.json", "app/routes/[.]well-known/mcp/server-card[.]json.ts"),
                frontend_routes,
            )
            self.assertNotIn(("react-router-file-route", "/mcp/server", "app/routes/mcp.server.ts"), frontend_routes)
            self.assertFalse(any(route.kind == "react-router-route" for route in facts.frontend_routes))

            api_routes = {(route.kind, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("react-router-data-route", "GET", "/", "loader"), api_routes)
            self.assertIn(("react-router-data-route", "GET", "/blog/:slug", "loader"), api_routes)
            self.assertIn(("react-router-data-route", "POST", "/blog/:slug", "action"), api_routes)
            self.assertIn(
                ("react-router-data-route", "GET", "/resources/webauthn/generate-registration-options", "loader"),
                api_routes,
            )
            self.assertNotIn(("react-router-data-route", "GET", "/mcp/server", "loader"), api_routes)


if __name__ == "__main__":
    unittest.main()
