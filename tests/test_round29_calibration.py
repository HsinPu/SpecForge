from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round29CalibrationTests(unittest.TestCase):

    def test_scan_project_composes_laravel_file_and_group_prefixes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "composer.json").write_text(
                '{"require":{"laravel/framework":"^11.0"}}\n',
                encoding="utf-8",
            )
            provider = root / "app" / "Providers"
            provider.mkdir(parents=True)
            (provider / "Route.php").write_text(
                """
<?php
class Route {
    protected function mapAdminRoutes() {
        Facade::prefix('{tenant}')
            ->middleware('admin')
            ->group(base_path('routes/admin.php'));
    }

    protected function mapApiRoutes() {
        Facade::prefix(config('api.prefix'))
            ->middleware('api')
            ->group(base_path('routes/api.php'));
    }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            config = root / "config"
            config.mkdir()
            (config / "api.php").write_text(
                "<?php return ['prefix' => env('API_PREFIX', 'api')];\n",
                encoding="utf-8",
            )
            routes = root / "routes"
            routes.mkdir()
            (routes / "admin.php").write_text(
                """
<?php
use Illuminate\\Support\\Facades\\Route;

Route::group(['prefix' => 'common'], function () {
    Route::get('companies/autocomplete', 'Common\\Companies@autocomplete');
    Route::resource('companies', 'Common\\Companies');
});

Route::group(['prefix' => 'auth'], function () {
    Route::get('logout', 'Auth\\Login@destroy');
});
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (routes / "api.php").write_text(
                """
<?php
use Illuminate\\Support\\Facades\\Route;

Route::group(['as' => 'api.'], function () {
    Route::get('ping', 'Common\\Ping@pong');
    Route::apiResource('users', 'Auth\\Users');
    Route::apiResource('documents.transactions', 'Document\\Transactions');
});
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes_seen = {(route.method, route.path, route.handler, route.kind) for route in facts.api_routes}
            self.assertIn(
                ("GET", "/{tenant}/common/companies/autocomplete", "Common\\Companies@autocomplete", "laravel-route"),
                routes_seen,
            )
            self.assertIn(
                ("GET", "/{tenant}/common/companies", "Common\\Companies@index", "laravel-resource-route"),
                routes_seen,
            )
            self.assertIn(
                ("GET", "/{tenant}/common/companies/create", "Common\\Companies@create", "laravel-resource-route"),
                routes_seen,
            )
            self.assertIn(
                ("GET", "/{tenant}/common/companies/{company}", "Common\\Companies@show", "laravel-resource-route"),
                routes_seen,
            )
            self.assertIn(
                ("PATCH", "/{tenant}/common/companies/{company}", "Common\\Companies@update", "laravel-resource-route"),
                routes_seen,
            )
            self.assertIn(
                ("GET", "/{tenant}/auth/logout", "Auth\\Login@destroy", "laravel-route"),
                routes_seen,
            )
            self.assertIn(("GET", "/api/ping", "Common\\Ping@pong", "laravel-route"), routes_seen)
            self.assertIn(("GET", "/api/users", "Auth\\Users@index", "laravel-api-resource-route"), routes_seen)
            self.assertIn(("POST", "/api/users", "Auth\\Users@store", "laravel-api-resource-route"), routes_seen)
            self.assertIn(
                ("GET", "/api/users/{user}", "Auth\\Users@show", "laravel-api-resource-route"),
                routes_seen,
            )
            self.assertIn(
                (
                    "GET",
                    "/api/documents/{document}/transactions/{transaction}",
                    "Document\\Transactions@show",
                    "laravel-api-resource-route",
                ),
                routes_seen,
            )

            paths = {route.path for route in facts.api_routes}
            self.assertNotIn("/common/companies/autocomplete", paths)
            self.assertNotIn("/companies/autocomplete", paths)
            self.assertNotIn("/ping", paths)
            self.assertNotIn("/api/users/create", paths)


if __name__ == "__main__":
    unittest.main()
