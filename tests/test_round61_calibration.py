from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round61TanStackRouterCalibrationTests(unittest.TestCase):
    def test_tanstack_router_and_start_routes_without_react_router_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            routes = root / "src" / "routes"
            routes.mkdir(parents=True)
            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "@tanstack/react-router": "^1.0.0",
    "@tanstack/react-start": "^1.0.0"
  }
}
""".lstrip(),
                encoding="utf-8",
            )
            (routes / "__root.tsx").write_text(
                """
import { createRootRouteWithContext } from '@tanstack/react-router';

type RouterContext = { userId?: string };

export const Route = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
});

function RootLayout() {
  return <main />;
}
""".lstrip(),
                encoding="utf-8",
            )
            (routes / "index.tsx").write_text(
                """
import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/')({
  component: Home,
});

function Home() {
  return <section />;
}
""".lstrip(),
                encoding="utf-8",
            )
            (routes / "users.$id.tsx").write_text(
                """
import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/users/$id')({
  component: UserPage,
});

function UserPage() {
  return <section />;
}
""".lstrip(),
                encoding="utf-8",
            )
            (routes / "docs.$.tsx").write_text(
                """
import { createLazyFileRoute } from '@tanstack/react-router';

export const Route = createLazyFileRoute('/docs/$')({
  component: DocsCatchAll,
});
""".lstrip(),
                encoding="utf-8",
            )
            (root / "src" / "server-functions.ts").write_text(
                """
import { createServerFn } from '@tanstack/react-start';

export const getUser = createServerFn({ method: 'GET' }).handler(async () => ({ id: '1' }));
""".lstrip(),
                encoding="utf-8",
            )
            (root / "src" / "route-docs.ts").write_text(
                """
import '@tanstack/react-router';

// createFileRoute('/commented')({})
const warning = `Use createFileRoute('/string-only')({}) in real route files`;
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("tanstack-router", "frontend"), frameworks)
            self.assertIn(("tanstack-start", "frontend"), frameworks)
            self.assertNotIn(("react-router", "frontend"), frameworks)
            self.assertNotIn(("qwik", "frontend"), frameworks)
            self.assertNotIn(("solid-router", "frontend"), frameworks)
            self.assertNotIn(("solid-start", "frontend"), frameworks)

            routes_found = {(route.route, route.framework, route.kind) for route in facts.frontend_routes}
            self.assertIn(("/", "tanstack-router", "tanstack-root-route"), routes_found)
            self.assertIn(("/", "tanstack-router", "tanstack-file-route"), routes_found)
            self.assertIn(("/users/{id}", "tanstack-router", "tanstack-file-route"), routes_found)
            self.assertIn(("/docs/{*}", "tanstack-router", "tanstack-file-route"), routes_found)
            self.assertNotIn(("/commented", "tanstack-router", "tanstack-file-route"), routes_found)
            self.assertNotIn(("/string-only", "tanstack-router", "tanstack-file-route"), routes_found)
            self.assertFalse(any(route.kind in {"react-router-route", "vue-router-route"} for route in facts.frontend_routes))

            state = {(usage.library, usage.usage, usage.name) for usage in facts.state_usages}
            self.assertIn(("tanstack-start", "server-function", "createServerFn"), state)


if __name__ == "__main__":
    unittest.main()
