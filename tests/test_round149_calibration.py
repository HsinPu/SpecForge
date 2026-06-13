from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round149ReactRouterCalibrationTests(unittest.TestCase):
    def test_react_router_jsx_nested_routes_are_joined_with_parent_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "react": "^18.0.0",
    "react-router": "^5.0.0",
    "react-router-dom": "^6.0.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            src = root / "src"
            src.mkdir()
            (src / "routes.tsx").write_text(
                """
import { Route } from "react-router";

const objectRoutes = [{ path: "/object-route" }];

export function getMetricRoutes() {
  return (
    <>
      <Route path="metrics">
        <Route path="new" component={NewMetricPage} />
        <Route path=":cardId" component={MetricAboutPage} />
        <Route
          path=":cardId/dependencies"
          component={MetricDependenciesPage}
        >
          <Route path="graph" component={DependencyGraphPage} />
        </Route>
      </Route>
      <Route path="/settings" element={<div />} />
      <Route path="/absolute">
        <Route path="child" component={ChildPage} />
      </Route>
      <Route path="/admin" component={AdminLayout}>
        <Route component={AdminApp}>
          <Route path="people">
            <Route component={PeopleLayout}>
              <Route path=":userId">
                <Route path="edit" component={EditUserModal} />
                <ModalRoute path="success" modal={UserSuccessModal} noWrap />
              </Route>
            </Route>
          </Route>
        </Route>
      </Route>
    </>
  );
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.route, route.framework, route.kind) for route in facts.frontend_routes}
            self.assertIn(("/metrics", "react", "react-router-route"), routes)
            self.assertIn(("/metrics/new", "react", "react-router-route"), routes)
            self.assertIn(("/metrics/:cardId", "react", "react-router-route"), routes)
            self.assertIn(("/metrics/:cardId/dependencies", "react", "react-router-route"), routes)
            self.assertIn(("/metrics/:cardId/dependencies/graph", "react", "react-router-route"), routes)
            self.assertIn(("/settings", "react", "react-router-route"), routes)
            self.assertIn(("/absolute/child", "react", "react-router-route"), routes)
            self.assertIn(("/admin/people/:userId/edit", "react", "react-router-route"), routes)
            self.assertIn(("/admin/people/:userId/success", "react", "react-router-route"), routes)
            self.assertIn(("/object-route", "react", "react-router-route"), routes)
            self.assertNotIn((":cardId", "react", "react-router-route"), routes)
            self.assertNotIn((":userId", "react", "react-router-route"), routes)
            self.assertNotIn(("/success", "react", "react-router-route"), routes)
            self.assertNotIn(("new", "react", "react-router-route"), routes)


if __name__ == "__main__":
    unittest.main()
