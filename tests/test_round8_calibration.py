from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round8CalibrationTests(unittest.TestCase):

    def test_scan_project_detects_runtime_config_and_nuxt_api_wrappers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "nuxt": "^3.0.0",
    "vue": "^3.0.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            composables = root / "composables"
            composables.mkdir()
            (composables / "useAPI.ts").write_text(
                """
import { useFetch, useRuntimeConfig } from '#imports';

export function useAPI<T = unknown>(url: string, userOptions = {}) {
  const config = useRuntimeConfig();
  const options = {
    baseURL: `${config.public.baseUrl}`,
    method: 'GET',
    ...userOptions,
  };
  return useFetch(url, options);
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            services = root / "services"
            services.mkdir()
            (services / "articles.ts").write_text(
                """
import { useAPI } from '~/composables';

export function listArticles() {
  return useAPI<AllArticles>('/articles');
}

export function createArticle(data: Article) {
  return useAPI<Article>('/articles', { method: 'POST', body: { article: data } });
}

export function updateArticle(slug: string, data: Article) {
  return useAPI<Article>(`/articles/${slug}`, { method: 'PUT', body: { article: data } });
}

export function submitDynamic(url: string) {
  return useAPI<Article>(url, { method: 'POST' });
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            rails_config = root / "config"
            rails_env = rails_config / "environments"
            rails_env.mkdir(parents=True)
            (rails_config / "secrets.yml").write_text(
                """
development:
  secret_key_base: literal-secret-should-not-be-rendered
production:
  secret_key_base: <%= ENV["SECRET_KEY_BASE"] %>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (rails_env / "production.rb").write_text(
                """
Rails.application.configure do
  config.serve_static_files = ENV['RAILS_SERVE_STATIC_FILES'].present?
  config.assets.compile = false
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            phoenix_config = rails_config / "prod.exs"
            phoenix_config.write_text(
                """
use Mix.Config

config :demo, DemoWeb.Endpoint,
  http: [port: {:system, "PORT"}],
  secret_key_base: Map.fetch!(System.get_env(), "SECRET_KEY_BASE")

config :demo, Demo.Repo,
  url: System.get_env("DATABASE_URL"),
  pool_size: String.to_integer(System.get_env("POOL_SIZE") || "10")
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            runtime_values = {value for fact in facts.runtime_configs for value in fact.values}
            self.assertIn("env-key:SECRET_KEY_BASE", runtime_values)
            self.assertIn("env-key:RAILS_SERVE_STATIC_FILES", runtime_values)
            self.assertIn("env-key:PORT", runtime_values)
            self.assertIn("env-key:DATABASE_URL", runtime_values)
            self.assertIn("env-key:POOL_SIZE", runtime_values)
            self.assertIn("config-key:secret_key_base", runtime_values)
            self.assertNotIn("literal-secret-should-not-be-rendered", runtime_values)
            self.assertIn("rails-config", {fact.kind for fact in facts.runtime_configs})
            self.assertIn("phoenix-config", {fact.kind for fact in facts.runtime_configs})

            api_calls = {(call.client, call.method, call.endpoint, call.context) for call in facts.api_calls}
            self.assertIn(("useAPI", "GET", "/articles", "composable-api"), api_calls)
            self.assertIn(("useAPI", "POST", "/articles", "composable-api"), api_calls)
            self.assertIn(("useAPI", "PUT", "/articles/${slug}", "composable-api"), api_calls)
            self.assertIn(("useAPI", "POST", "dynamic:url", "composable-api"), api_calls)
            self.assertIn(("useFetch", "GET", "dynamic:url", "dynamic-source"), api_calls)


if __name__ == "__main__":
    unittest.main()
