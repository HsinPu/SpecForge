from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round24CalibrationTests(unittest.TestCase):

    def test_scan_project_links_metabase_defendpoint_routes_and_rtk_query_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                json.dumps({"dependencies": {"@reduxjs/toolkit": "^2.0.0", "react": "^19.0.0"}}),
                encoding="utf-8",
            )

            routes_dir = root / "src" / "metabase" / "api_routes"
            routes_dir.mkdir(parents=True)
            (routes_dir / "routes.clj").write_text(
                """
(ns metabase.api-routes.routes)

(def ^:private route-map
  {"/session" metabase.session.api/routes
   "/card"    (+auth metabase.queries-rest.api/card-routes)})
""".strip()
                + "\n",
                encoding="utf-8",
            )
            ee_routes_dir = root / "enterprise" / "backend" / "src" / "metabase_enterprise" / "api_routes"
            ee_routes_dir.mkdir(parents=True)
            (ee_routes_dir / "routes.clj").write_text(
                """
(ns metabase-enterprise.api-routes.routes)

(def ^:private ee-routes-map
  {"/action-v2"              metabase-enterprise.action-v2.api/routes
   "/advanced-permissions"   metabase-enterprise.advanced-permissions.api.routes/routes})
""".strip()
                + "\n",
                encoding="utf-8",
            )

            session_dir = root / "src" / "metabase" / "session"
            session_dir.mkdir(parents=True)
            (session_dir / "api.clj").write_text(
                """
(ns metabase.session.api
  "/api/session endpoints")

(api.macros/defendpoint :get "/properties"
  []
  {})
""".strip()
                + "\n",
                encoding="utf-8",
            )

            card_dir = root / "src" / "metabase" / "queries_rest" / "api"
            card_dir.mkdir(parents=True)
            (card_dir / "card.clj").write_text(
                """
(ns metabase.queries-rest.api.card
  "/api/card endpoints.")

(api.macros/defendpoint :post "/:card-id/query"
  [id]
  {})
""".strip()
                + "\n",
                encoding="utf-8",
            )
            channel_dir = root / "src" / "metabase" / "channel"
            channel_dir.mkdir(parents=True)
            (channel_dir / "api.clj").write_text(
                """
(ns metabase.channel.api)

(def channel-routes
  "/api/channel routes"
  (api.macros/ns-handler 'metabase.channel.api.channel))
""".strip()
                + "\n",
                encoding="utf-8",
            )
            channel_api_dir = channel_dir / "api"
            channel_api_dir.mkdir()
            (channel_api_dir / "channel.clj").write_text(
                """
(ns ^{:added "0.51.0"} metabase.channel.api.channel)

(api.macros/defendpoint :get "/"
  []
  {})

(api.macros/defendpoint :put "/:id"
  [id]
  {})
""".strip()
                + "\n",
                encoding="utf-8",
            )
            action_dir = root / "enterprise" / "backend" / "src" / "metabase_enterprise" / "action_v2"
            action_dir.mkdir(parents=True)
            (action_dir / "api.clj").write_text(
                """
(ns metabase-enterprise.action-v2.api)

(api.macros/defendpoint :post "/execute"
  []
  {})
""".strip()
                + "\n",
                encoding="utf-8",
            )
            advanced_dir = root / "enterprise" / "backend" / "src" / "metabase_enterprise" / "advanced_permissions" / "api"
            advanced_dir.mkdir(parents=True)
            (advanced_dir / "routes.clj").write_text(
                """
(ns metabase-enterprise.advanced-permissions.api.routes)

(def route-map
  {"/application" (api.macros/ns-handler 'metabase-enterprise.advanced-permissions.api.application)})
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (advanced_dir / "application.clj").write_text(
                """
(ns metabase-enterprise.advanced-permissions.api.application)

(api.macros/defendpoint :get "/graph"
  []
  {})
""".strip()
                + "\n",
                encoding="utf-8",
            )
            dev_dir = root / "dev" / "src" / "dev" / "api"
            dev_dir.mkdir(parents=True)
            (dev_dir / "preview.clj").write_text(
                """
(ns dev.api.preview
  "Dev-only endpoints. These were previously at `/api/pulse/preview_*`.")

(api.macros/defendpoint :get "/preview-card/:id"
  []
  {})
""".strip()
                + "\n",
                encoding="utf-8",
            )
            ignored_dir = root / ".clj-kondo" / "src" / "hooks"
            ignored_dir.mkdir(parents=True)
            (ignored_dir / "macros.clj").write_text(
                """
(ns hooks.macros)
(api.macros/defendpoint :get "/ignored" [] {})
""".strip()
                + "\n",
                encoding="utf-8",
            )

            api_dir = root / "frontend" / "src" / "metabase" / "api"
            api_dir.mkdir(parents=True)
            (api_dir / "session.ts").write_text(
                """
export const sessionApi = Api.injectEndpoints({
  endpoints: builder => ({
    getSessionProperties: builder.query({
      query: () => ({ method: "GET", url: "/api/session/properties" }),
    }),
    runCardQuery: builder.mutation({
      query: id => ({ method: "POST", url: `/api/card/${id}/query` }),
    }),
    executeAction: builder.mutation({
      query: () => ({ method: "POST", url: "/api/ee/action-v2/execute" }),
    }),
    listChannels: builder.query({
      query: () => ({ method: "GET", url: "/api/channel" }),
    }),
    updateChannel: builder.mutation({
      query: id => ({ method: "PUT", url: `/api/channel/${id}` }),
    }),
    getApplicationPermissions: builder.query({
      query: () => ({ method: "GET", url: "/api/ee/advanced-permissions/application/graph" }),
    }),
  }),
});
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.framework, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("clojure-ring", "GET", "/api/session/properties", "metabase.session.api"), routes)
            self.assertIn(("clojure-ring", "POST", "/api/card/:card-id/query", "metabase.queries-rest.api.card"), routes)
            self.assertIn(("clojure-ring", "GET", "/api/channel", "metabase.channel.api.channel"), routes)
            self.assertIn(("clojure-ring", "PUT", "/api/channel/:id", "metabase.channel.api.channel"), routes)
            self.assertIn(("clojure-ring", "POST", "/api/ee/action-v2/execute", "metabase-enterprise.action-v2.api"), routes)
            self.assertIn(
                (
                    "clojure-ring",
                    "GET",
                    "/api/ee/advanced-permissions/application/graph",
                    "metabase-enterprise.advanced-permissions.api.application",
                ),
                routes,
            )
            self.assertNotIn(("clojure-ring", "GET", "/api/pulse/preview_*/preview-card/:id", "dev.api.preview"), routes)
            self.assertFalse(any(route.path == "/ignored" for route in facts.api_routes))

            calls = {(call.client, call.method, call.endpoint) for call in facts.api_calls}
            self.assertIn(("rtk-query", "GET", "/api/session/properties"), calls)
            self.assertIn(("rtk-query", "POST", "/api/card/:id/query"), calls)
            self.assertIn(("rtk-query", "POST", "/api/ee/action-v2/execute"), calls)
            self.assertIn(("rtk-query", "GET", "/api/channel"), calls)
            self.assertIn(("rtk-query", "PUT", "/api/channel/:id"), calls)
            self.assertIn(("rtk-query", "GET", "/api/ee/advanced-permissions/application/graph"), calls)

            links = {
                (link.method, link.endpoint): link.matched_route
                for link in facts.api_links
                if link.matched_route
            }
            self.assertEqual("/api/session/properties", links[("GET", "/api/session/properties")])
            self.assertEqual("/api/card/:card-id/query", links[("POST", "/api/card/:id/query")])
            self.assertEqual("/api/ee/action-v2/execute", links[("POST", "/api/ee/action-v2/execute")])
            self.assertEqual("/api/channel", links[("GET", "/api/channel")])
            self.assertEqual("/api/channel/:id", links[("PUT", "/api/channel/:id")])
            self.assertEqual(
                "/api/ee/advanced-permissions/application/graph",
                links[("GET", "/api/ee/advanced-permissions/application/graph")],
            )


if __name__ == "__main__":
    unittest.main()
