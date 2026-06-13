from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round143LaravelInvoiceNinjaCalibrationTests(unittest.TestCase):
    def test_laravel_fluent_prefix_array_handlers_and_resource_only_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "composer.json").write_text('{"require":{"laravel/framework":"^11.0"}}\n', encoding="utf-8")
            routes = root / "routes"
            routes.mkdir()
            (routes / "shop.php").write_text(
                """
<?php
use App\\Http\\Controllers\\Shop;
use Illuminate\\Support\\Facades\\Route;

Route::middleware('company_key_db')->prefix('api/v1')->group(function () {
    Route::get('shop/products', [Shop\\ProductController::class, 'index']);
    Route::post('shop/invoices', [Shop\\InvoiceController::class, 'store']);
});
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (routes / "contact.php").write_text(
                """
<?php
use App\\Http\\Controllers\\Contact;
use Illuminate\\Support\\Facades\\Route;

Route::middleware('contact_db')->prefix('api/v1/contact')->name('api.contact.')->group(function () {
    Route::get('invoices', [Contact\\InvoiceController::class, 'index']);
});
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (routes / "client.php").write_text(
                """
<?php
use Illuminate\\Support\\Facades\\Route;

Route::group(['prefix' => 'client'], function () {
    Route::get('dashboard', [App\\Http\\Controllers\\ClientPortal\\DashboardController::class, 'index']);
    Route::resource('documents', App\\Http\\Controllers\\ClientPortal\\DocumentController::class)->only(['index', 'show']);
});
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)
            seen = {(route.method, route.path, route.handler, route.kind) for route in facts.api_routes}

            self.assertIn(("GET", "/api/v1/shop/products", "Shop\\ProductController@index", "laravel-route"), seen)
            self.assertIn(("POST", "/api/v1/shop/invoices", "Shop\\InvoiceController@store", "laravel-route"), seen)
            self.assertIn(("GET", "/api/v1/contact/invoices", "Contact\\InvoiceController@index", "laravel-route"), seen)
            self.assertIn(
                (
                    "GET",
                    "/client/dashboard",
                    "App\\Http\\Controllers\\ClientPortal\\DashboardController@index",
                    "laravel-route",
                ),
                seen,
            )
            self.assertIn(
                (
                    "GET",
                    "/client/documents",
                    "App\\Http\\Controllers\\ClientPortal\\DocumentController@index",
                    "laravel-resource-route",
                ),
                seen,
            )
            self.assertIn(
                (
                    "GET",
                    "/client/documents/{document}",
                    "App\\Http\\Controllers\\ClientPortal\\DocumentController@show",
                    "laravel-resource-route",
                ),
                seen,
            )

            self.assertNotIn("/shop/products", {route.path for route in facts.api_routes})
            self.assertNotIn("/contact/invoices", {route.path for route in facts.api_routes})
            self.assertNotIn("/client/documents/create", {route.path for route in facts.api_routes})


if __name__ == "__main__":
    unittest.main()
