from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round59QwikCalibrationTests(unittest.TestCase):
    def test_qwik_city_routes_components_state_and_handlers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            routes = root / "src" / "routes"
            user_route = routes / "users" / "[id]"
            api_route = routes / "api" / "add"
            json_route = routes / "files" / "[name].json"
            routes.mkdir(parents=True)
            user_route.mkdir(parents=True)
            api_route.mkdir(parents=True)
            json_route.mkdir(parents=True)
            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "@builder.io/qwik": "^1.10.0",
    "@builder.io/qwik-city": "^1.10.0"
  },
  "devDependencies": {
    "vite": "^6.0.0"
  }
}
""".lstrip(),
                encoding="utf-8",
            )
            (routes / "index.tsx").write_text(
                """
import { component$, useContext, useSignal } from '@builder.io/qwik';
import { routeLoader$ } from '@builder.io/qwik-city';

export const useHome = routeLoader$(() => ({ title: 'Home' }));

export default component$(() => {
  const count = useSignal(0);
  const theme = useContext({} as never);
  return <main>{count.value}</main>;
});
""".lstrip(),
                encoding="utf-8",
            )
            (user_route / "index.tsx").write_text(
                """
import { component$ } from '@builder.io/qwik';

export const UserCard = component$(() => <div>User</div>);
""".lstrip(),
                encoding="utf-8",
            )
            (api_route / "index.tsx").write_text(
                """
import type { RequestHandler } from '@builder.io/qwik-city';

export const onGet: RequestHandler = async ({ query, json }) => {
  return json(200, { value: query.get('value') });
};

export const onPost: RequestHandler = async ({ parseBody, json }) => {
  const body = await parseBody();
  return json(201, body);
};
""".lstrip(),
                encoding="utf-8",
            )
            (routes / "users" / "layout.tsx").write_text(
                """
import type { RequestHandler } from '@builder.io/qwik-city';

export const onRequest: RequestHandler = async ({ next }) => {
  return next();
};
""".lstrip(),
                encoding="utf-8",
            )
            (json_route / "index.ts").write_text(
                """
import type { RequestHandler } from '@builder.io/qwik-city';

export const onGet: RequestHandler = async ({ json }) => json(200, {});
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("qwik", "frontend"), frameworks)
            self.assertIn(("qwik-city", "frontend"), frameworks)
            self.assertIn(("qwik-city", "backend"), frameworks)

            frontend_routes = {(route.route, route.framework, route.kind) for route in facts.frontend_routes}
            self.assertIn(("/", "qwik-city", "qwik-city-file-route"), frontend_routes)
            self.assertIn(("/users/{id}", "qwik-city", "qwik-city-file-route"), frontend_routes)
            self.assertIn(("/api/add", "qwik-city", "qwik-city-file-route"), frontend_routes)
            self.assertFalse(any(route.framework == "fresh" for route in facts.frontend_routes))

            components = {(component.name, component.framework) for component in facts.components}
            self.assertIn(("Index", "qwik"), components)
            self.assertIn(("UserCard", "qwik"), components)
            self.assertFalse(any(component.framework == "react" for component in facts.components))

            state = {(usage.library, usage.usage, usage.name) for usage in facts.state_usages}
            self.assertIn(("qwik", "signal", "useSignal"), state)
            self.assertIn(("qwik-city", "route-data", "routeLoader$"), state)
            self.assertNotIn(("react", "hook", "useContext"), state)

            api_routes = {(route.method, route.path, route.framework, route.kind) for route in facts.api_routes}
            self.assertIn(("GET", "/api/add", "qwik-city", "qwik-city-route-handler"), api_routes)
            self.assertIn(("POST", "/api/add", "qwik-city", "qwik-city-route-handler"), api_routes)
            self.assertIn(("ANY", "/users", "qwik-city", "qwik-city-route-handler"), api_routes)
            self.assertIn(("GET", "/files/{name}.json", "qwik-city", "qwik-city-route-handler"), api_routes)
            self.assertNotIn(("ANY", "/users/layout", "qwik-city", "qwik-city-route-handler"), api_routes)
            self.assertFalse(any(route.framework in {"express", "fresh"} for route in facts.api_routes))
            post_route = next(route for route in facts.api_routes if route.method == "POST" and route.path == "/api/add")
            self.assertEqual("body", post_route.request_body)
            self.assertEqual("json", post_route.response_type)


if __name__ == "__main__":
    unittest.main()
