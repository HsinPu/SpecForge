from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round157FormApiLinkCalibrationTests(unittest.TestCase):
    def test_blade_form_submission_links_to_named_laravel_route(self) -> None:
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
    Route::post('payments/process/response', [App\\Http\\Controllers\\ClientPortal\\PaymentController::class, 'response'])->name('client.payments.response');
});
""".strip()
                + "\n",
                encoding="utf-8",
            )

            views = root / "resources" / "views" / "portal"
            views.mkdir(parents=True)
            (views / "paypal.blade.php").write_text(
                """
<form method="POST" action="{{ route('client.payments.response') }}">
  <input type="hidden" name="payment_hash" value="{{ $hash }}">
  <button type="submit">Pay</button>
</form>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (views / "external.blade.php").write_text(
                """
<form method="POST" action="{{ $payment_endpoint_url }}">
  <input type="hidden" name="token" value="{{ $token }}">
</form>
<form action="#">
  <input name="local_search">
</form>
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            form = next(form for form in facts.forms if form.source == "resources/views/portal/paypal.blade.php")
            self.assertEqual("POST", form.method)
            self.assertEqual("route:client.payments.response", form.action)
            self.assertIn("payment_hash", form.fields)

            form_call = next(
                call
                for call in facts.api_calls
                if call.client == "form" and call.endpoint == "route:client.payments.response"
            )
            self.assertEqual("POST", form_call.method)
            self.assertEqual("form-submit", form_call.context)
            self.assertEqual("form-submit", form_call.trigger)
            self.assertEqual("POST /client/payments/process/response", form_call.matched_route)

            link = next(
                link
                for link in facts.api_links
                if link.source == "resources/views/portal/paypal.blade.php"
                and link.endpoint == "route:client.payments.response"
            )
            self.assertEqual("/client/payments/process/response", link.matched_route)
            self.assertEqual("POST", link.matched_method)
            self.assertEqual("named-route", link.match_type)
            self.assertEqual("high", link.confidence)

            frontend_map = next(item for item in facts.frontend_maps if item.page == "resources/views/portal/paypal.blade.php")
            self.assertIn("route:client.payments.response", frontend_map.api_calls)

            self.assertIn("dynamic:form-action", {call.endpoint for call in facts.api_calls})
            self.assertNotIn("{{ $payment_endpoint_url }}", {call.endpoint for call in facts.api_calls})
            self.assertFalse(any(call.client == "form" and call.endpoint == "#" for call in facts.api_calls))


if __name__ == "__main__":
    unittest.main()
