from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round113HonoCrossFileMountCalibrationTests(unittest.TestCase):
    def test_hono_cross_file_route_mounts_are_prefixed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            src.mkdir()
            (root / "package.json").write_text(
                '{"dependencies":{"hono":"^4.0.0"},"scripts":{"dev":"wrangler dev src/index.ts"}}\n',
                encoding="utf-8",
            )
            (src / "index.ts").write_text(
                """
import { Hono } from 'hono'
import api from './api'
import { TodoAPI } from './TodoAPI'

const app = new Hono()
app.route('/api', api)
app.route('/todo', TodoAPI)

export default app
""".lstrip(),
                encoding="utf-8",
            )
            (src / "api.ts").write_text(
                """
import { Hono } from 'hono'

const api = new Hono()
api.get('/', (c) => c.json({ ok: true }))
api.get('/posts/:id', (c) => c.json({ id: c.req.param('id') }))
api.post('/posts', async (c) => {
  const body = await c.req.json()
  return c.json(body, 201)
})

export default api
""".lstrip(),
                encoding="utf-8",
            )
            (src / "TodoAPI.ts").write_text(
                """
import { Hono } from 'hono'

export const TodoAPI = new Hono()
  .get('/todos', (c) => c.json({ todos: [] }))
  .post('/todos', async (c) => {
    const body = await c.req.json<{ text: string }>()
    return c.json(body, 201)
  })
  .delete('/todos/:id', (c) => c.json({ ok: true }))
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.method, route.path, route.handler, route.request_body) for route in facts.api_routes}
            self.assertIn(("GET", "/api", "api.get", None), routes)
            self.assertIn(("GET", "/api/posts/{id}", "api.get", None), routes)
            self.assertIn(("POST", "/api/posts", "api.post", "json"), routes)
            self.assertIn(("GET", "/todo/todos", "TodoAPI.get", None), routes)
            self.assertIn(("POST", "/todo/todos", "TodoAPI.post", "json"), routes)
            self.assertIn(("DELETE", "/todo/todos/{id}", "TodoAPI.delete", None), routes)
            self.assertNotIn(("GET", "/posts/{id}", "api.get", None), routes)
            mounted = next(route for route in facts.api_routes if route.path == "/api/posts/{id}")
            self.assertEqual(["id"], [param.name for param in mounted.parameters])

            get_contract = next(
                contract for contract in facts.api_contracts if contract.method == "GET" and contract.path == "/api"
            )
            post_contract = next(
                contract for contract in facts.api_contracts if contract.method == "POST" and contract.path == "/todo/todos"
            )
            delete_contract = next(
                contract for contract in facts.api_contracts if contract.method == "DELETE" and contract.path == "/todo/todos/{id}"
            )
            self.assertNotIn("body:c.req.json", get_contract.request_hints)
            self.assertIn("body:c.req.json", post_contract.request_hints)
            self.assertNotIn("body:c.req.json", delete_contract.request_hints)


if __name__ == "__main__":
    unittest.main()
