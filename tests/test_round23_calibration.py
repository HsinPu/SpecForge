from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round23CalibrationTests(unittest.TestCase):

    def test_scan_project_links_api_client_template_urls_to_openapi_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            (root / "package.json").write_text(
                json.dumps({"dependencies": {"vue": "^3.0.0"}}),
                encoding="utf-8",
            )
            api_dir = root / "app" / "javascript" / "dashboard" / "api"
            api_dir.mkdir(parents=True)
            (api_dir / "ApiClient.js").write_text(
                """
/* global axios */

class ApiClient {
  show(id) {
    return axios.get(`${this.url}/${id}`);
  }
}

export default ApiClient;
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (api_dir / "agents.js").write_text(
                """
/* global axios */
import ApiClient from './ApiClient';

class Agents extends ApiClient {
  constructor() {
    super('agents', { accountScoped: true });
  }

  list() {
    return axios.get(this.url);
  }

  bulkInvite() {
    return axios.post(`${this.url}/bulk_create`);
  }

  search() {
    return axios.get(`${this.url}/search`);
  }

  archive() {
    return axios.post(`${this.url}/archive`);
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (api_dir / "agentBots.js").write_text(
                """
/* global axios */
import ApiClient from './ApiClient';

class AgentBots extends ApiClient {
  constructor() {
    super('agent_bots', { accountScoped: true });
  }

  deleteAvatar(botId) {
    return axios.delete(`${this.url}/${botId}/avatar`);
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            channel_dir = api_dir / "channel"
            channel_dir.mkdir()
            (channel_dir / "fbChannel.js").write_text(
                """
/* global axios */
import ApiClient from '../ApiClient';

class FacebookChannel extends ApiClient {
  constructor() {
    super('facebook_indicators', { accountScoped: true });
  }

  registerPage() {
    return axios.post(`${this.url.replace(this.resource, '')}callbacks/register_facebook_page`);
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            help_center = api_dir / "helpCenter"
            help_center.mkdir()
            (help_center / "portals.js").write_text(
                """
/* global axios */
import ApiClient from '../ApiClient';

class PortalsAPI extends ApiClient {
  constructor() {
    super('portals', { accountScoped: true });
  }
}

export default PortalsAPI;
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (help_center / "articles.js").write_text(
                """
/* global axios */
import PortalsAPI from './portals';

class ArticlesAPI extends PortalsAPI {
  constructor() {
    super('articles', { accountScoped: true });
  }

  getArticle({ portalSlug, id }) {
    return axios.get(`${this.url}/${portalSlug}/articles/${id}`);
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (api_dir / "reports.js").write_text(
                """
/* global axios */
import ApiClient from './ApiClient';

class Reports extends ApiClient {
  constructor() {
    super('reports', { accountScoped: true, apiVersion: 'v2' });
  }

  summary() {
    return axios.get(`${this.url}/summary`);
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            enterprise = api_dir / "enterprise"
            enterprise.mkdir()
            (enterprise / "account.js").write_text(
                """
/* global axios */
import ApiClient from '../ApiClient';

class EnterpriseAccountAPI extends ApiClient {
  constructor() {
    super('', { accountScoped: true, enterprise: true });
  }

  checkout() {
    return axios.post(`${this.url}checkout`);
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (api_dir / "mfa.js").write_text(
                """
/* global axios */
import ApiClient from './ApiClient';

class MfaAPI extends ApiClient {
  constructor() {
    super('profile/mfa', { accountScoped: false });
  }

  backupCodes() {
    return axios.post(`${this.url}/backup_codes`);
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            helpers = root / "app" / "javascript" / "dashboard" / "helper"
            helpers.mkdir(parents=True)
            (helpers / "uploadHelper.js").write_text(
                """
const API_VERSION = 'v1';

export function uploadAvatar(accountId) {
  return fetch(`/api/${API_VERSION}/accounts/${accountId}/upload`, { method: 'POST' });
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            auth = root / "app" / "javascript" / "dashboard" / "store"
            auth.mkdir(parents=True)
            (auth / "auth.js").write_text(
                """
export function signIn(credentials) {
  return fetch('/auth/sign_in', { method: 'POST', body: JSON.stringify(credentials) });
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            config = root / "config"
            config.mkdir()
            (config / "routes.rb").write_text(
                """
Rails.application.routes.draw do
  mount_devise_token_auth_for 'User', at: 'auth'
end
""".strip()
                + "\n",
                encoding="utf-8",
            )
            views = root / "app" / "views" / "layouts"
            views.mkdir(parents=True)
            (views / "vueapp.html.erb").write_text(
                """
<script>
  window.chatwootConfig = {
    hostURL: '<%= ENV.fetch('FRONTEND_URL', '') %>',
  }
</script>
""".strip()
                + "\n",
                encoding="utf-8",
            )

            (root / "swagger.json").write_text(
                json.dumps(
                    {
                        "openapi": "3.0.0",
                        "paths": {
                            "/api/v1/accounts/{account_id}/agents": {"get": {}},
                            "/api/v1/accounts/{account_id}/agents/{id}": {"get": {}, "patch": {}},
                            "/api/v1/accounts/{account_id}/agents/bulk_create": {"post": {}},
                            "/api/v1/accounts/{account_id}/agent_bots/{id}/avatar": {"delete": {}},
                            "/api/v1/accounts/{account_id}/callbacks/register_facebook_page": {"post": {}},
                            "/api/v1/accounts/{account_id}/portals/{portal_slug}/articles/{id}": {"get": {}},
                            "/api/v2/accounts/{account_id}/reports/summary": {"get": {}},
                            "/enterprise/api/v1/accounts/{account_id}/checkout": {"post": {}},
                            "/api/v1/profile/mfa/backup_codes": {"post": {}},
                            "/api/v1/accounts/{account_id}/upload": {"post": {}},
                        },
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            facts = scan_project(root)

            calls = {(call.method, call.endpoint) for call in facts.api_calls}
            self.assertIn(("GET", "/api/v1/accounts/:account_id/agents"), calls)
            self.assertIn(("POST", "/api/v1/accounts/:account_id/agents/bulk_create"), calls)
            self.assertIn(("GET", "/api/v1/accounts/:account_id/agents/search"), calls)
            self.assertIn(("POST", "/api/v1/accounts/:account_id/agents/archive"), calls)
            self.assertIn(("DELETE", "/api/v1/accounts/:account_id/agent_bots/:botId/avatar"), calls)
            self.assertIn(("POST", "/api/v1/accounts/:account_id/callbacks/register_facebook_page"), calls)
            self.assertIn(("GET", "/api/v1/accounts/:account_id/portals/:portalSlug/articles/:id"), calls)
            self.assertIn(("GET", "/api/v2/accounts/:account_id/reports/summary"), calls)
            self.assertIn(("POST", "/enterprise/api/v1/accounts/:account_id/checkout"), calls)
            self.assertIn(("POST", "/api/v1/profile/mfa/backup_codes"), calls)
            self.assertIn(("POST", "/api/:API_VERSION/accounts/:accountId/upload"), calls)
            self.assertIn(("POST", "/auth/sign_in"), calls)
            self.assertNotIn(("GET", ":url/:id"), calls)
            self.assertFalse(any(endpoint == "FRONTEND_URL" for _method, endpoint in calls))

            links = {
                (link.method, link.endpoint): link.matched_route
                for link in facts.api_links
                if link.matched_route
            }
            self.assertEqual(
                "/api/v1/accounts/{account_id}/agents",
                links[("GET", "/api/v1/accounts/:account_id/agents")],
            )
            self.assertEqual(
                "/api/v1/accounts/{account_id}/agents/bulk_create",
                links[("POST", "/api/v1/accounts/:account_id/agents/bulk_create")],
            )
            archive_link = next(
                link
                for link in facts.api_links
                if link.method == "POST"
                and link.endpoint == "/api/v1/accounts/:account_id/agents/archive"
            )
            self.assertIsNone(archive_link.matched_route)
            search_link = next(
                link
                for link in facts.api_links
                if link.method == "GET"
                and link.endpoint == "/api/v1/accounts/:account_id/agents/search"
            )
            self.assertIsNone(search_link.matched_route)
            self.assertEqual(
                "/api/v1/accounts/{account_id}/agent_bots/{id}/avatar",
                links[("DELETE", "/api/v1/accounts/:account_id/agent_bots/:botId/avatar")],
            )
            self.assertEqual(
                "/api/v1/accounts/{account_id}/callbacks/register_facebook_page",
                links[("POST", "/api/v1/accounts/:account_id/callbacks/register_facebook_page")],
            )
            self.assertEqual(
                "/api/v1/accounts/{account_id}/portals/{portal_slug}/articles/{id}",
                links[("GET", "/api/v1/accounts/:account_id/portals/:portalSlug/articles/:id")],
            )
            self.assertEqual(
                "/enterprise/api/v1/accounts/{account_id}/checkout",
                links[("POST", "/enterprise/api/v1/accounts/:account_id/checkout")],
            )
            self.assertEqual(
                "/api/v1/accounts/{account_id}/upload",
                links[("POST", "/api/:API_VERSION/accounts/:accountId/upload")],
            )
            self.assertEqual(
                "/auth/sign_in",
                links[("POST", "/auth/sign_in")],
            )


if __name__ == "__main__":
    unittest.main()
