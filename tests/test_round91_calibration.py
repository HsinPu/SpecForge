from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round91PhoenixElixirCalibrationTests(unittest.TestCase):
    def test_phoenix_resources_mix_ecto_and_controller_tests_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mix.exs").write_text(
                """
defmodule Demo.MixProject do
  use Mix.Project

  def project do
    [
      app: :demo,
      version: "0.1.0",
      elixir: "~> 1.16",
      deps: deps()
    ]
  end

  defp deps do
    [
      {:phoenix, "~> 1.7.14"},
      {:phoenix_live_view, "~> 0.20.17"},
      {:ecto_sql, "~> 3.11"},
      {:postgrex, ">= 0.0.0"}
    ]
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            web = root / "lib" / "demo_web"
            web.mkdir(parents=True)
            (web / "router.ex").write_text(
                """
defmodule DemoWeb.Router do
  use DemoWeb, :router

  scope "/api", DemoWeb do
    pipe_through :api

    resources "/articles", ArticleController, except: [:new, :edit] do
      resources "/comments", CommentController, only: [:index, :create, :delete]
    end

    get "/profiles/:username", ProfileController, :show
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            schema_dir = root / "lib" / "demo" / "blog"
            schema_dir.mkdir(parents=True)
            (schema_dir / "article.ex").write_text(
                """
defmodule Demo.Blog.Article do
  use Ecto.Schema

  schema "articles" do
    field(:title, :string)
    field(:tag_list, {:array, :string}, default: [])
    belongs_to(:author, Demo.Accounts.User, foreign_key: :user_id)
    has_many(:comments, Demo.Blog.Comment)

    timestamps(inserted_at: :created_at)
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            migration_dir = root / "priv" / "repo" / "migrations"
            migration_dir.mkdir(parents=True)
            (migration_dir / "20260101000000_create_articles.exs").write_text(
                """
defmodule Demo.Repo.Migrations.CreateArticles do
  use Ecto.Migration

  def change do
    create table(:articles) do
      add(:title, :string)
      add(:slug, :string)
      add(:user_id, references(:users))

      timestamps()
    end

    create(unique_index(:articles, [:slug]))
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            test_dir = root / "test" / "demo_web" / "controllers"
            test_dir.mkdir(parents=True)
            (test_dir / "article_controller_test.exs").write_text(
                """
defmodule DemoWeb.ArticleControllerTest do
  use DemoWeb.ConnCase

  test "lists articles", %{conn: conn} do
    conn = get(conn, article_path(conn, :index))
    assert json_response(conn, 200)["articles"]
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (test_dir / "comment_controller_test.exs").write_text(
                """
defmodule DemoWeb.CommentControllerTest do
  use DemoWeb.ConnCase

  test "creates comments", %{conn: conn} do
    conn = post(conn, article_comment_path(conn, :create, "welcome"), comment: %{body: "ok"})
    assert json_response(conn, 201)["comment"]
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            dependencies = {(dependency.name, dependency.source) for dependency in facts.dependencies}
            self.assertIn(("phoenix", "mix.exs"), dependencies)
            self.assertIn(("ecto_sql", "mix.exs"), dependencies)

            commands = {command.name for command in facts.commands}
            self.assertIn("mix deps.get", commands)
            self.assertIn("mix test", commands)
            self.assertIn("mix phx.server", commands)
            self.assertIn("mix ecto.migrate", commands)

            entrypoints = {(entrypoint.kind, entrypoint.path, entrypoint.command) for entrypoint in facts.entrypoints}
            self.assertIn(("phoenix-app", "mix.exs", "mix phx.server"), entrypoints)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("phoenix", "backend"), frameworks)

            routes = {(route.method, route.path, route.handler): route for route in facts.api_routes}
            self.assertIn(("GET", "/api/articles", "ArticleController:index"), routes)
            self.assertIn(("POST", "/api/articles", "ArticleController:create"), routes)
            self.assertIn(("GET", "/api/articles/:id", "ArticleController:show"), routes)
            self.assertIn(("PATCH", "/api/articles/:id", "ArticleController:update"), routes)
            self.assertIn(("DELETE", "/api/articles/:id", "ArticleController:delete"), routes)
            self.assertIn(("GET", "/api/articles/:article_id/comments", "CommentController:index"), routes)
            self.assertIn(("POST", "/api/articles/:article_id/comments", "CommentController:create"), routes)
            self.assertIn(("DELETE", "/api/articles/:article_id/comments/:id", "CommentController:delete"), routes)
            self.assertIn(("GET", "/api/profiles/:username", "ProfileController:show"), routes)
            self.assertNotIn(("ANY", "/api/articles", "ArticleController:resource"), routes)

            create_route = routes[("POST", "/api/articles/:article_id/comments", "CommentController:create")]
            self.assertEqual("params", create_route.request_body)
            self.assertIn("article_id", [param.name for param in create_route.parameters])

            models = {(model.name, model.kind): model for model in facts.data_models}
            article = models[("Article", "ecto-schema")]
            self.assertIn("title:string", article.fields)
            self.assertIn("tag_list:array:string", article.fields)
            self.assertIn("author:Demo.Accounts.User", article.fields)
            self.assertIn("relation:belongs_to:author:Demo.Accounts.User", article.annotations)
            self.assertIn("timestamps:true", article.annotations)

            data_layers = {(layer.kind, layer.name): layer.details for layer in facts.data_layers}
            migration = data_layers[("ecto-migration", "20260101000000_create_articles")]
            self.assertIn("table:articles", migration)
            self.assertIn("column:title", migration)
            self.assertIn("reference:user_id:users", migration)
            self.assertIn("index:articles:slug", migration)

            test_maps = {test_map.test_path: test_map for test_map in facts.test_maps}
            article_test = test_maps["test/demo_web/controllers/article_controller_test.exs"]
            self.assertEqual("api-route", article_test.target_kind)
            self.assertEqual("GET /api/articles", article_test.target)
            self.assertEqual("high", article_test.confidence)

            comment_test = test_maps["test/demo_web/controllers/comment_controller_test.exs"]
            self.assertEqual("api-route", comment_test.target_kind)
            self.assertEqual("POST /api/articles/:article_id/comments", comment_test.target)
            self.assertEqual("high", comment_test.confidence)


if __name__ == "__main__":
    unittest.main()
