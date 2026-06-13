from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round32SvelteKitCalibrationTests(unittest.TestCase):
    def test_sveltekit_route_modules_api_wrappers_and_route_maps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"devDependencies":{"@sveltejs/kit":"^2.0.0","svelte":"^5.0.0","vite":"^7.0.0"}}\n',
                encoding="utf-8",
            )
            (root / "svelte.config.js").write_text("export default {};\n", encoding="utf-8")
            lib = root / "src" / "lib"
            lib.mkdir(parents=True)
            (lib / "api.js").write_text(
                """
const base = 'https://api.example.test/api';

async function send({ method, path }) {
    return fetch(`${base}/${path}`, { method });
}

export function get(path) {
    return send({ method: 'GET', path });
}

export function del(path) {
    return send({ method: 'DELETE', path });
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            routes = root / "src" / "routes"
            article = routes / "article" / "[slug]"
            article.mkdir(parents=True)
            (routes / "+page.svelte").write_text(
                """
<script>
    import { page } from '$app/state';
    const tab = $derived(page.url.searchParams.get('tab') ?? 'all');
</script>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (routes / "+page.server.js").write_text(
                """
import * as api from '$lib/api';

export async function load() {
    const endpoint = 'articles';
    return api.get(`${endpoint}?limit=10`);
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (article / "+page.svelte").write_text("<h1>Article</h1>\n", encoding="utf-8")
            (article / "ArticleMeta.svelte").write_text("<p>Meta</p>\n", encoding="utf-8")
            (article / "+page.server.js").write_text(
                """
import * as api from '$lib/api.js';

export async function load({ params }) {
    return api.get(`articles/${params.slug}`);
}

export const actions = {
    deleteComment: async ({ params, url }) => {
        const id = url.searchParams.get('id');
        return api.del(`articles/${params.slug}/comments/${id}`);
    }
};
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes_by_source = {(route.route, route.path, route.kind) for route in facts.frontend_routes}
            self.assertIn(("/", "src/routes/+page.svelte", "sveltekit-route"), routes_by_source)
            self.assertIn(("/", "src/routes/+page.server.js", "sveltekit-route"), routes_by_source)
            self.assertIn(("/article/:slug", "src/routes/article/[slug]/+page.server.js", "sveltekit-route"), routes_by_source)

            calls = {(call.method, call.endpoint, call.path) for call in facts.api_calls}
            self.assertIn(("GET", "dynamic:endpoint", "src/routes/+page.server.js"), calls)
            self.assertIn(("GET", "/articles/:slug", "src/routes/article/[slug]/+page.server.js"), calls)
            self.assertIn(("DELETE", "/articles/:slug/comments/:id", "src/routes/article/[slug]/+page.server.js"), calls)
            self.assertIn(("GET", "https://api.example.test/api/:path", "src/lib/api.js"), calls)

            state = {(item.library, item.usage, item.name, item.source) for item in facts.state_usages}
            self.assertIn(("svelte", "rune", "$derived", "src/routes/+page.svelte"), state)

            maps = {item.route: item for item in facts.frontend_maps}
            self.assertIn("/", maps)
            self.assertIn("/article/:slug", maps)
            self.assertIn("dynamic:endpoint", maps["/"].api_calls)
            self.assertIn("/articles/:slug", maps["/article/:slug"].api_calls)
            self.assertIn("ArticleMeta", maps["/article/:slug"].components)


if __name__ == "__main__":
    unittest.main()
