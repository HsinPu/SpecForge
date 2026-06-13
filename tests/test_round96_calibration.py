from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round96RemixCalibrationTests(unittest.TestCase):
    def test_remix_entrypoint_jsx_forms_and_express_catchall_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "scripts": {
    "start": "node ./server.ts",
    "dev": "remix vite:dev",
    "test": "vitest"
  },
  "dependencies": {
    "@remix-run/express": "^2.0.0",
    "@remix-run/node": "^2.0.0",
    "express": "^4.18.0",
    "react": "^18.0.0",
    "vite": "^5.0.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "server.ts").write_text(
                """
import express from "express";
import { createRequestHandler } from "@remix-run/express";

const app = express();
app.get("/healthz", healthHandler);
app.all("*", function getReplayResponse(req, res, next) {
  return next();
});
app.all(
  "*",
  createRequestHandler({ build: require("./build") })
);
app.listen(process.env.PORT || 3000);
""".strip()
                + "\n",
                encoding="utf-8",
            )
            routes = root / "app" / "routes"
            routes.mkdir(parents=True)
            (routes / "register.tsx").write_text(
                """
import { Form } from "@remix-run/react";

export async function action({ request }) {
  const formData = await request.formData();
  return null;
}

export default function Register() {
  return (
    <Form method="post">
      <input name="email" />
      <input name="password" />
      <input name="password_confirmation" />
    </Form>
  );
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (routes / "articles.$slug.tsx").write_text(
                """
import { Form } from "@remix-run/react";

export async function loader() {
  return null;
}

export async function action({ params, request }) {
  return null;
}

export default function Article({ article }) {
  return (
    <>
      <Form method="post" action={`/articles/${article.slug}/favorites`}>
        <button>Favorite</button>
      </Form>
      <Form method="post">
        <textarea name="content" />
        <input type="hidden" name={"commentId"} />
        <button>Comment</button>
      </Form>
    </>
  );
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            components = root / "app" / "components"
            components.mkdir(parents=True)
            (components / "header.tsx").write_text(
                """
import { Form } from "@remix-run/react";

export function Header() {
  return (
    <Form method="post" action="/logout">
      <button>Logout</button>
    </Form>
  );
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            entrypoints = {(item.kind, item.path, item.command) for item in facts.entrypoints}
            self.assertIn(("remix-server-entrypoint", "server.ts", "npm run start"), entrypoints)

            routes_seen = {(item.framework, item.method, item.path) for item in facts.api_routes}
            self.assertIn(("express", "GET", "/healthz"), routes_seen)
            self.assertNotIn(("express", "ALL", "*"), routes_seen)

            forms_by_action = {item.action: item for item in facts.forms}
            self.assertIn("/register", forms_by_action)
            self.assertEqual(forms_by_action["/register"].method, "POST")
            self.assertEqual(forms_by_action["/register"].fields, ["email", "password", "password_confirmation"])
            self.assertIn("/articles/:slug/favorites", forms_by_action)
            self.assertIn("/articles/:slug", forms_by_action)
            self.assertEqual(forms_by_action["/articles/:slug"].fields, ["content", "commentId"])
            self.assertIn("/logout", forms_by_action)


if __name__ == "__main__":
    unittest.main()
