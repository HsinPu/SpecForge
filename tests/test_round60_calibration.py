from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round60SolidStartCalibrationTests(unittest.TestCase):
    def test_solid_start_routes_components_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            routes = root / "src" / "routes"
            user_route = routes / "users"
            optional_route = routes / "[[option]]"
            api = root / "src" / "lib"
            routes.mkdir(parents=True)
            user_route.mkdir()
            optional_route.mkdir()
            api.mkdir(parents=True)
            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "solid-js": "^1.9.0",
    "@solidjs/router": "^0.15.0",
    "@solidjs/start": "^1.0.0"
  }
}
""".lstrip(),
                encoding="utf-8",
            )
            (routes / "index.tsx").write_text(
                """
import { createSignal } from 'solid-js';
import { createAsync } from '@solidjs/router';
import { getUser } from '../lib/api';

export default function Home() {
  const [count, setCount] = createSignal(0);
  const user = createAsync(() => getUser('1'));
  return <main>{count()}</main>;
}
""".lstrip(),
                encoding="utf-8",
            )
            (user_route / "[id].tsx").write_text(
                """
import type { RouteSectionProps } from '@solidjs/router';

export default function UserPage(props: RouteSectionProps) {
  return <div>{props.params.id}</div>;
}
""".lstrip(),
                encoding="utf-8",
            )
            (optional_route / "thing.tsx").write_text(
                """
export default function OptionalThing() {
  return <div>Optional</div>;
}
""".lstrip(),
                encoding="utf-8",
            )
            (api / "api.ts").write_text(
                """
import { action, query } from '@solidjs/router';

export const getUser = query(async (id: string) => ({ id }));
export const saveUser = action(async (formData: FormData) => formData);
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("solid", "frontend"), frameworks)
            self.assertIn(("solid-router", "frontend"), frameworks)
            self.assertIn(("solid-start", "frontend"), frameworks)
            self.assertNotIn(("react", "frontend"), frameworks)

            routes_found = {(route.route, route.framework, route.kind) for route in facts.frontend_routes}
            self.assertIn(("/", "solid-start", "solid-start-file-route"), routes_found)
            self.assertIn(("/users/{id}", "solid-start", "solid-start-file-route"), routes_found)
            self.assertIn(("/{option?}/thing", "solid-start", "solid-start-file-route"), routes_found)

            components = {(component.name, component.framework) for component in facts.components}
            self.assertIn(("Home", "solid"), components)
            self.assertIn(("UserPage", "solid"), components)
            self.assertFalse(any(component.framework == "react" for component in facts.components))

            state = {(usage.library, usage.usage, usage.name) for usage in facts.state_usages}
            self.assertIn(("solid", "signal", "createSignal"), state)
            self.assertIn(("solid-router", "route-data", "createAsync"), state)
            self.assertIn(("solid-router", "route-data", "query"), state)
            self.assertIn(("solid-router", "route-data", "action"), state)
            self.assertFalse(any(usage.library == "react" for usage in facts.state_usages))


if __name__ == "__main__":
    unittest.main()
