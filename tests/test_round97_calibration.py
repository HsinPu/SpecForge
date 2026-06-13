from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round97WordPressCalibrationTests(unittest.TestCase):
    def test_wordpress_rewrite_routes_cli_commands_and_php_template_forms_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "composer.json").write_text(
                """
{
  "name": "wp-api/oauth1",
  "type": "wordpress-plugin",
  "scripts": {
    "lint": "phpcs"
  },
  "require": {
    "php": "^8.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "oauth-server.php").write_text(
                """
<?php
/**
 * Plugin Name: Demo OAuth
 */

if ( defined( 'WP_CLI' ) && WP_CLI ) {
    WP_CLI::add_command( 'oauth1', 'WP_REST_OAuth1_CLI' );
}

function rest_oauth1_register_rewrites() {
    add_rewrite_rule( '^oauth1/authorize/?$', 'index.php?rest_oauth1=authorize', 'top' );
    add_rewrite_rule( '^oauth1/request/?$', 'index.php?rest_oauth1=request', 'top' );
    add_rewrite_rule( '^oauth1/access/?$', 'index.php?rest_oauth1=access', 'top' );
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            theme = root / "theme"
            theme.mkdir()
            (theme / "oauth1-authorize.php").write_text(
                """
<?php $url = site_url( 'wp-login.php?action=oauth1_authorize', 'login_post' ); ?>
<?php /** Mentions <form> in a docblock and should not create a form. */ ?>
<form name="oauth1_authorize_form" action="<?php echo esc_url( $url ); ?>" method="post">
  <input type="hidden" name="oauth_token" value="<?php echo esc_attr( $token_key ); ?>" />
  <input type="text" value="<?php echo esc_attr( $consumer_name ); ?>" name="consumer" id="consumer-id" />
  <button type="submit" name="wp-submit" value="authorize">Authorize</button>
</form>
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(item.framework, item.kind, item.method, item.path, item.handler) for item in facts.api_routes}
            self.assertIn(
                ("wordpress", "wordpress-rewrite-route", "ANY", "/oauth1/authorize", "rewrite:index.php?rest_oauth1=authorize"),
                routes,
            )
            self.assertIn(
                ("wordpress", "wordpress-rewrite-route", "ANY", "/oauth1/request", "rewrite:index.php?rest_oauth1=request"),
                routes,
            )
            self.assertIn(
                ("wordpress", "wordpress-rewrite-route", "ANY", "/oauth1/access", "rewrite:index.php?rest_oauth1=access"),
                routes,
            )

            commands = {(item.name, tuple(item.arguments), tuple(item.options)) for item in facts.commands}
            self.assertIn(("wp oauth1", ("oauth1",), ("handler:WP_REST_OAuth1_CLI",)), commands)

            forms = {(item.source, item.method, item.action, tuple(item.fields)) for item in facts.forms}
            self.assertIn(
                ("theme/oauth1-authorize.php", "POST", "php-dynamic:$url", ("oauth_token", "consumer")),
                forms,
            )


if __name__ == "__main__":
    unittest.main()
