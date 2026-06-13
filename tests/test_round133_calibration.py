from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round133LaravelBladeApiCallCalibrationTests(unittest.TestCase):
    def test_blade_route_helpers_in_fetch_and_axios_are_named_calls_not_broken_urls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            views = root / "resources" / "views" / "portal"
            views.mkdir(parents=True)
            (root / "composer.json").write_text('{"require":{"laravel/framework":"^11.0"}}\n', encoding="utf-8")
            (views / "payment.blade.php").write_text(
                """
<button id="pay">Pay</button>
<script>
  fetch('{{ route('client.payments.response') }}', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  });
  axios.get("{{ route('client.payments.status') }}");
  fetch('/api/v1/invoices');
</script>
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            calls = {(call.client, call.method, call.endpoint) for call in facts.api_calls}
            self.assertIn(("fetch", "POST", "route:client.payments.response"), calls)
            self.assertIn(("axios", "GET", "route:client.payments.status"), calls)
            self.assertIn(("fetch", "GET", "/api/v1/invoices"), calls)
            self.assertNotIn("{{ route(", {call.endpoint for call in facts.api_calls})


if __name__ == "__main__":
    unittest.main()
