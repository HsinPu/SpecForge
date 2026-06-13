from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round117LaravelCalibrationTests(unittest.TestCase):

    def test_laravel_match_resource_options_params_and_body_hints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "composer.json").write_text('{"require":{"laravel/framework":"^11.0"}}\n', encoding="utf-8")
            routes = root / "routes"
            routes.mkdir()
            (routes / "api.php").write_text(
                """
<?php
use Illuminate\\Support\\Facades\\Route;

Route::group(['namespace' => 'Api'], function () {
    Route::match(['put', 'patch'], 'user', 'UserController@update');

    Route::resource('articles', 'ArticleController', [
        'except' => [
            'create', 'edit'
        ]
    ]);

    Route::resource('articles/{article}/comments', 'CommentController', [
        'only' => [
            'index', 'store', 'destroy'
        ]
    ]);
});
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes_seen = {(route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("PUT", "/api/user", "UserController@update"), routes_seen)
            self.assertIn(("PATCH", "/api/user", "UserController@update"), routes_seen)
            self.assertIn(("GET", "/api/articles", "ArticleController@index"), routes_seen)
            self.assertIn(("POST", "/api/articles", "ArticleController@store"), routes_seen)
            self.assertIn(("GET", "/api/articles/{article}", "ArticleController@show"), routes_seen)
            self.assertIn(("PUT", "/api/articles/{article}", "ArticleController@update"), routes_seen)
            self.assertIn(("PATCH", "/api/articles/{article}", "ArticleController@update"), routes_seen)
            self.assertIn(("DELETE", "/api/articles/{article}", "ArticleController@destroy"), routes_seen)
            self.assertIn(("GET", "/api/articles/{article}/comments", "CommentController@index"), routes_seen)
            self.assertIn(("POST", "/api/articles/{article}/comments", "CommentController@store"), routes_seen)
            self.assertIn(("DELETE", "/api/articles/{article}/comments/{comment}", "CommentController@destroy"), routes_seen)

            paths = {route.path for route in facts.api_routes}
            self.assertNotIn("/api/articles/create", paths)
            self.assertNotIn("/api/articles/{article}/edit", paths)
            self.assertNotIn("/api/articles/{article}/comments/{comment}", {route.path for route in facts.api_routes if route.method == "GET"})

            article_update = next(route for route in facts.api_routes if route.method == "PATCH" and route.path == "/api/articles/{article}")
            self.assertEqual(["article"], [param.name for param in article_update.parameters])
            self.assertEqual("request", article_update.request_body)
            comment_destroy = next(route for route in facts.api_routes if route.method == "DELETE" and route.path == "/api/articles/{article}/comments/{comment}")
            self.assertEqual(["article", "comment"], [param.name for param in comment_destroy.parameters])


if __name__ == "__main__":
    unittest.main()
