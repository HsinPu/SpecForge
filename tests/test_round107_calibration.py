from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round107AstroDocsCalibrationTests(unittest.TestCase):
    def test_astro_starlight_content_pages_entrypoint_and_collections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "type": "module",
  "packageManager": "pnpm@11.1.2",
  "scripts": {
    "dev": "astro dev",
    "build": "astro build",
    "check": "astro check"
  },
  "dependencies": {
    "astro": "^6.3.0",
    "@astrojs/starlight": "^0.39.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "pnpm-lock.yaml").write_text("lockfileVersion: '11.0'\n", encoding="utf-8")
            (root / "astro.config.ts").write_text(
                """
import starlight from '@astrojs/starlight';
import { defineConfig } from 'astro/config';

export default defineConfig({
  integrations: [starlight({ title: 'Docs' })],
});
""".strip()
                + "\n",
                encoding="utf-8",
            )
            pages = root / "src" / "pages"
            docs = root / "src" / "content" / "docs" / "en" / "guides" / "backend"
            pages.mkdir(parents=True)
            docs.mkdir(parents=True)
            (pages / "index.astro").write_text("---\n---\n<h1>Home</h1>\n", encoding="utf-8")
            (docs.parent.parent / "getting-started.mdx").write_text(
                "---\ntitle: Getting started\n---\n\n# Getting started\n",
                encoding="utf-8",
            )
            (docs / "index.mdx").write_text(
                "---\ntitle: Backend guides\n---\n\n# Backend guides\n",
                encoding="utf-8",
            )
            (root / "src" / "content.config.ts").write_text(
                """
import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema } from '@astrojs/starlight/schema';
import { defineCollection } from 'astro:content';
import { z } from 'astro/zod';

const contributorSchema = z.object({
  id: z.number(),
  login: z.string(),
});

export const collections = {
  docs: defineCollection({
    loader: docsLoader(),
    schema: docsSchema({ extend: z.object({ title: z.string(), i18nReady: z.boolean() }) }),
  }),
  contributors: defineCollection({
    loader: async () => [],
    schema: z.object({ avatar_url: z.string(), commits: z.number() }),
  }),
};
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("astro", frameworks)
            self.assertIn("starlight", frameworks)

            entrypoints = {(entry.kind, entry.path, entry.command) for entry in facts.entrypoints}
            self.assertIn(("astro-entrypoint", "src/pages/index.astro", "pnpm run dev"), entrypoints)

            routes = {(route.framework, route.kind, route.route, route.path) for route in facts.frontend_routes}
            self.assertIn(
                ("astro", "astro-content-page-route", "/en/getting-started", "src/content/docs/en/getting-started.mdx"),
                routes,
            )
            self.assertIn(
                ("astro", "astro-content-page-route", "/en/guides/backend", "src/content/docs/en/guides/backend/index.mdx"),
                routes,
            )

            pages = {(page.kind, page.template_engine, page.route, page.title) for page in facts.pages}
            self.assertIn(("content-page", "astro-content", "/en/getting-started", "Getting started"), pages)
            self.assertIn(("content-page", "astro-content", "/en/guides/backend", "Backend guides"), pages)

            models = {model.name: model for model in facts.data_models if model.kind == "astro-content-collection"}
            self.assertIn("docs", models)
            self.assertIn("contributors", models)
            self.assertIn("loader:docsLoader", models["docs"].annotations)
            self.assertIn("schema:docsSchema", models["docs"].annotations)
            self.assertEqual(models["contributors"].fields, ["avatar_url", "commits"])


if __name__ == "__main__":
    unittest.main()
