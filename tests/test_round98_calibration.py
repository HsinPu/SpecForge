from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round98Yii2CalibrationTests(unittest.TestCase):
    def test_yii2_framework_entrypoints_commands_and_rest_url_rules_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "composer.json").write_text(
                """
{
  "require": {
    "yiisoft/yii2": "~2.0.14",
    "yiisoft/yii2-bootstrap": "~2.0.0"
  },
  "require-dev": {
    "codeception/codeception": "^4.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "yii").write_text("#!/usr/bin/env php\n<?php\n", encoding="utf-8")
            web = root / "web"
            web.mkdir()
            (web / "index.php").write_text(
                """
<?php
require __DIR__ . '/../vendor/autoload.php';
require __DIR__ . '/../vendor/yiisoft/yii2/Yii.php';
(new yii\\web\\Application([]))->run();
""".strip()
                + "\n",
                encoding="utf-8",
            )
            commands = root / "commands"
            commands.mkdir()
            (commands / "HelloController.php").write_text(
                """
<?php
namespace app\\commands;
class HelloController extends \\yii\\console\\Controller {
    public function actionIndex() {}
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            api = root / "modules" / "api"
            controllers = api / "controllers"
            controllers.mkdir(parents=True)
            (api / "Module.php").write_text(
                """
<?php
namespace app\\modules\\api;
use yii\\rest\\UrlRule;
class Module extends \\yii\\base\\Module {
    private function registerUrlRules($app) {
        $app->getUrlManager()->addRules([
            [
                'class' => UrlRule::class,
                'prefix' => $this->id,
                'controller' => ['users' => $this->id . '/auth'],
                'extraPatterns' => [
                    'POST login' => 'login',
                    'OPTIONS login' => 'options',
                ],
            ],
            [
                'class' => UrlRule::class,
                'prefix' => $this->id,
                'controller' => ['user' => $this->id . '/auth'],
                'only' => ['index', 'update', 'options'],
                'extraPatterns' => [
                    'PUT,PATCH' => 'update',
                ],
            ],
            [
                'class' => UrlRule::class,
                'prefix' => $this->id,
                'controller' => ['articles' => $this->id . '/article'],
                'except' => ['feed'],
                'extraPatterns' => [
                    'POST {id}/favorite' => 'favorite',
                    'DELETE {id}/favorite' => 'unfavorite',
                ],
                'tokens' => [
                    '{id}' => '<id>',
                ],
            ],
            [
                'class' => UrlRule::class,
                'prefix' => $this->id,
                'controller' => ['profiles' => $this->id . '/profile'],
                'only' => ['view', 'follow', 'unfollow', 'options'],
                'extraPatterns' => [
                    'GET,HEAD {username}' => 'view',
                    'POST {username}/follow' => 'follow',
                    'DELETE {username}/follow' => 'unfollow',
                ],
            ],
        ]);
    }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (controllers / "AuthController.php").write_text(
                """
<?php
namespace app\\modules\\api\\controllers;
class AuthController extends Controller {
    public function actionCreate() {}
    public function actionLogin() {}
    public function actionIndex() {}
    public function actionUpdate() {}
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (controllers / "ArticleController.php").write_text(
                """
<?php
namespace app\\modules\\api\\controllers;
class ArticleController extends ActiveController {
    public function actions() {
        return [
            'view' => [],
            'delete' => [],
        ];
    }
    public function actionCreate() {}
    public function actionUpdate($id) {}
    public function actionFavorite($id) {}
    public function actionUnfavorite($id) {}
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (controllers / "ProfileController.php").write_text(
                """
<?php
namespace app\\modules\\api\\controllers;
class ProfileController extends Controller {
    public function actionView($username) {}
    public function actionFollow($username) {}
    public function actionUnfollow($username) {}
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(item.name, item.category) for item in facts.frameworks}
            self.assertIn(("yii2", "backend"), frameworks)

            entrypoints = {(item.kind, item.path, item.command) for item in facts.entrypoints}
            self.assertIn(("yii-web-front-controller", "web/index.php", "php -S localhost:8000 -t web"), entrypoints)
            self.assertIn(("yii-console", "yii", "php yii"), entrypoints)

            commands_seen = {item.name for item in facts.commands}
            self.assertIn("php yii", commands_seen)
            self.assertIn("php yii migrate", commands_seen)
            self.assertIn("php yii hello", commands_seen)

            routes = {(item.method, item.path, item.handler) for item in facts.api_routes}
            self.assertIn(("POST", "/api/users/login", "api/auth#login"), routes)
            self.assertIn(("POST", "/api/users", "api/auth#create"), routes)
            self.assertIn(("PUT", "/api/user", "api/auth#update"), routes)
            self.assertIn(("POST", "/api/articles/{id}/favorite", "api/article#favorite"), routes)
            self.assertIn(("GET", "/api/profiles/{username}", "api/profile#view"), routes)
            self.assertNotIn(("PUT", "/api/users/{id}", "api/auth#update"), routes)
            self.assertNotIn(("GET", "/api/profiles/{id}", "api/profile#view"), routes)


if __name__ == "__main__":
    unittest.main()
