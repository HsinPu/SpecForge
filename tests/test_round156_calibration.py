from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round156LaravelNamedRouteLinkCalibrationTests(unittest.TestCase):
    def test_blade_named_route_api_call_links_to_laravel_backend_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "composer.json").write_text('{"require":{"laravel/framework":"^11.0"}}\n', encoding="utf-8")

            routes = root / "routes"
            routes.mkdir()
            (routes / "client.php").write_text(
                """
<?php
use Illuminate\\Support\\Facades\\Route;

Route::prefix('client')->group(function () {
    Route::post('payments/process/response', [App\\Http\\Controllers\\ClientPortal\\PaymentController::class, 'response'])->name('client.payments.response')->middleware(['locale']);
    Route::get('payments/process/response', [App\\Http\\Controllers\\ClientPortal\\PaymentController::class, 'response'])->name('client.payments.response.get');
});
""".strip()
                + "\n",
                encoding="utf-8",
            )

            views = root / "resources" / "views" / "portal"
            views.mkdir(parents=True)
            (views / "paypal.blade.php").write_text(
                """
<script>
fetch('{{ route('client.payments.response') }}', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' }
});
</script>
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            route = next(
                route
                for route in facts.api_routes
                if route.framework == "laravel"
                and route.method == "POST"
                and route.path == "/client/payments/process/response"
            )
            self.assertEqual("laravel-route-name:client.payments.response", route.evidence.note)

            link = next(
                link
                for link in facts.api_links
                if link.endpoint == "route:client.payments.response"
            )
            self.assertEqual("/client/payments/process/response", link.matched_route)
            self.assertEqual("POST", link.matched_method)
            self.assertEqual("laravel", link.matched_framework)
            self.assertEqual("named-route", link.match_type)
            self.assertEqual("high", link.confidence)

            call = next(call for call in facts.api_calls if call.endpoint == "route:client.payments.response")
            self.assertEqual("POST /client/payments/process/response", call.matched_route)


if __name__ == "__main__":
    unittest.main()
