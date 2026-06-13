from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round104HonoOpenApiCalibrationTests(unittest.TestCase):
    def test_hono_openapi_routes_contracts_and_source_entrypoint_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src" / "lib").mkdir(parents=True)
            (root / "src" / "routes" / "tasks").mkdir(parents=True)
            (root / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
            (root / "package.json").write_text(
                """
{
  "type": "module",
  "scripts": {
    "dev": "tsx watch src/index.ts",
    "start": "node ./dist/src/index.js",
    "test": "vitest",
    "build": "tsc"
  },
  "dependencies": {
    "hono": "^4.0.0",
    "@hono/node-server": "^1.0.0",
    "@hono/zod-openapi": "^1.0.0",
    "@scalar/hono-api-reference": "^1.0.0"
  }
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "src" / "index.ts").write_text(
                """
import { serve } from "@hono/node-server";
import app from "./app";

serve({ fetch: app.fetch, port: 3000 });
""".lstrip(),
                encoding="utf-8",
            )
            (root / "src" / "app.ts").write_text(
                """
import configureOpenAPI from "./lib/configure-open-api";
import createApp from "./lib/create-app";
import index from "./routes/index.route";
import tasks from "./routes/tasks/tasks.index";

const app = createApp();
configureOpenAPI(app);
const routes = [index, tasks] as const;
routes.forEach((route) => app.route("/", route));
export default app;
""".lstrip(),
                encoding="utf-8",
            )
            (root / "src" / "lib" / "create-app.ts").write_text(
                """
import { OpenAPIHono } from "@hono/zod-openapi";

export type AppOpenAPI = OpenAPIHono;
export function createRouter() {
  return new OpenAPIHono();
}
export default function createApp() {
  return createRouter();
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "src" / "lib" / "configure-open-api.ts").write_text(
                """
import { Scalar } from "@scalar/hono-api-reference";
import type { AppOpenAPI } from "./create-app";

export default function configureOpenAPI(app: AppOpenAPI) {
  app.doc("/doc", { openapi: "3.0.0", info: { title: "Tasks", version: "1.0.0" } });
  app.get("/reference", Scalar({ url: "/doc" }));
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "src" / "routes" / "index.route.ts").write_text(
                """
import { createRoute } from "@hono/zod-openapi";
import { HttpStatusCodes } from "stoker/http-status-codes";
import { createRouter } from "../lib/create-app";

const router = createRouter().openapi(
  createRoute({
    method: "get",
    path: "/",
    responses: {
      [HttpStatusCodes.OK]: { description: "Health check" },
    },
  }),
  (c) => c.json({ message: "ok" })
);

export default router;
""".lstrip(),
                encoding="utf-8",
            )
            (root / "src" / "routes" / "tasks" / "tasks.routes.ts").write_text(
                """
import { createRoute } from "@hono/zod-openapi";
import { HttpStatusCodes } from "stoker/http-status-codes";

export const list = createRoute({
  method: "get",
  path: "/tasks",
  responses: {
    [HttpStatusCodes.OK]: { description: "List tasks" },
  },
});

export const create = createRoute({
  method: "post",
  path: "/tasks",
  request: {
    body: { content: { "application/json": {} } },
  },
  responses: {
    [HttpStatusCodes.OK]: { description: "Created task" },
    [HttpStatusCodes.UNPROCESSABLE_ENTITY]: { description: "Invalid task" },
  },
});

export const patch = createRoute({
  method: "patch",
  path: "/tasks/{id}",
  request: {
    params: {},
    body: { content: { "application/json": {} } },
  },
  responses: {
    [HttpStatusCodes.OK]: { description: "Updated task" },
    [HttpStatusCodes.NOT_FOUND]: { description: "Missing task" },
    [HttpStatusCodes.UNPROCESSABLE_ENTITY]: { description: "Invalid task" },
  },
});

export const remove = createRoute({
  method: "delete",
  path: "/tasks/{id}",
  request: {
    params: {},
  },
  responses: {
    [HttpStatusCodes.NO_CONTENT]: { description: "Deleted task" },
    [HttpStatusCodes.NOT_FOUND]: { description: "Missing task" },
  },
});
""".lstrip(),
                encoding="utf-8",
            )
            (root / "src" / "routes" / "tasks" / "tasks.index.ts").write_text(
                """
import { createRouter } from "../../lib/create-app";
import * as routes from "./tasks.routes";

const router = createRouter()
  .openapi(routes.list, () => {})
  .openapi(routes.create, () => {})
  .openapi(routes.patch, () => {})
  .openapi(routes.remove, () => {});

export default router;
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("hono", "backend"), frameworks)
            self.assertIn(("openapi", "backend"), frameworks)
            self.assertNotIn(("express", "backend"), frameworks)

            entrypoints = {(entry.kind, entry.path, entry.command) for entry in facts.entrypoints}
            self.assertIn(("node-app-entrypoint", "src/index.ts", "pnpm run start"), entrypoints)

            routes = {(route.method, route.path, route.framework, route.kind, route.request_body, route.response_type) for route in facts.api_routes}
            self.assertIn(("GET", "/doc", "hono", "hono-route", None, "openapi"), routes)
            self.assertIn(("GET", "/reference", "hono", "hono-route", None, None), routes)
            self.assertIn(("GET", "/", "hono", "hono-openapi-route", None, "responses:200"), routes)
            self.assertIn(("GET", "/tasks", "hono", "hono-openapi-route", None, "responses:200"), routes)
            self.assertIn(("POST", "/tasks", "hono", "hono-openapi-route", "body", "responses:200,422"), routes)
            self.assertIn(("PATCH", "/tasks/{id}", "hono", "hono-openapi-route", "body", "responses:200,404,422"), routes)
            self.assertIn(("DELETE", "/tasks/{id}", "hono", "hono-openapi-route", None, "responses:204,404"), routes)
            self.assertFalse(any(route.framework == "express" for route in facts.api_routes))

            patch_route = next(route for route in facts.api_routes if route.method == "PATCH" and route.path == "/tasks/{id}")
            self.assertEqual(["id"], [param.name for param in patch_route.parameters])

            patch_contract = next(contract for contract in facts.api_contracts if contract.method == "PATCH" and contract.path == "/tasks/{id}" and contract.framework == "hono")
            self.assertIn("body:body", patch_contract.request_hints)
            self.assertIn("body:openapi.request.body", patch_contract.request_hints)
            self.assertIn("response:openapi.responses", patch_contract.response_hints)
            self.assertEqual(["200", "404", "422"], patch_contract.status_codes)

            list_contract = next(contract for contract in facts.api_contracts if contract.method == "GET" and contract.path == "/tasks" and contract.framework == "hono")
            self.assertEqual([], list_contract.request_hints)
            self.assertEqual(["200"], list_contract.status_codes)
            self.assertEqual([], list_contract.error_hints)

            doc_contract = next(contract for contract in facts.api_contracts if contract.method == "GET" and contract.path == "/doc" and contract.framework == "hono")
            self.assertIn("response:openapi.document", doc_contract.response_hints)
            self.assertNotIn("response:scalar-api-reference", doc_contract.response_hints)


if __name__ == "__main__":
    unittest.main()
