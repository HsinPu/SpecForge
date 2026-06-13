from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round67WooCommerceCalibrationTests(unittest.TestCase):
    def test_woocommerce_wordpress_routes_api_fetch_and_scaffold_template_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            controller = root / "plugins" / "woocommerce" / "includes" / "rest-api" / "Controllers" / "Version3"
            frontend = root / "plugins" / "woocommerce" / "client" / "admin" / "client"
            scaffold = root / "packages" / "js" / "create-woo-extension" / "variants" / "default"
            controller.mkdir(parents=True)
            frontend.mkdir(parents=True)
            scaffold.mkdir(parents=True)
            (root / "composer.json").write_text('{"require":{"johnpbloch/wordpress":"^6.0"}}\n', encoding="utf-8")
            (root / "package.json").write_text(
                '{"dependencies":{"@wordpress/api-fetch":"^7.0.0","react":"^18.0.0"}}\n',
                encoding="utf-8",
            )

            (controller / "class-wc-rest-data-currencies-controller.php").write_text(
                r"""
<?php
class WC_REST_Data_Currencies_Controller {
	protected $namespace = 'wc/v3';
	protected $rest_base = 'data/currencies';

	public function register_routes() {
		register_rest_route(
			$this->namespace,
			'/' . $this->rest_base . '/(?P<currency>[\w-]{3})',
			array(
				array(
					'methods'  => WP_REST_Server::READABLE,
					'callback' => array( $this, 'get_item' ),
				),
				array(
					'methods'  => WP_REST_Server::EDITABLE,
					'callback' => array( $this, 'update_item' ),
				),
			)
		);
	}
}
""".lstrip(),
                encoding="utf-8",
            )
            (frontend / "currency.ts").write_text(
                """
import apiFetch from '@wordpress/api-fetch';

export function loadCurrency() {
  return apiFetch( { path: '/wc/v3/data/currencies/USD' } );
}

export function updateCurrency() {
  return window.wp.apiFetch( { path: '/wc/v3/data/currencies/USD', method: 'PUT' } );
}
""".lstrip(),
                encoding="utf-8",
            )
            (scaffold / "composer.json.mustache").write_text(
                '{"name":"{{slug}}/{{slug}}","autoload":{"psr-4":{"{{namespace}}\\\\":"src/"}}}\n',
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.method, route.path, route.handler, route.framework) for route in facts.api_routes}
            self.assertIn(("GET", "/wp-json/wc/v3/data/currencies/{currency}", "get_item", "wordpress"), routes)
            self.assertIn(("PUT", "/wp-json/wc/v3/data/currencies/{currency}", "update_item", "wordpress"), routes)

            calls = {(call.method, call.endpoint, call.client) for call in facts.api_calls}
            self.assertIn(("GET", "/wp-json/wc/v3/data/currencies/USD", "apiFetch"), calls)
            self.assertIn(("PUT", "/wp-json/wc/v3/data/currencies/USD", "window.wp.apiFetch"), calls)
            self.assertTrue(
                any(
                    link.endpoint == "/wp-json/wc/v3/data/currencies/USD"
                    and link.matched_route == "/wp-json/wc/v3/data/currencies/{currency}"
                    and link.matched_framework == "wordpress"
                    for link in facts.api_links
                )
            )
            self.assertFalse(any(route.path.endswith("composer.json.mustache") for route in facts.frontend_routes))
            scaffold_file = next(file for file in facts.files if file.path.endswith("composer.json.mustache"))
            self.assertEqual("sample", scaffold_file.role)


if __name__ == "__main__":
    unittest.main()
