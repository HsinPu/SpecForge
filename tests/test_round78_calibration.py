from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round78LaravelCalibrationTests(unittest.TestCase):
    def test_laravel_entrypoints_commands_and_route_provider_api_prefix_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "composer.json").write_text(
                """
{
  "require": {
    "laravel/framework": "^11.0"
  },
  "scripts": {
    "test": "@php artisan test",
    "reset": [
      "@php artisan migrate:fresh",
      "@php artisan db:seed"
    ]
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "artisan").write_text("#!/usr/bin/env php\n<?php\n", encoding="utf-8")
            (root / "public").mkdir()
            (root / "public" / "index.php").write_text("<?php require __DIR__.'/../vendor/autoload.php';\n", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "database" / "migrations").mkdir(parents=True)

            provider = root / "app" / "App" / "Providers"
            provider.mkdir(parents=True)
            (provider / "RouteServiceProvider.php").write_text(
                """
<?php
use Illuminate\\Support\\Facades\\Route;

class RouteServiceProvider {
    protected function mapWebRoutes(): void {
        Route::group([
            'middleware' => 'web',
        ], function ($router) {
            require base_path('routes/web.php');
        });
    }

    protected function mapApiRoutes(): void {
        Route::group([
            'middleware' => 'api',
            'prefix' => 'api',
        ], function ($router) {
            require base_path('routes/api.php');
        });
    }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            routes = root / "routes"
            routes.mkdir()
            (routes / "api.php").write_text(
                """
<?php
use Illuminate\\Support\\Facades\\Route;
Route::get('books/{id}', 'BookApiController@show');
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (routes / "web.php").write_text(
                """
<?php
use Illuminate\\Support\\Facades\\Route;
Route::get('/books/{slug}', 'BookController@show');
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            entrypoints = {(entry.kind, entry.path, entry.command) for entry in facts.entrypoints}
            self.assertIn(("laravel-artisan", "artisan", "php artisan"), entrypoints)
            self.assertIn(("laravel-http-front-controller", "public/index.php", "php artisan serve"), entrypoints)

            commands = {command.name for command in facts.commands}
            self.assertIn("php artisan route:list", commands)
            self.assertIn("php artisan migrate", commands)
            self.assertIn("php artisan test", commands)
            self.assertIn("composer run test", commands)
            self.assertIn("composer run reset", commands)

            routes_seen = {(route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("GET", "/api/books/{id}", "BookApiController@show"), routes_seen)
            self.assertIn(("GET", "/books/{slug}", "BookController@show"), routes_seen)
            self.assertNotIn("/books/{id}", {route.path for route in facts.api_routes})

    def test_laravel_bootstrap_with_routing_api_prefix_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "composer.json").write_text('{"require":{"laravel/framework":"^12.0"}}\n', encoding="utf-8")
            bootstrap = root / "bootstrap"
            bootstrap.mkdir()
            (bootstrap / "app.php").write_text(
                """
<?php
return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
        api: __DIR__.'/../routes/api.php',
        apiPrefix: 'api/v2',
    )->create();
""".strip()
                + "\n",
                encoding="utf-8",
            )
            routes = root / "routes"
            routes.mkdir()
            (routes / "api.php").write_text(
                """
<?php
use Illuminate\\Support\\Facades\\Route;
Route::post('/widgets', 'WidgetApiController@store');
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (routes / "web.php").write_text(
                """
<?php
use Illuminate\\Support\\Facades\\Route;
Route::get('/widgets', 'WidgetController@index');
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes_seen = {(route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("POST", "/api/v2/widgets", "WidgetApiController@store"), routes_seen)
            self.assertIn(("GET", "/widgets", "WidgetController@index"), routes_seen)


if __name__ == "__main__":
    unittest.main()
