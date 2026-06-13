from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round142PhoenixPlausibleRouterCalibrationTests(unittest.TestCase):
    def test_phoenix_router_keeps_named_and_multiline_scope_prefixes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mix.exs").write_text(
                """
defmodule Demo.MixProject do
  use Mix.Project

  defp deps do
    [{:phoenix, "~> 1.7"}, {:phoenix_live_view, "~> 0.20"}]
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

  scope path: "/api/plugins", as: :plugins_api do
    scope "/spec" do
      get("/openapi", OpenApiSpex.Plug.RenderSpec, [])
    end

    scope "/v1/capabilities", DemoWeb.Plugin.Controllers,
      assigns: %{plugins_api: true} do
      get("/", Capabilities, :index)
    end

    scope "/v1", DemoWeb.Plugin.Controllers, assigns: %{plugins_api: true} do
      get("/shared_links", SharedLinks, :index)
    end
  end

  scope "/api", DemoWeb do
    post "/event", Api.ExternalController, :event

    scope "/stats", DemoWeb.Api do
      post "/:domain/exploration/next-with-funnel",
           StatsController,
           :exploration_next_with_funnel
    end
  end

  scope "/", DemoWeb do
    scope alias: Live, assigns: %{connect_live_socket: true} do
      live "/:domain/verification",
           on_ee(do: Verification, else: AwaitingPageviews),
           :verification,
           as: :site
    end
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)
            routes = {(route.method, route.path, route.handler, route.kind): route for route in facts.api_routes}

            self.assertIn(("GET", "/api/plugins/spec/openapi", "OpenApiSpex.Plug.RenderSpec", "phoenix-route"), routes)
            self.assertIn(("GET", "/api/plugins/v1/capabilities", "Capabilities:index", "phoenix-route"), routes)
            self.assertIn(("GET", "/api/plugins/v1/shared_links", "SharedLinks:index", "phoenix-route"), routes)
            self.assertIn(("POST", "/api/event", "Api.ExternalController:event", "phoenix-route"), routes)
            self.assertIn(
                (
                    "POST",
                    "/api/stats/:domain/exploration/next-with-funnel",
                    "StatsController:exploration_next_with_funnel",
                    "phoenix-route",
                ),
                routes,
            )
            self.assertIn(
                (
                    "GET",
                    "/:domain/verification",
                    "on_ee(do: Verification, else: AwaitingPageviews):verification",
                    "phoenix-live-route",
                ),
                routes,
            )

            plugin_route = routes[("GET", "/api/plugins/spec/openapi", "OpenApiSpex.Plug.RenderSpec", "phoenix-route")]
            self.assertEqual("lib/demo_web/router.ex", plugin_route.evidence.file)
            stats_route = routes[
                (
                    "POST",
                    "/api/stats/:domain/exploration/next-with-funnel",
                    "StatsController:exploration_next_with_funnel",
                    "phoenix-route",
                )
            ]
            self.assertEqual("params", stats_route.request_body)
            self.assertIn("domain", [param.name for param in stats_route.parameters])


if __name__ == "__main__":
    unittest.main()
