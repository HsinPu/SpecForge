from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class PolyglotCalibrationTests(unittest.TestCase):

    def test_scan_project_detects_polyglot_frameworks_symbols_routes_and_data_layers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "go.mod").write_text(
                "module demo\n\ngo 1.23\n\nrequire github.com/gin-gonic/gin v1.10.0\n",
                encoding="utf-8",
            )
            go_dir = root / "cmd" / "server"
            go_dir.mkdir(parents=True)
            (go_dir / "main.go").write_text(
                """
package main

import "github.com/gin-gonic/gin"

func main() {
  router := gin.Default()
  api := router.Group("/api")
  api.GET("/users/:id", getUser)
}

func getUser(c *gin.Context) {}
type User struct {}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            (root / "Cargo.toml").write_text(
                """
[package]
name = "demo"
version = "0.1.0"

[dependencies]
clap = "4"
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "src").mkdir()
            (root / "src" / "main.rs").write_text(
                """
use clap::Parser;

pub struct Cli {}
pub fn run() {}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            (root / "composer.json").write_text(
                '{"require":{"laravel/framework":"^11.0"}}\n',
                encoding="utf-8",
            )
            routes_dir = root / "routes"
            routes_dir.mkdir()
            (routes_dir / "api.php").write_text(
                """
<?php
use Illuminate\\Support\\Facades\\Route;
Route::get('/accounts/{id}', 'AccountController@show');
""".strip()
                + "\n",
                encoding="utf-8",
            )
            php_migration = root / "database" / "migrations"
            php_migration.mkdir(parents=True)
            (php_migration / "2026_01_01_000000_create_accounts.php").write_text(
                """
<?php
Schema::create('accounts', function ($table) {
    $table->string('name');
});
""".strip()
                + "\n",
                encoding="utf-8",
            )

            (root / "Gemfile").write_text("gem 'rails'\n", encoding="utf-8")
            rails_config = root / "config"
            rails_config.mkdir()
            (rails_config / "routes.rb").write_text(
                """
Rails.application.routes.draw do
  get "/posts", to: "posts#index"
  resources :comments
end
""".strip()
                + "\n",
                encoding="utf-8",
            )
            rails_migration = root / "db" / "migrate"
            rails_migration.mkdir(parents=True)
            (rails_migration / "20260101000000_create_posts.rb").write_text(
                """
class CreatePosts < ActiveRecord::Migration[8.0]
  def change
    create_table :posts do |t|
      t.string :title
    end
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

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
  use Phoenix.Router
  get "/dashboard", PageController, :index
end
""".strip()
                + "\n",
                encoding="utf-8",
            )
            ecto_migration = root / "priv" / "repo" / "migrations"
            ecto_migration.mkdir(parents=True)
            (ecto_migration / "20260101000000_create_events.exs").write_text(
                """
defmodule Demo.Repo.Migrations.CreateEvents do
  use Ecto.Migration
  def change do
    create table(:events) do
      add :name, :string
    end
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            (root / "Demo.csproj").write_text(
                """
<Project Sdk="Microsoft.NET.Sdk.Web">
  <ItemGroup>
    <PackageReference Include="Microsoft.AspNetCore.Mvc" Version="2.3.0" />
  </ItemGroup>
</Project>
""".strip(),
                encoding="utf-8",
            )
            controllers_dir = root / "Controllers"
            controllers_dir.mkdir()
            (controllers_dir / "UsersController.cs").write_text(
                """
using Microsoft.AspNetCore.Mvc;

[Route("api/[controller]")]
public class UsersController : ControllerBase {
  [HttpGet("{id}")]
  public IActionResult Get(string id) { return Ok(); }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            migration_dir = root / "Migrations"
            migration_dir.mkdir()
            (migration_dir / "Init.cs").write_text(
                """
class Init {
  void Up(MigrationBuilder migrationBuilder) {
    migrationBuilder.CreateTable(name: "Customers", columns: table => new {});
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            (root / "pubspec.yaml").write_text(
                """
dependencies:
  flutter:
    sdk: flutter
  provider: ^6.0.0
""".strip()
                + "\n",
                encoding="utf-8",
            )
            lib_dir = root / "lib"
            lib_dir.mkdir(exist_ok=True)
            (lib_dir / "main.dart").write_text(
                """
import 'package:flutter/material.dart';

class MainApp extends StatelessWidget {
  Widget build(BuildContext context) => Container();
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            (root / "svelte.config.js").write_text("export default {};\n", encoding="utf-8")
            svelte_route = root / "src" / "routes" / "users"
            svelte_route.mkdir(parents=True, exist_ok=True)
            (svelte_route / "+page.svelte").write_text(
                """
<script>
  import { page } from '$app/stores';
  fetch('/api/users/123');
</script>
<h1>Users</h1>
""".strip()
                + "\n",
                encoding="utf-8",
            )

            kotlin_dir = root / "app" / "src" / "main" / "kotlin"
            kotlin_dir.mkdir(parents=True)
            (kotlin_dir / "MainActivity.kt").write_text(
                """
import androidx.activity.ComponentActivity

class MainActivity : ComponentActivity()
fun bootstrap() {}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            (root / "deps.edn").write_text(
                '{:deps {org.clojure/clojure {:mvn/version "1.12.0"}}}\n',
                encoding="utf-8",
            )
            clj_dir = root / "src" / "demo"
            clj_dir.mkdir(parents=True, exist_ok=True)
            (clj_dir / "core.clj").write_text(
                """
(ns demo.core
  (:require [clojure.string :as str]
            [next.jdbc :as jdbc]))

(defn run [] :ok)
""".strip()
                + "\n",
                encoding="utf-8",
            )

            generated_dir = root / "public" / "canvaskit"
            generated_dir.mkdir(parents=True)
            (generated_dir / "canvaskit.js").write_text(
                "export function GeneratedNoise() { return null; }\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            framework_names = {framework.name for framework in facts.frameworks}
            self.assertTrue(
                {"aspnetcore", "flutter", "gin", "laravel", "phoenix", "rails", "sveltekit"}
                <= framework_names
            )
            self.assertNotIn("next", framework_names)
            self.assertIn("github.com/gin-gonic/gin", {item.module for item in facts.imports})
            self.assertIn("clap::Parser", {item.module for item in facts.imports})
            self.assertIn("MainApp", {symbol.name for symbol in facts.symbols})
            self.assertIn("MainActivity", {symbol.name for symbol in facts.symbols})
            self.assertIn("run", {symbol.name for symbol in facts.symbols})
            self.assertIn("UsersPage", {component.name for component in facts.components})
            self.assertIn("/users", {route.route for route in facts.frontend_routes})
            self.assertIn("/api/users/123", {call.endpoint for call in facts.api_calls})
            self.assertIn("/api/users/:id", {route.path for route in facts.api_routes})
            self.assertIn("/api/accounts/{id}", {route.path for route in facts.api_routes})
            self.assertIn("/posts", {route.path for route in facts.api_routes})
            self.assertIn("/comments", {route.path for route in facts.api_routes})
            self.assertIn("/dashboard", {route.path for route in facts.api_routes})
            self.assertIn("/api/users/{id}", {route.path for route in facts.api_routes})
            self.assertTrue(
                {"efcore-data", "ecto-migration", "laravel-migration", "rails-migration"}
                <= {fact.kind for fact in facts.data_layers}
            )
            self.assertIn("public/canvaskit/canvaskit.js", {file.path for file in facts.files if file.role == "generated"})
            self.assertNotIn(
                "public/canvaskit/canvaskit.js",
                {symbol.path for symbol in facts.symbols},
            )


if __name__ == "__main__":
    unittest.main()
