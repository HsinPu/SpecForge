from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round52PhoenixLiveViewCalibrationTests(unittest.TestCase):
    def test_phoenix_live_routes_heex_forms_and_ecto_schema_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mix.exs").write_text(
                """
defmodule Demo.MixProject do
  use Mix.Project
  defp deps do
    [
      {:phoenix, "~> 1.7"},
      {:phoenix_live_view, "~> 0.20"},
      {:ecto_sql, "~> 3.10"}
    ]
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )
            web = root / "lib" / "demo_web"
            live = web / "live" / "profile_live"
            models = root / "lib" / "demo" / "media"
            migrations = root / "priv" / "repo" / "migrations"
            live.mkdir(parents=True)
            models.mkdir(parents=True)
            migrations.mkdir(parents=True)

            (web / "router.ex").write_text(
                """
defmodule DemoWeb.Router do
  use DemoWeb, :router

  scope "/app", DemoWeb do
    pipe_through :browser
    get "/oauth/:provider", OAuthController, :new

    live_session :authenticated do
      live "/:profile_username", ProfileLive, :show
      live "/:profile_username/songs/new", ProfileLive, :new
    end
  end

  scope "/dev" do
    pipe_through :browser
    live_dashboard "/dashboard", metrics: DemoWeb.Telemetry
    forward "/mailbox", Plug.Swoosh.MailboxPreview
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (models / "song.ex").write_text(
                """
defmodule Demo.Media.Song do
  use Ecto.Schema

  schema "songs" do
    field :title, :string
    field :status, Ecto.Enum, values: [draft: 0, published: 1], default: :draft
    belongs_to :user, Demo.Accounts.User
    embeds_one :transcript, Transcript do
      field :text, :string
    end
    timestamps()
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (migrations / "20260101000000_create_songs.exs").write_text(
                """
defmodule Demo.Repo.Migrations.CreateSongs do
  use Ecto.Migration

  def change do
    create table(:songs) do
      add :title, :string, null: false
      add :user_id, references(:users, on_delete: :nothing)
      timestamps()
    end

    create index(:songs, [:user_id])
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (live / "form_component.html.heex").write_text(
                """
<.form for={@form} action="/songs" method="post">
  <input name="title" />
</.form>
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("phoenix", "backend"), frameworks)
            self.assertIn(("phoenix-liveview", "frontend"), frameworks)

            api_routes = {(route.kind, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("phoenix-route", "GET", "/app/oauth/:provider", "OAuthController:new"), api_routes)
            self.assertIn(("phoenix-live-route", "GET", "/app/:profile_username", "ProfileLive:show"), api_routes)
            self.assertIn(("phoenix-live-route", "GET", "/app/:profile_username/songs/new", "ProfileLive:new"), api_routes)
            self.assertIn(("phoenix-live-dashboard-route", "GET", "/dev/dashboard", "Phoenix.LiveDashboard"), api_routes)
            self.assertIn(("phoenix-forward-route", "ANY", "/dev/mailbox", "Plug.Swoosh.MailboxPreview"), api_routes)

            oauth_route = next(route for route in facts.api_routes if route.path == "/app/oauth/:provider")
            self.assertIn(("path", "provider"), {(param.source, param.name) for param in oauth_route.parameters})

            live_route = next(route for route in facts.api_routes if route.path == "/app/:profile_username")
            self.assertEqual("LiveView", live_route.response_type)
            self.assertIn(("path", "profile_username"), {(param.source, param.name) for param in live_route.parameters})

            frontend_routes = {(route.framework, route.kind, route.route) for route in facts.frontend_routes}
            self.assertIn(("phoenix-liveview", "phoenix-live-route", "/app/:profile_username"), frontend_routes)
            self.assertIn(("phoenix-liveview", "phoenix-live-dashboard-route", "/dev/dashboard"), frontend_routes)

            forms = {(form.source, form.method, form.action, tuple(form.fields)) for form in facts.forms}
            self.assertIn(("lib/demo_web/live/profile_live/form_component.html.heex", "POST", "/songs", ("title",)), forms)

            models_by_name = {model.name: model for model in facts.data_models}
            self.assertEqual("ecto-schema", models_by_name["Song"].kind)
            self.assertIn("title:string", models_by_name["Song"].fields)
            self.assertIn("status:Ecto.Enum", models_by_name["Song"].fields)
            self.assertIn("table:songs", models_by_name["Song"].annotations)
            self.assertIn("enum:status", models_by_name["Song"].annotations)
            self.assertIn("relation:belongs_to:user:Demo.Accounts.User", models_by_name["Song"].annotations)
            self.assertIn("embed:embeds_one:transcript:Transcript", models_by_name["Song"].annotations)

            data_layers = {(layer.kind, layer.name, tuple(layer.details)) for layer in facts.data_layers}
            self.assertTrue(
                any(
                    kind == "ecto-migration"
                    and "reference:user_id:users" in details
                    and "index:songs:user_id" in details
                    for kind, _name, details in data_layers
                )
            )
            self.assertTrue(any(kind == "code-model:ecto-schema" and name == "Song" for kind, name, _details in data_layers))


if __name__ == "__main__":
    unittest.main()
