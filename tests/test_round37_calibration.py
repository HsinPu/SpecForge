from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round37FastifyCalibrationTests(unittest.TestCase):
    def test_fastify_routes_autoprefix_shorthand_and_contract_hints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"dependencies":{"fastify":"^4.0.0","@fastify/autoload":"^5.0.0"}}\n',
                encoding="utf-8",
            )
            routes = root / "routes"
            routes.mkdir()
            (routes / "admin.js").write_text(
                """
export const autoPrefix = '/api'

export default async function admin (fastify, opts) {
  fastify.route({
    method: 'PUT',
    path: '/users/:id',
    schema: {
      response: {
        201: { type: 'object' }
      }
    },
    handler: updateUser
  })

  fastify.route({
    method: ['GET', 'POST'],
    url: '/sessions',
    handler: onSessions
  })

  fastify.get('/health', onHealth)

  async function updateUser (req, reply) {
    const id = req.params.id
    const expand = req.query.expand
    const name = req.body.name
    reply.code(201).send({ id, expand, name })
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("fastify", frameworks)

            api_routes = {(route.framework, route.kind, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("fastify", "fastify-route", "PUT", "/api/users/:id", "updateUser"), api_routes)
            self.assertIn(("fastify", "fastify-route", "GET", "/api/sessions", "onSessions"), api_routes)
            self.assertIn(("fastify", "fastify-route", "POST", "/api/sessions", "onSessions"), api_routes)
            self.assertIn(("fastify", "fastify-route", "GET", "/api/health", "onHealth"), api_routes)

            contract = next(
                item
                for item in facts.api_contracts
                if item.framework == "fastify" and item.method == "PUT" and item.path == "/api/users/:id"
            )
            self.assertIn("path:req.params.id", contract.request_hints)
            self.assertIn("query:req.query.expand", contract.request_hints)
            self.assertIn("body:req.body.name", contract.request_hints)
            self.assertIn("response:reply.send", contract.response_hints)
            self.assertIn("201", contract.status_codes)


if __name__ == "__main__":
    unittest.main()
