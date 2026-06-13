from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round34AngularCalibrationTests(unittest.TestCase):
    def test_angular_nested_lazy_routes_templates_and_httpclient_concat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"dependencies":{"@angular/core":"^20.0.0","@angular/router":"^20.0.0","@angular/common":"^20.0.0"}}\n',
                encoding="utf-8",
            )
            src = root / "src"
            app = src / "app"
            profile = app / "features" / "profile"
            services = profile / "services"
            app.mkdir(parents=True)
            profile.mkdir(parents=True)
            services.mkdir(parents=True)

            (src / "index.html").write_text("<app-root></app-root>\n", encoding="utf-8")
            (app / "app.component.html").write_text(
                '<form><input name="q"></form><img src="/assets/logo.svg">\n',
                encoding="utf-8",
            )
            (app / "app.routes.ts").write_text(
                """
import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', loadComponent: () => import('./home.component') },
  {
    path: 'editor',
    children: [
      { path: '', loadComponent: () => import('./editor.component') },
      { path: ':slug', loadComponent: () => import('./editor.component') },
    ],
  },
  { path: 'profile', loadChildren: () => import('./features/profile/profile.routes') },
];
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (profile / "profile.routes.ts").write_text(
                """
import { Routes } from '@angular/router';

const routes: Routes = [
  {
    path: '',
    children: [
      {
        path: ':username',
        children: [
          { path: '', loadComponent: () => import('./profile.component') },
          { path: 'favorites', loadComponent: () => import('./favorites.component') },
        ],
      },
    ],
  },
];

export default routes;
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (services / "profile.service.ts").write_text(
                """
import { HttpClient } from '@angular/common/http';

export class ProfileService {
  constructor(private readonly http: HttpClient) {}

  get(username: string) {
    return this.http.get('/profiles/' + username);
  }

  follow(username: string) {
    return this.http
      .post('/profiles/' + username + '/follow', {});
  }

  update(article: { slug: string }) {
    return this.http
      .put(`/articles/${article.slug}`, {});
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.kind, route.route, route.path) for route in facts.frontend_routes}
            self.assertIn(("angular-route", "/", "src/app/app.routes.ts"), routes)
            self.assertIn(("angular-route", "/editor", "src/app/app.routes.ts"), routes)
            self.assertIn(("angular-route", "/editor/:slug", "src/app/app.routes.ts"), routes)
            self.assertIn(("angular-lazy-route", "/profile/:username", "src/app/features/profile/profile.routes.ts"), routes)
            self.assertIn(
                ("angular-lazy-route", "/profile/:username/favorites", "src/app/features/profile/profile.routes.ts"),
                routes,
            )

            pages = {(page.route, page.path) for page in facts.pages}
            self.assertIn(("/", "src/index.html"), pages)
            self.assertNotIn(("/src/app/app.component", "src/app/app.component.html"), pages)

            forms = {(form.source, tuple(form.fields)) for form in facts.forms}
            self.assertIn(("src/app/app.component.html", ("q",)), forms)

            api_calls = {(call.method, call.endpoint, call.path) for call in facts.api_calls}
            self.assertIn(("GET", "/profiles/:username", "src/app/features/profile/services/profile.service.ts"), api_calls)
            self.assertIn(("POST", "/profiles/:username/follow", "src/app/features/profile/services/profile.service.ts"), api_calls)
            self.assertIn(("PUT", "/articles/:slug", "src/app/features/profile/services/profile.service.ts"), api_calls)


if __name__ == "__main__":
    unittest.main()
