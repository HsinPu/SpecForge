from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round162LaravelNamedRouteCalibrationTests(unittest.TestCase):
    def test_laravel_group_name_prefixes_and_resource_names_link_blade_forms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "composer.json").write_text('{"require":{"laravel/framework":"^12.0"}}\n', encoding="utf-8")
            routes = root / "routes"
            views = root / "resources" / "views" / "portal"
            routes.mkdir()
            views.mkdir(parents=True)
            (routes / "client.php").write_text(
                """
<?php
use Illuminate\\Support\\Facades\\Route;

Route::group(['prefix' => 'client', 'as' => 'client.'], function () {
    Route::post('payments/process', [PaymentController::class, 'process'])->name('payments.process');
    Route::resource('documents', DocumentController::class)->only(['index', 'show']);
    Route::resource('payment_methods', PaymentMethodController::class)->except(['edit', 'update']);
});

Route::name('vendor.')->prefix('vendor')->group(function () {
    Route::post('purchase_orders/bulk', [PurchaseOrderController::class, 'bulk'])->name('purchase_orders.bulk');
    Route::put('profile/{vendor_contact}/edit', [VendorContactController::class, 'update'])->name('profile.update');
});
""".lstrip(),
                encoding="utf-8",
            )
            (views / "forms.blade.php").write_text(
                """
<form action="{{ route('client.payments.process') }}" method="post">
    <input name="amount">
</form>
<form action="{{ route('client.documents.index') }}" method="get">
    <input name="search">
</form>
<form action="{{ route('vendor.purchase_orders.bulk') }}" method="post">
    <input name="ids[]">
</form>
<form action="{{ route('client.payment_methods.destroy', [$paymentMethod]) }}" method="post">
    @method('DELETE')
    <input name="reason">
</form>
<form action="{{ route('vendor.profile.update', ['vendor_contact' => $contact]) }}" method="post">
    <input type="hidden" name="_method" value="PUT">
    <input name="name">
</form>
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            route_notes = {
                (route.method, route.path): route.evidence.note
                for route in facts.api_routes
                if route.framework == "laravel"
            }
            self.assertEqual("laravel-route-name:client.payments.process", route_notes[("POST", "/client/payments/process")])
            self.assertEqual("laravel-route-name:client.documents.index", route_notes[("GET", "/client/documents")])
            self.assertEqual("laravel-route-name:client.documents.show", route_notes[("GET", "/client/documents/{document}")])
            self.assertEqual("laravel-route-name:client.payment_methods.destroy", route_notes[("DELETE", "/client/payment_methods/{payment_method}")])
            self.assertEqual("laravel-route-name:vendor.purchase_orders.bulk", route_notes[("POST", "/vendor/purchase_orders/bulk")])
            self.assertEqual("laravel-route-name:vendor.profile.update", route_notes[("PUT", "/vendor/profile/{vendor_contact}/edit")])

            form_methods = {(form.action, form.method, form.evidence.note) for form in facts.forms}
            self.assertIn(("route:client.payment_methods.destroy", "POST", "form-method-override:DELETE"), form_methods)
            self.assertIn(("route:vendor.profile.update", "POST", "form-method-override:PUT"), form_methods)

            calls = {(call.method, call.endpoint, call.matched_route) for call in facts.api_calls}
            self.assertIn(("POST", "route:client.payments.process", "POST /client/payments/process"), calls)
            self.assertIn(("GET", "route:client.documents.index", "GET /client/documents"), calls)
            self.assertIn(("POST", "route:vendor.purchase_orders.bulk", "POST /vendor/purchase_orders/bulk"), calls)
            self.assertIn(("DELETE", "route:client.payment_methods.destroy", "DELETE /client/payment_methods/{payment_method}"), calls)
            self.assertIn(("PUT", "route:vendor.profile.update", "PUT /vendor/profile/{vendor_contact}/edit"), calls)


if __name__ == "__main__":
    unittest.main()
