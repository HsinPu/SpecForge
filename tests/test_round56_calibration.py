from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round56HonoCalibrationTests(unittest.TestCase):
    def test_hono_routes_mounts_frameworks_and_wrangler_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            src.mkdir()
            (root / "package.json").write_text(
                """
{
  "type": "module",
  "dependencies": { "hono": "^4.0.0" },
  "devDependencies": {
    "wrangler": "^3.0.0",
    "@cloudflare/workers-types": "^4.0.0"
  },
  "scripts": { "dev": "wrangler dev src/index.ts" }
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "wrangler.jsonc").write_text(
                """
{
  "name": "hono-fixture",
  "main": "src/index.ts",
  "compatibility_date": "2025-03-19",
  "dev": { "port": 3000 },
  "kv_namespaces": [{ "binding": "TODOS", "id": "example" }],
  "assets": { "binding": "ASSETS" }
}
""".lstrip(),
                encoding="utf-8",
            )
            (src / "index.ts").write_text(
                """
import { Hono } from 'hono'

const app = new Hono()
const books = new Hono()

app.get('/', (c) => c.text('ok'))
app.get('/api/*', (c) => c.text('fallback', 404))

books.get('/:id', (c) => c.json({ id: c.req.param('id') }))
books.post('/', async (c) => {
  const body = await c.req.json()
  return c.json(body, 201)
})

app.route('/books', books)

export default app
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("hono", "backend"), frameworks)
            self.assertIn(("cloudflare-workers", "runtime"), frameworks)
            self.assertNotIn(("express", "backend"), frameworks)

            routes = {(route.method, route.path, route.framework, route.kind, route.request_body, route.response_type) for route in facts.api_routes}
            self.assertIn(("GET", "/", "hono", "hono-route", None, "text"), routes)
            self.assertIn(("GET", "/api/{*}", "hono", "hono-route", None, "text"), routes)
            self.assertIn(("GET", "/books/{id}", "hono", "hono-route", None, "json"), routes)
            self.assertIn(("POST", "/books", "hono", "hono-route", "json", "json"), routes)
            self.assertFalse(any(route.framework == "express" for route in facts.api_routes))
            book_route = next(route for route in facts.api_routes if route.path == "/books/{id}")
            self.assertEqual(["id"], [param.name for param in book_route.parameters])

            wrangler = next(fact for fact in facts.runtime_configs if fact.kind == "wrangler-config")
            self.assertIn("runtime:cloudflare-workers", wrangler.values)
            self.assertIn("name:hono-fixture", wrangler.values)
            self.assertIn("main:src/index.ts", wrangler.values)
            self.assertIn("compatibility_date:2025-03-19", wrangler.values)
            self.assertIn("port:3000", wrangler.values)
            self.assertIn("binding:TODOS", wrangler.values)
            self.assertIn("binding:ASSETS", wrangler.values)


if __name__ == "__main__":
    unittest.main()
