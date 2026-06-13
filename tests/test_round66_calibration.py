from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round66StrapiMonorepoCalibrationTests(unittest.TestCase):
    def test_strapi_monorepo_without_yarn_fastify_or_solid_route_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".yarn" / "releases").mkdir(parents=True)
            (root / "packages" / "core" / "content-type-builder" / "admin" / "src" / "components").mkdir(parents=True)
            (root / "packages" / "core" / "admin" / "admin" / "src" / "services").mkdir(parents=True)
            (root / "packages" / "core" / "admin" / "server" / "src" / "routes").mkdir(parents=True)

            (root / "package.json").write_text(
                '{"dependencies":{"@strapi/strapi":"5.0.0","react":"^18.0.0"}}\n',
                encoding="utf-8",
            )
            (root / ".yarn" / "releases" / "yarn-4.12.0.cjs").write_text(
                """
const fastify = require('fastify');
fastify().get('/internal-yarn-runtime', () => {});
""".lstrip(),
                encoding="utf-8",
            )
            (
                root
                / "packages"
                / "core"
                / "admin"
                / "admin"
                / "src"
                / "services"
                / "admin.ts"
            ).write_text(
                """
export function loadInit(client: { get(path: string): Promise<unknown> }) {
  return client.get('/admin/init');
}
""".lstrip(),
                encoding="utf-8",
            )
            (
                root
                / "packages"
                / "core"
                / "content-type-builder"
                / "admin"
                / "src"
                / "components"
                / "ConditionForm.tsx"
            ).write_text(
                """
import React, { Suspense } from 'react';

export function ConditionForm() {
  const action = 'show';
  return <Suspense fallback={null}><section>{action}</section></Suspense>;
}
""".lstrip(),
                encoding="utf-8",
            )
            (
                root
                / "packages"
                / "core"
                / "admin"
                / "server"
                / "src"
                / "routes"
                / "admin.ts"
            ).write_text(
                """
export default [
  {
    method: 'GET',
    path: '/init',
    handler: 'admin.init',
  },
];
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("strapi", "backend"), frameworks)
            self.assertNotIn(("fastify", "backend"), frameworks)
            self.assertNotIn(("solid", "frontend"), frameworks)
            self.assertNotIn(("solid-start", "frontend"), frameworks)

            routes = {(route.framework, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("strapi", "GET", "/admin/init", "admin.init"), routes)
            self.assertFalse(any(route.kind == "solid-start-file-route" for route in facts.frontend_routes))
            self.assertFalse(any(route.framework == "fastify" for route in facts.api_routes))
            self.assertTrue(
                any(
                    link.endpoint == "/admin/init"
                    and link.matched_route == "/admin/init"
                    and link.matched_framework == "strapi"
                    for link in facts.api_links
                )
            )


if __name__ == "__main__":
    unittest.main()
