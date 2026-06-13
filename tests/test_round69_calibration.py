from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round69SvelteKitCalibrationTests(unittest.TestCase):
    def test_sveltekit_server_actions_forms_endpoints_and_type_docs_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "@sveltejs/kit": "^2.0.0",
    "svelte": "^5.0.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            api_route = root / "src" / "routes" / "api" / "posts" / "[slug]"
            login_route = root / "src" / "routes" / "login"
            types_dir = root / "src" / "lib"
            api_route.mkdir(parents=True)
            login_route.mkdir(parents=True)
            types_dir.mkdir(parents=True)

            (api_route / "+server.ts").write_text(
                """
export async function GET({ params }) {
  return Response.json({ slug: params.slug });
}

export const POST = async ({ request, params }) => {
  const body = await request.json();
  return Response.json({ body, slug: params.slug }, { status: 201 });
};
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (login_route / "+page.server.ts").write_text(
                """
export async function load({ locals }) {
  return { user: locals.user };
}

export const actions = {
  default: async ({ request }) => {
    const data = await request.formData();
    return { ok: Boolean(data.get('email')) };
  },
  logout: async ({ cookies }) => {
    cookies.delete('jwt', { path: '/' });
  }
};
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (login_route / "+page.svelte").write_text(
                """
<script>
  import { enhance } from '$app/forms';
</script>

<form use:enhance method="POST">
  <input name="email" type="email" />
  <input name="password" type="password" />
</form>

<form
  use:enhance={() => {
    return () => {};
  }}
  method="POST"
  action="?/logout"
>
  <button type="submit">Sign out</button>
</form>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (types_dir / "api.d.ts").write_text(
                """
/**
 * Example only:
 * fetch('/docs-only');
 */
export interface ApiClient {}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.framework, route.kind, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("sveltekit", "sveltekit-endpoint", "GET", "/api/posts/:slug", "GET"), routes)
            self.assertIn(("sveltekit", "sveltekit-endpoint", "POST", "/api/posts/:slug", "POST"), routes)
            self.assertIn(("sveltekit", "sveltekit-page-server-load", "LOAD", "/login", "load"), routes)
            self.assertIn(("sveltekit", "sveltekit-form-action", "POST", "/login", "actions.default"), routes)
            self.assertIn(("sveltekit", "sveltekit-form-action", "POST", "/login?/logout", "actions.logout"), routes)

            post_route = next(route for route in facts.api_routes if route.path == "/api/posts/:slug" and route.method == "POST")
            self.assertEqual(["slug"], [param.name for param in post_route.parameters])
            self.assertEqual("request", post_route.request_body)
            default_action = next(route for route in facts.api_routes if route.path == "/login" and route.handler == "actions.default")
            self.assertEqual("formData", default_action.request_body)

            forms = {(form.source, form.method, form.action, tuple(form.fields)) for form in facts.forms}
            self.assertIn(("src/routes/login/+page.svelte", "POST", "/login", ("email", "password")), forms)
            self.assertIn(("src/routes/login/+page.svelte", "POST", "/login?/logout", ()), forms)

            calls = {(call.client, call.endpoint) for call in facts.api_calls}
            self.assertNotIn(("fetch", "/docs-only"), calls)


if __name__ == "__main__":
    unittest.main()
