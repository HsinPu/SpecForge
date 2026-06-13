from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round43KoaCalibrationTests(unittest.TestCase):
    def test_koa_router_routes_prefixes_and_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"dependencies":{"koa":"^2.0.0","koa-router":"^7.0.0","koa-bodyparser":"^4.0.0"}}\n',
                encoding="utf-8",
            )
            routes = root / "src" / "routes"
            controllers = root / "src" / "controllers"
            routes.mkdir(parents=True)
            controllers.mkdir(parents=True)
            (routes / "index.js").write_text(
                """
const Router = require("koa-router")
const router = new Router()
const api = new Router()
const users = require("./users-router")

api.use(users)
router.use("/api", api.routes())
module.exports = router
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (routes / "users-router.js").write_text(
                """
const Router = require("koa-router")
const ctrl = require("../controllers/users-controller")
const auth = require("../middleware/auth")
const router = new Router()

router.post("/users", ctrl.post)
router.get("/users/:id", auth, ctrl.get)
module.exports = router.routes()
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (controllers / "users-controller.js").write_text(
                """
module.exports = {
  async post(ctx) {
    const { body } = ctx.request
    ctx.status = 201
    ctx.body = { user: body.user }
  },

  async get(ctx) {
    const { id } = ctx.params
    const { expand } = ctx.query
    const { user } = ctx.state
    ctx.assert(user, 401)
    ctx.body = { id, expand }
  },
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("koa", frameworks)

            routes_seen = {(route.framework, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("koa", "POST", "/api/users", "ctrl.post"), routes_seen)
            self.assertIn(("koa", "GET", "/api/users/:id", "ctrl.get"), routes_seen)
            self.assertNotIn(("express", "POST", "/users", "ctrl.post"), routes_seen)

            post_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "koa" and contract.method == "POST" and contract.path == "/api/users"
            )
            self.assertIn("body:ctx.request.body", post_contract.request_hints)
            self.assertIn("response:ctx.body", post_contract.response_hints)
            self.assertIn("201", post_contract.status_codes)

            get_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "koa" and contract.method == "GET" and contract.path == "/api/users/:id"
            )
            self.assertIn("path:id", get_contract.request_hints)
            self.assertIn("path:ctx.params.id", get_contract.request_hints)
            self.assertIn("query:ctx.query.expand", get_contract.request_hints)
            self.assertIn("auth:ctx.state.user", get_contract.request_hints)
            self.assertIn("401", get_contract.status_codes)


if __name__ == "__main__":
    unittest.main()
