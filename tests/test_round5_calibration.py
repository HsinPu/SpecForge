from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round5CalibrationTests(unittest.TestCase):

    def test_scan_project_detects_round5_framework_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            (root / "mix.exs").write_text(
                """
defmodule Demo.MixProject do
  defp deps do
    [{:phoenix, "~> 1.7"}]
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )
            phoenix_router = root / "lib" / "demo_web"
            phoenix_router.mkdir(parents=True)
            (phoenix_router / "router.ex").write_text(
                """
defmodule DemoWeb.Router do
  use DemoWeb, :router

  scope "/", DemoWeb do
    get("/articles/feed", ArticleController, :feed)
    resources "/articles", ArticleController, except: [:new, :edit] do
      resources("/comments", CommentController, except: [:new, :edit])
    end
    post("/users/login", SessionController, :create)
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            api = root / "api"
            api.mkdir()
            (api / "package.json").write_text(
                '{"dependencies":{"express":"^5.0.0","express-graphql":"^0.9.0","graphql":"^16.0.0"}}\n',
                encoding="utf-8",
            )
            api_src = api / "src"
            api_src.mkdir()
            (api_src / "graphql.js").write_text(
                """
import graphqlHTTP from 'express-graphql';

export default function setupGraphQL(server) {
  server.use('/graphql', graphqlHTTP({}));
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            (root / "pubspec.yaml").write_text(
                """
name: demo
dependencies:
  flutter:
    sdk: flutter
  go_router: ^14.0.0
""".strip()
                + "\n",
                encoding="utf-8",
            )
            flutter_lib = root / "lib"
            flutter_lib.mkdir(exist_ok=True)
            (flutter_lib / "app.dart").write_text(
                """
import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

class App extends StatelessWidget {
  const App({super.key});
}

final router = GoRouter(routes: [
  GoRoute(path: '/home'),
  GoRoute(path: '/users/:id'),
]);
""".strip()
                + "\n",
                encoding="utf-8",
            )

            android_file = root / "app" / "src" / "main" / "java" / "demo"
            android_file.mkdir(parents=True)
            version_catalog = root / "gradle"
            version_catalog.mkdir()
            (version_catalog / "libs.versions.toml").write_text(
                """
[libraries]
androidx-compose-runtime = { group = "androidx.compose.runtime", name = "runtime" }
androidx-room-runtime = { group = "androidx.room", name = "room-runtime" }

[plugins]
android-application = { id = "com.android.application" }
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (android_file / "HomeScreen.kt").write_text(
                """
package demo

import androidx.compose.runtime.Composable

@Composable
fun HomeScreen(title: String) {
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (android_file / "LocalTask.kt").write_text(
                """
package demo

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "task")
data class LocalTask(@PrimaryKey val id: String)
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (android_file / "TaskDao.kt").write_text(
                """
package demo

import androidx.room.Dao
import androidx.room.Query

@Dao
interface TaskDao {
  @Query("SELECT * FROM task")
  fun observeAll(): List<LocalTask>
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            framework_names = {framework.name for framework in facts.frameworks}
            self.assertTrue({"phoenix", "express", "graphql", "flutter", "android", "jetpack-compose"} <= framework_names)
            self.assertNotIn("spring", framework_names)
            self.assertIn(("phoenix", "GET", "/articles/feed"), _api_routes(facts))
            self.assertIn(("phoenix", "GET", "/articles"), _api_routes(facts))
            self.assertIn(("phoenix", "POST", "/articles"), _api_routes(facts))
            self.assertIn(("phoenix", "GET", "/articles/:article_id/comments"), _api_routes(facts))
            self.assertIn(("phoenix", "POST", "/users/login"), _api_routes(facts))
            self.assertIn(("graphql", "ANY", "/graphql"), _api_routes(facts))
            self.assertIn("App", {component.name for component in facts.components})
            self.assertIn("HomeScreen", {component.name for component in facts.components})
            self.assertIn("/home", {route.route for route in facts.frontend_routes})
            self.assertIn("/users/:id", {route.route for route in facts.frontend_routes})
            self.assertIn("graphql", {dependency.name for dependency in facts.dependencies})
            self.assertIn("androidx.room:room-runtime", {dependency.name for dependency in facts.dependencies})
            self.assertIn("room-entity", {item.kind for item in facts.data_layers})
            self.assertIn("room-dao", {item.kind for item in facts.data_layers})

    def test_framework_false_positives_are_conservative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            rails_js = root / "app" / "assets" / "javascripts"
            rails_js.mkdir(parents=True)
            (rails_js / "application.js").write_text("// Rails asset pipeline\n", encoding="utf-8")
            (root / "Gemfile").write_text("gem 'rails'\n", encoding="utf-8")

            laravel = root / "laravel"
            laravel.mkdir()
            (laravel / "composer.json").write_text(
                '{"require":{"laravel/framework":"^11.0","symfony/console":"^7.0"}}\n',
                encoding="utf-8",
            )
            handler = laravel / "app" / "Exceptions"
            handler.mkdir(parents=True)
            (handler / "Handler.php").write_text(
                "<?php\nuse Symfony\\Component\\HttpKernel\\Exception\\HttpException;\n",
                encoding="utf-8",
            )

            android = root / "android"
            android_src = android / "app" / "src" / "main" / "java" / "demo"
            android_src.mkdir(parents=True)
            (android / "build.gradle.kts").write_text("plugins { id(\"com.android.application\") }\n", encoding="utf-8")
            (android_src / "MainActivity.kt").write_text("package demo\nclass MainActivity\n", encoding="utf-8")

            facts = scan_project(root)

            framework_names = {framework.name for framework in facts.frameworks}
            self.assertIn("rails", framework_names)
            self.assertIn("laravel", framework_names)
            self.assertIn("android", framework_names)
            self.assertNotIn("ember", framework_names)
            self.assertNotIn("symfony", framework_names)
            self.assertNotIn("spring", framework_names)


def _api_routes(facts: object) -> set[tuple[str, str, str]]:
    return {(route.framework, route.method, route.path) for route in facts.api_routes}


if __name__ == "__main__":
    unittest.main()
