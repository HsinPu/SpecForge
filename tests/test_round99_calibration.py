from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round99SlimCalibrationTests(unittest.TestCase):
    def test_slim_routes_entrypoint_and_illuminate_without_laravel_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "composer.json").write_text(
                """
{
  "require": {
    "slim/slim": "^3.12",
    "illuminate/database": "^5.5"
  },
  "require-dev": {
    "phpunit/phpunit": "^9.0"
  },
  "scripts": {
    "start": "php -S localhost:8080 -t public public/index.php",
    "test": "vendor/bin/phpunit"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "phinx.php").write_text("<?php\nreturn [];\n", encoding="utf-8")
            (root / "phpunit.xml").write_text("<phpunit />\n", encoding="utf-8")
            public = root / "public"
            public.mkdir()
            (public / "index.php").write_text(
                """
<?php
require __DIR__ . '/../vendor/autoload.php';
$app = new \\Slim\\App([]);
require __DIR__ . '/../src/routes.php';
$app->run();
""".strip()
                + "\n",
                encoding="utf-8",
            )
            src = root / "src"
            src.mkdir()
            (src / "routes.php").write_text(
                """
<?php
use App\\Controller\\ArticleController;
use App\\Controller\\LoginController;
use Slim\\Http\\Request;
use Slim\\Http\\Response;

$app->group('/api', function () {
    $this->post('/users/login', LoginController::class . ':login')->setName('auth.login');
    $this->get('/articles/{slug}', ArticleController::class . ':show');
    $this->map(['PUT', 'PATCH'], '/articles/{slug}', ArticleController::class . ':update');
    $this->get('/tags', function (Request $request, Response $response) {
        return $response;
    });
});

$app->get('/[{name}]', function (Request $request, Response $response, array $args) {
    return $response;
});
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {item.name for item in facts.frameworks}
            self.assertIn("slim", frameworks)
            self.assertIn("illuminate", frameworks)
            self.assertNotIn("laravel", frameworks)

            entrypoints = {(item.kind, item.path, item.command) for item in facts.entrypoints}
            self.assertIn(("slim-front-controller", "public/index.php", "composer run start"), entrypoints)

            commands = {item.name for item in facts.commands}
            self.assertIn("composer run start", commands)
            self.assertIn("vendor/bin/phpunit", commands)
            self.assertIn("vendor/bin/phinx migrate", commands)

            routes = {(item.method, item.path, item.handler) for item in facts.api_routes}
            self.assertIn(("POST", "/api/users/login", "App\\Controller\\LoginController:login"), routes)
            self.assertIn(("GET", "/api/articles/{slug}", "App\\Controller\\ArticleController:show"), routes)
            self.assertIn(("PUT", "/api/articles/{slug}", "App\\Controller\\ArticleController:update"), routes)
            self.assertIn(("PATCH", "/api/articles/{slug}", "App\\Controller\\ArticleController:update"), routes)
            self.assertIn(("GET", "/api/tags", "closure"), routes)
            self.assertIn(("GET", "/{name}", "closure"), routes)

            article_route = next(item for item in facts.api_routes if item.path == "/api/articles/{slug}" and item.method == "GET")
            self.assertEqual([param.name for param in article_route.parameters], ["slug"])


if __name__ == "__main__":
    unittest.main()
