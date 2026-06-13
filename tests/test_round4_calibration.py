from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round4CalibrationTests(unittest.TestCase):

    def test_scan_project_detects_round4_framework_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "@angular/core": "^20.0.0",
    "@nestjs/common": "^10.0.0",
    "@nestjs/core": "^10.0.0",
    "@nuxt/devtools": "^1.0.0",
    "ember-source": "^5.0.0",
    "nuxt": "^3.0.0",
    "vue": "^3.0.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "nuxt.config.ts").write_text("export default defineNuxtConfig({});\n", encoding="utf-8")
            nuxt_page = root / "pages" / "users"
            nuxt_page.mkdir(parents=True)
            (nuxt_page / "[id].vue").write_text("<template><main /></template>\n", encoding="utf-8")

            angular_dir = root / "src" / "app"
            angular_dir.mkdir(parents=True)
            (angular_dir / "profile.component.ts").write_text(
                """
import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-profile',
  template: '<div>{{name}}</div>'
})
export class ProfileComponent {
  @Input() name = '';
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (angular_dir / "app.routes.ts").write_text(
                """
export const routes = [
  { path: 'settings', loadComponent: () => import('./profile.component') }
];
""".strip()
                + "\n",
                encoding="utf-8",
            )

            nest_src = root / "nest"
            nest_src.mkdir()
            (nest_src / "article.controller.ts").write_text(
                """
import { Controller, Get, Post, Param } from '@nestjs/common';

@Controller('articles')
export class ArticleController {
  @Get(':slug')
  findOne(@Param('slug') slug: string) {}

  @Post()
  create() {}
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            (root / "requirements.txt").write_text("Django==5.0\ndjangorestframework==3.15\n", encoding="utf-8")
            django_dir = root / "conduit" / "apps" / "articles"
            django_dir.mkdir(parents=True)
            (django_dir / "urls.py").write_text(
                """
from django.urls import path
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'articles', ArticleViewSet)

urlpatterns = [
    path('profiles/<str:username>/', ProfileView.as_view()),
]
""".strip()
                + "\n",
                encoding="utf-8",
            )

            (root / "go.mod").write_text(
                "module demo\n\nrequire github.com/labstack/echo/v4 v4.12.0\n",
                encoding="utf-8",
            )
            (root / "main.go").write_text(
                """
package main

import "github.com/labstack/echo/v4"

func main() {
  e := echo.New()
  api := e.Group("/api")
  api.GET("/users/:id", getUser)
}

func getUser(c echo.Context) error { return nil }
""".strip()
                + "\n",
                encoding="utf-8",
            )

            (root / "Cargo.toml").write_text(
                """
[package]
name = "demo"
version = "0.1.0"

[dependencies]
axum = "0.7"
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "src").mkdir(exist_ok=True)
            (root / "src" / "lib.rs").write_text(
                """
use axum::{routing::{get, post}, Router};

pub fn routes() -> Router {
  Router::new()
    .route("/api/users", post(create_user))
    .route("/api/user", get(current_user).put(update_user))
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            (root / "composer.json").write_text(
                '{"require":{"symfony/framework-bundle":"^7.0","symfony/routing":"^7.0"}}\n',
                encoding="utf-8",
            )
            php_controller = root / "src" / "Controller"
            php_controller.mkdir(parents=True, exist_ok=True)
            (php_controller / "BlogController.php").write_text(
                """
<?php
use Symfony\\Component\\Routing\\Attribute\\Route;

#[Route('/blog')]
class BlogController {
  #[Route('/posts/{slug}', methods: ['GET'])]
  public function post() {}
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            (root / "BlazorDemo.csproj").write_text(
                """
<Project Sdk="Microsoft.NET.Sdk.Web">
  <ItemGroup>
    <PackageReference Include="Microsoft.AspNetCore.Blazor" Version="0.7.0" />
  </ItemGroup>
</Project>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            blazor_pages = root / "BlazorApp" / "Pages"
            blazor_pages.mkdir(parents=True)
            (blazor_pages / "Counter.cshtml").write_text('@page "/counter"\n<h1>Counter</h1>\n', encoding="utf-8")

            ember_app = root / "app"
            (ember_app / "components").mkdir(parents=True)
            (ember_app / "router.js").write_text(
                """
import EmberRouter from '@ember/routing/router';

Router.map(function () {
  this.route('editor', function () {
    this.route('edit', { path: ':id' });
  });
  this.route('profile', { path: 'profile/:id' });
});
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (ember_app / "components" / "article-card.js").write_text(
                """
import Component from '@glimmer/component';

export default class ArticleCardComponent extends Component {}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            framework_names = {framework.name for framework in facts.frameworks}
            self.assertTrue(
                {
                    "angular",
                    "axum",
                    "blazor",
                    "django",
                    "drf",
                    "echo",
                    "ember",
                    "nestjs",
                    "nuxt",
                    "symfony",
                }
                <= framework_names
            )
            self.assertIn("ProfileComponent", {component.name for component in facts.components})
            self.assertIn("ArticleCardComponent", {component.name for component in facts.components})
            self.assertIn("Counter", {component.name for component in facts.components})
            self.assertIn("/users/:id", {route.route for route in facts.frontend_routes})
            self.assertIn("/settings", {route.route for route in facts.frontend_routes})
            self.assertIn("/counter", {route.route for route in facts.frontend_routes})
            self.assertIn("/editor", {route.route for route in facts.frontend_routes})
            self.assertIn("/editor/:id", {route.route for route in facts.frontend_routes})
            self.assertIn("/profile/:id", {route.route for route in facts.frontend_routes})
            api_routes = {(route.framework, route.method, route.path) for route in facts.api_routes}
            self.assertIn(("nestjs", "GET", "/articles/:slug"), api_routes)
            self.assertIn(("nestjs", "POST", "/articles"), api_routes)
            self.assertIn(("django", "ANY", "/profiles/<str:username>"), api_routes)
            self.assertIn(("drf", "ANY", "/articles"), api_routes)
            self.assertIn(("echo", "GET", "/api/users/:id"), api_routes)
            self.assertIn(("axum", "POST", "/api/users"), api_routes)
            self.assertIn(("axum", "GET", "/api/user"), api_routes)
            self.assertIn(("axum", "PUT", "/api/user"), api_routes)
            self.assertIn(("symfony", "GET", "/blog/posts/{slug}"), api_routes)
            self.assertNotIn(("symfony", "ANY", "/blog/blog"), api_routes)
            self.assertNotIn("gin", framework_names)

    def test_vue_pages_are_not_nuxt_without_nuxt_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"dependencies":{"vue":"^3.0.0","vite":"^7.0.0"}}\n',
                encoding="utf-8",
            )
            pages = root / "src" / "pages"
            pages.mkdir(parents=True)
            (pages / "Home.vue").write_text("<template><main /></template>\n", encoding="utf-8")

            facts = scan_project(root)

            framework_names = {framework.name for framework in facts.frameworks}
            self.assertIn("vue", framework_names)
            self.assertNotIn("nuxt", framework_names)
            self.assertNotIn("nuxt", {route.framework for route in facts.frontend_routes})

    def test_go_router_path_is_not_gin_without_gin_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "go.mod").write_text(
                "module demo\n\nrequire github.com/labstack/echo/v4 v4.12.0\n",
                encoding="utf-8",
            )
            router_dir = root / "internal" / "router"
            router_dir.mkdir(parents=True)
            (router_dir / "router.go").write_text(
                """
package router

import "github.com/labstack/echo/v4"

func Mount(e *echo.Echo) {
  e.GET("/health", health)
}

func health(c echo.Context) error { return nil }
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            framework_names = {framework.name for framework in facts.frameworks}
            self.assertIn("echo", framework_names)
            self.assertNotIn("gin", framework_names)

    def test_nest_module_path_is_not_angular_without_angular_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"dependencies":{"@nestjs/common":"^10.0.0","@nestjs/core":"^10.0.0"}}\n',
                encoding="utf-8",
            )
            src = root / "src"
            src.mkdir()
            (src / "app.module.ts").write_text(
                """
import { Module } from '@nestjs/common';

@Module({})
export class AppModule {}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            framework_names = {framework.name for framework in facts.frameworks}
            self.assertIn("nestjs", framework_names)
            self.assertNotIn("angular", framework_names)


if __name__ == "__main__":
    unittest.main()
