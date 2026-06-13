from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round58ElysiaBunCalibrationTests(unittest.TestCase):
    def test_elysia_routes_framework_detection_and_bun_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            tests = root / "test"
            src.mkdir()
            tests.mkdir()
            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "elysia": "^1.4.0"
  },
  "devDependencies": {
    "bun-types": "^1.2.0"
  },
  "scripts": {
    "dev": "bun run src/server.ts"
  }
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "bun.lock").write_text("", encoding="utf-8")
            (src / "server.ts").write_text(
                """
import { Elysia, t } from 'elysia'

/**
 * Example only:
 * app.get('/docs-only', () => 'ignore')
 */
const app = new Elysia({ prefix: '/api' })
  .get('/users/:id', ({ params }) => params.id)
  .post('/users', ({ body }) => body, {
    body: t.Object({
      name: t.String()
    })
  })
  .group('/admin', (app) => app.get('/stats', () => 'ok'))
  .listen(3000)

const publicApp = new Elysia().get('/public', () => 'ok')
""".lstrip(),
                encoding="utf-8",
            )
            (tests / "server_test.ts").write_text(
                """
import { Elysia } from 'elysia'
new Elysia().get('/test-only', () => 'ignore')
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("elysia", "backend"), frameworks)
            self.assertIn(("bun", "runtime"), frameworks)

            routes = {(route.method, route.path, route.framework, route.kind) for route in facts.api_routes}
            self.assertIn(("GET", "/api/users/{id}", "elysia", "elysia-route"), routes)
            self.assertIn(("POST", "/api/users", "elysia", "elysia-route"), routes)
            self.assertIn(("GET", "/api/admin/stats", "elysia", "elysia-route"), routes)
            self.assertIn(("GET", "/public", "elysia", "elysia-route"), routes)
            self.assertNotIn(("GET", "/api/admin/public", "elysia", "elysia-route"), routes)
            self.assertNotIn(("GET", "/docs-only", "elysia", "elysia-route"), routes)
            self.assertFalse(any(route.framework == "express" for route in facts.api_routes))
            self.assertFalse(any(route.path == "/test-only" for route in facts.api_routes))

            users_route = next(route for route in facts.api_routes if route.path == "/api/users/{id}")
            self.assertEqual(["id"], [param.name for param in users_route.parameters])
            create_route = next(route for route in facts.api_routes if route.path == "/api/users")
            self.assertEqual("schema", create_route.request_body)


if __name__ == "__main__":
    unittest.main()
