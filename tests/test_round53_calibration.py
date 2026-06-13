from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round53EmberCalibrationTests(unittest.TestCase):
    def test_ember_routes_templates_components_and_state_without_vue_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = root / "packages" / "test-app" / "app"
            component_dir = app / "components"
            template_dir = app / "templates"
            engine_dir = root / "packages" / "test-app" / "lib" / "my-engine" / "addon"
            store_dir = root / "packages" / "ember-simple-auth" / "src" / "session-stores"
            component_dir.mkdir(parents=True)
            template_dir.mkdir(parents=True)
            engine_dir.mkdir(parents=True)
            store_dir.mkdir(parents=True)
            (root / "package.json").write_text(
                '{"devDependencies":{"ember-source":"~5.0.0","@ember/test-helpers":"*"}}\n',
                encoding="utf-8",
            )
            (app / "router.js").write_text(
                """
import EmberRouter from '@ember/routing/router';

class Router extends EmberRouter {}

Router.map(function () {
  this.route('login');
  this.route('protected');
  this.route('admin', { path: '/admin-area' }, function () {
    this.route('users');
  });
  this.mount('my-engine', { as: 'engine', path: '/engine' });
});
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (engine_dir / "routes.js").write_text(
                """
export default function () {
  this.route('protected');
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (engine_dir / "templates").mkdir()
            (engine_dir / "templates" / "protected.hbs").write_text("Protected engine page\n", encoding="utf-8")
            (template_dir / "login.hbs").write_text("<LoginForm />\n", encoding="utf-8")
            (template_dir / "application.hbs").write_text("{{outlet}}\n", encoding="utf-8")
            (component_dir / "login-form.hbs").write_text(
                """
<form {{on "submit" this.authenticate}}>
  <input name="identification" />
</form>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (component_dir / "login-form.js").write_text(
                """
import Component from '@glimmer/component';
import { tracked } from '@glimmer/tracking';
import { service } from '@ember/service';

export default class LoginFormComponent extends Component {
  @service session;
  @tracked identification;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (store_dir / "cookie.ts").write_text(
                """
import { computed } from '@ember/object';

export default function cookieExpirationTime() {
  return computed({ get() { return null; } });
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("ember", "frontend"), frameworks)

            routes = {(route.framework, route.kind, route.route, route.path) for route in facts.frontend_routes}
            self.assertIn(("ember", "ember-route", "/login", "packages/test-app/app/router.js"), routes)
            self.assertIn(("ember", "ember-route", "/protected", "packages/test-app/app/router.js"), routes)
            self.assertIn(("ember", "ember-route", "/admin-area/users", "packages/test-app/app/router.js"), routes)
            self.assertIn(("ember", "ember-mount-route", "/engine", "packages/test-app/app/router.js"), routes)
            self.assertIn(("ember", "ember-engine-route", "/engine/protected", "packages/test-app/lib/my-engine/addon/routes.js"), routes)
            self.assertIn(("handlebars", "template-page-route", "/login", "packages/test-app/app/templates/login.hbs"), routes)
            self.assertNotIn(
                ("handlebars", "template-page-route", "/protected", "packages/test-app/lib/my-engine/addon/templates/protected.hbs"),
                routes,
            )
            self.assertNotIn(
                ("handlebars", "template-page-route", "/packages/test-app/app/components/login-form", "packages/test-app/app/components/login-form.hbs"),
                routes,
            )
            self.assertFalse(any(route.path.endswith("application.hbs") for route in facts.frontend_routes))

            components = {(component.name, component.framework, component.path) for component in facts.components}
            self.assertIn(("LoginFormComponent", "ember", "packages/test-app/app/components/login-form.js"), components)
            self.assertIn(("LoginFormComponent", "ember", "packages/test-app/app/components/login-form.hbs"), components)

            state = {(usage.library, usage.usage, usage.name, usage.source) for usage in facts.state_usages}
            self.assertIn(("ember", "service", "session", "packages/test-app/app/components/login-form.js"), state)
            self.assertIn(("ember", "tracked", "identification", "packages/test-app/app/components/login-form.js"), state)
            self.assertFalse(any(usage.library == "vue" for usage in facts.state_usages))


if __name__ == "__main__":
    unittest.main()
