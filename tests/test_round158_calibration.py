from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round158PhoenixApiHelperCalibrationTests(unittest.TestCase):
    def test_phoenix_helpers_and_plausible_api_path_calls_link_to_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mix.exs").write_text(
                """
defmodule Demo.MixProject do
  use Mix.Project

  defp deps do
    [{:phoenix, "~> 1.8"}, {:phoenix_live_view, "~> 1.1"}]
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

  scope "/", DemoWeb do
    get "/login", AuthController, :login_form
    post "/login", AuthController, :login
    get "/settings/api-keys", SettingsController, :api_keys
    post "/settings/api-keys", SettingsController, :create_api_key
    post "/settings/preferences/name", SettingsController, :update_name
    post "/sites/:domain/memberships/invite", Site.MembershipController, :invite_member
    post "/api/stats/:domain/query", StatsController, :query
    get "/api/stats/:domain/conversions", StatsController, :conversions
    get "/api/stats/:domain/custom-prop-values/:prop", StatsController, :custom_prop_values
    get "/api/stats/:domain/suggestions/:filter_name", StatsController, :suggestions
    get "/api/stats/:domain/suggestions/custom-prop-values/:prop_key", StatsController, :custom_prop_values
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            templates = web / "templates" / "auth"
            templates.mkdir(parents=True)
            (templates / "login_form.html.heex").write_text(
                """
<.form action={Routes.auth_path(@conn, :login)}>
  <input name="email" />
</.form>
<.form action={Routes.settings_path(@conn, :update_name)}>
  <input name="name" />
</.form>
<.form action={Routes.settings_path(@conn, :api_keys)}>
  <input name="api_key_name" />
</.form>
<.form action={Routes.membership_path(@conn, :invite_member, @site.domain)}>
  <input name="email" />
</.form>
<form method="post" action={@form_submit_url}>
  <input name="runtime_only" />
</form>
""".strip()
                + "\n",
                encoding="utf-8",
            )

            dashboard = root / "assets" / "js" / "dashboard"
            dashboard.mkdir(parents=True)
            (dashboard / "stats.ts").write_text(
                """
import * as api from './api'
import * as url from './util/url'
import { apiPath } from './util/url'
import { fetchSuggestions } from './util/filters'
import { useQueryApi } from './hooks/use-query-api'

export function loadStats(site, dashboardState, queryKey, prop) {
  api.get(url.apiPath(site, '/conversions'), dashboardState)
  api.get(apiPath(site, `/custom-prop-values/${prop}`), dashboardState)
  useQueryApi(site, queryKey)
}

export function loadSuggestions(site, dashboardState, filterKey, propKey) {
  fetchSuggestions(apiPath(site, `/suggestions/${filterKey}`), dashboardState, 'P')
  fetchSuggestions(
    url.apiPath(site, `/suggestions/custom-prop-values/${encodeURIComponent(propKey)}`),
    dashboardState,
    'Q'
  )
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            calls = {(call.client, call.method, call.endpoint, call.context, call.matched_route) for call in facts.api_calls}
            self.assertIn(("api", "GET", "/api/stats/:domain/conversions", "apiPath-helper", "GET /api/stats/:domain/conversions"), calls)
            self.assertIn(("api", "GET", "/api/stats/:domain/custom-prop-values/:prop", "apiPath-helper", "GET /api/stats/:domain/custom-prop-values/:prop"), calls)
            self.assertIn(("useQueryApi", "POST", "/api/stats/:domain/query", "composable-api", "POST /api/stats/:domain/query"), calls)
            self.assertIn(("fetchSuggestions", "GET", "/api/stats/:domain/suggestions/:filterKey", "apiPath-wrapper", "GET /api/stats/:domain/suggestions/:filter_name"), calls)
            self.assertIn(("fetchSuggestions", "GET", "/api/stats/:domain/suggestions/custom-prop-values/:propKey", "apiPath-wrapper", "GET /api/stats/:domain/suggestions/custom-prop-values/:prop_key"), calls)
            self.assertFalse(any(call.endpoint in {"dynamic:url", "dynamic:apiPath", "dynamic:site"} for call in facts.api_calls))

            form_calls = {(call.method, call.endpoint, call.matched_route) for call in facts.api_calls if call.client == "form"}
            self.assertIn(("POST", "phoenix-helper:auth_path:login", "POST /login"), form_calls)
            self.assertIn(("POST", "phoenix-helper:settings_path:update_name", "POST /settings/preferences/name"), form_calls)
            self.assertIn(("POST", "phoenix-helper:settings_path:api_keys", "POST /settings/api-keys"), form_calls)
            self.assertIn(("POST", "phoenix-helper:membership_path:invite_member", "POST /sites/:domain/memberships/invite"), form_calls)
            self.assertIn(("POST", "dynamic:form-action", None), form_calls)
            self.assertNotIn(("@form_submit_url", None, None), form_calls)

            links = {(link.method, link.endpoint, link.matched_route, link.match_type, link.confidence) for link in facts.api_links}
            self.assertIn(("POST", "phoenix-helper:auth_path:login", "/login", "phoenix-helper", "high"), links)
            self.assertIn(("POST", "phoenix-helper:settings_path:update_name", "/settings/preferences/name", "phoenix-helper", "high"), links)
            self.assertIn(("POST", "phoenix-helper:settings_path:api_keys", "/settings/api-keys", "phoenix-helper", "high"), links)
            self.assertIn(("POST", "phoenix-helper:membership_path:invite_member", "/sites/:domain/memberships/invite", "phoenix-helper", "high"), links)


if __name__ == "__main__":
    unittest.main()
