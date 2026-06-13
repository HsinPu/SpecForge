from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round57FreshCalibrationTests(unittest.TestCase):
    def test_fresh_file_routes_handlers_frameworks_and_deno_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            routes = root / "www" / "routes"
            docs = routes / "docs"
            routes.mkdir(parents=True)
            docs.mkdir()
            (root / "www" / "deno.json").write_text(
                """
{
  "tasks": {
    "dev": "vite",
    "build": "vite build",
    "start": "deno serve -A _fresh/server.js"
  },
  "imports": {
    "fresh": "jsr:@fresh/core",
    "@std/path": "jsr:@std/path"
  }
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "www" / "main.ts").write_text(
                """
import { App, staticFiles } from "fresh";

export const app = new App()
  .use(staticFiles())
  .fsRoutes();
""".lstrip(),
                encoding="utf-8",
            )
            (routes / "index.tsx").write_text(
                """
export default function Home() {
  return <main>Fresh</main>;
}
""".lstrip(),
                encoding="utf-8",
            )
            (docs / "[...slug].tsx").write_text(
                """
import { define } from "../../utils.ts";

export const handler = define.handlers({
  async GET(ctx) {
    return new Response(ctx.params.slug);
  },
});

export default function DocsPage() {
  return <main>Docs</main>;
}
""".lstrip(),
                encoding="utf-8",
            )
            (routes / "raw.ts").write_text(
                """
import type { RouteConfig } from "fresh";
import { define } from "../utils.ts";

export const handler = define.handlers({
  async GET(ctx) {
    return new Response(ctx.params.path);
  },
});

export const config: RouteConfig = {
  routeOverride: "/@:version/:path*",
};
""".lstrip(),
                encoding="utf-8",
            )
            (routes / "_middleware.ts").write_text("export function handler() {}\n", encoding="utf-8")
            internal = root / "packages" / "fresh" / "src"
            internal.mkdir(parents=True)
            (internal / "context.ts").write_text(
                """
/**
 * Example:
 *   app.get("/", () => new Response("docs only"));
 */
export class Context {}
""".lstrip(),
                encoding="utf-8",
            )
            (internal / "app_test.tsx").write_text(
                """
const app = { get() {} };
app.get("/", () => new Response("test only"));
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("fresh", "frontend"), frameworks)
            self.assertIn(("fresh", "backend"), frameworks)
            self.assertIn(("deno", "runtime"), frameworks)

            frontend_routes = {(route.route, route.framework, route.kind, route.path) for route in facts.frontend_routes}
            self.assertIn(("/", "fresh", "fresh-file-route", "www/routes/index.tsx"), frontend_routes)
            self.assertIn(("/docs/{slug*}", "fresh", "fresh-file-route", "www/routes/docs/[...slug].tsx"), frontend_routes)
            self.assertIn(("/@{version}/{path*}", "fresh", "fresh-file-route", "www/routes/raw.ts"), frontend_routes)
            self.assertFalse(any(route.path.endswith("_middleware.ts") for route in facts.frontend_routes))

            api_routes = {(route.method, route.path, route.framework, route.kind) for route in facts.api_routes}
            self.assertIn(("GET", "/docs/{slug*}", "fresh", "fresh-handler-route"), api_routes)
            self.assertIn(("GET", "/@{version}/{path*}", "fresh", "fresh-handler-route"), api_routes)
            self.assertFalse(any(route.framework == "express" for route in facts.api_routes))
            raw_route = next(route for route in facts.api_routes if route.path == "/@{version}/{path*}")
            self.assertEqual(["version", "path"], [param.name for param in raw_route.parameters])

            deno = next(fact for fact in facts.runtime_configs if fact.kind == "deno-config")
            self.assertIn("runtime:deno", deno.values)
            self.assertIn("task:dev", deno.values)
            self.assertIn("task:build", deno.values)
            self.assertIn("task:start", deno.values)
            self.assertIn("import:fresh", deno.values)


if __name__ == "__main__":
    unittest.main()
