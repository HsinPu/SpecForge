from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round51RemixCalibrationTests(unittest.TestCase):
    def test_remix_route_modules_contracts_and_prisma_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"dependencies":{"@remix-run/node":"*","@remix-run/react":"*","@prisma/client":"^5.0.0","react":"^18.0.0"},"devDependencies":{"@remix-run/dev":"*","prisma":"^5.0.0"}}\n',
                encoding="utf-8",
            )
            routes = root / "app" / "routes"
            routes.mkdir(parents=True)
            (root / "prisma").mkdir()
            (routes / "notes.$noteId.tsx").write_text(
                """
import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json, redirect } from "@remix-run/node";
import { deleteNote, getNote } from "~/models/note.server";
import { requireUserId } from "~/session.server";

export const loader = async ({ params, request }: LoaderFunctionArgs) => {
  const userId = await requireUserId(request);
  const note = await getNote({ id: params.noteId, userId });
  if (!note) {
    throw new Response("Not Found", { status: 404 });
  }
  return json({ note });
};

export const action = async ({ params, request }: ActionFunctionArgs) => {
  const userId = await requireUserId(request);
  await deleteNote({ id: params.noteId, userId });
  return redirect("/notes");
};

export default function NotePage() {
  return <div />;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (routes / "notes.new.tsx").write_text(
                """
import type { ActionFunctionArgs } from "@remix-run/node";
import { json, redirect } from "@remix-run/node";
import { createNote } from "~/models/note.server";
import { requireUserId } from "~/session.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  const userId = await requireUserId(request);
  const formData = await request.formData();
  const title = formData.get("title");
  const body = formData.get("body");
  if (typeof title !== "string") {
    return json({ errors: { title: "Title is required" } }, { status: 400 });
  }
  const note = await createNote({ title, body, userId });
  return redirect(`/notes/${note.id}`);
};
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "prisma" / "schema.prisma").write_text(
                """
datasource db {
  provider = "sqlite"
  url = env("DATABASE_URL")
}

generator client {
  provider = "prisma-client-js"
}

model Note {
  id String @id @default(cuid())
  title String
  body String
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frontend_routes = {(route.framework, route.kind, route.route) for route in facts.frontend_routes}
            self.assertIn(("remix", "remix-file-route", "/notes/:noteId"), frontend_routes)
            self.assertIn(("remix", "remix-file-route", "/notes/new"), frontend_routes)

            api_routes = {(route.framework, route.kind, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("remix", "remix-data-route", "GET", "/notes/:noteId", "loader"), api_routes)
            self.assertIn(("remix", "remix-data-route", "POST", "/notes/:noteId", "action"), api_routes)
            self.assertIn(("remix", "remix-data-route", "POST", "/notes/new", "action"), api_routes)

            note_action = next(route for route in facts.api_routes if route.framework == "remix" and route.path == "/notes/:noteId" and route.method == "POST")
            self.assertIn(("path", "noteId"), {(param.source, param.name) for param in note_action.parameters})
            self.assertEqual("redirect", note_action.response_type)

            new_action = next(route for route in facts.api_routes if route.framework == "remix" and route.path == "/notes/new")
            self.assertEqual("formData", new_action.request_body)
            self.assertEqual("json|redirect", new_action.response_type)

            loader_contract = next(contract for contract in facts.api_contracts if contract.framework == "remix" and contract.method == "GET")
            self.assertIn("path:noteId", loader_contract.request_hints)
            self.assertIn("auth:requireUserId", loader_contract.request_hints)
            self.assertIn("model-call:getNote", loader_contract.response_hints)
            self.assertIn("404", loader_contract.status_codes)

            new_contract = next(contract for contract in facts.api_contracts if contract.framework == "remix" and contract.path == "/notes/new")
            self.assertIn("body:formData", new_contract.request_hints)
            self.assertIn("form:title", new_contract.request_hints)
            self.assertIn("model-call:createNote", new_contract.response_hints)
            self.assertNotIn("server-call:get", new_contract.response_hints)

            models = {model.name: model for model in facts.data_models}
            self.assertEqual("prisma-model", models["Note"].kind)
            self.assertIn("id:String", models["Note"].fields)
            self.assertIn("primary-key:id", models["Note"].annotations)


if __name__ == "__main__":
    unittest.main()
