from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round81NocoDbCalibrationTests(unittest.TestCase):
    def test_large_test_fixture_data_does_not_pollute_test_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                (
                    '{"scripts":{'
                    '"registerIntegrations":"node build-utils/registerIntegrations.js",'
                    '"start":"npm run watch:run",'
                    '"watch:run":"cross-env ENTRYPOINT=src/run/docker rspack --config rspack.dev.config.js"'
                    '},'
                    '"dependencies":{"express":"^4.18.0","knex":"^3.1.0"},'
                    '"devDependencies":{"vitest":"^2.0.0"}}\n'
                ),
                encoding="utf-8",
            )
            src = root / "src"
            src.mkdir()
            (src / "server.ts").write_text(
                """
import express from "express";

const app = express();
app.get("/", Get);
app.get("/api/users", listUsers);

function Get(req, res) {
  res.send("ok");
}

function listUsers(req, res) {
  res.status(200).json([]);
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            run_dir = src / "run"
            run_dir.mkdir()
            (run_dir / "docker.ts").write_text(
                'import "../server";\n',
                encoding="utf-8",
            )
            build_utils = root / "build-utils"
            build_utils.mkdir()
            (build_utils / "registerIntegrations.js").write_text("console.log('helper')\n", encoding="utf-8")
            db = src / "db"
            db.mkdir()
            (db / "meta.ts").write_text(
                """
import type { Knex } from "knex";

enum MetaTable {
  USERS = "nc_users",
}

export async function ensureUsers(knex: Knex, ncMeta: any) {
  await knex.schema.hasTable("nc_users");
  return ncMeta.knexConnection(MetaTable.USERS).where("id", "u1");
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            components = src / "components"
            components.mkdir()
            (components / "Dock.vue").write_text(
                "<template><aside /></template>\n",
                encoding="utf-8",
            )
            (components / "Local.vue").write_text(
                "<template><section /></template>\n",
                encoding="utf-8",
            )
            (components / "Setup.vue").write_text(
                "<template><section /></template>\n",
                encoding="utf-8",
            )
            tests = root / "tests"
            tests.mkdir()
            (tests / "users.test.ts").write_text(
                """
describe("users", () => {
  it("calls the route", async () => {
    await fetch("/api/users");
  });
});
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (tests / "install.bats").write_text(
                "setup() { echo setup help; }\ncurl --request GET /\n",
                encoding="utf-8",
            )
            (tests / "sakila-insert-data.sql").write_text(
                ("INSERT INTO audit_log VALUES ('GET /api/users should not count from fixture data');\n" * 5000),
                encoding="utf-8",
            )
            golden = root / "docker-compose" / "tests" / "golden" / "local"
            golden.mkdir(parents=True)
            (golden / "docker-compose.yml").write_text(
                "services:\n  app:\n    image: nocodb/nocodb\n",
                encoding="utf-8",
            )
            gui = root / "packages" / "gui"
            gui.mkdir(parents=True)
            (gui / "package.json").write_text(
                '{"scripts":{"dev":"nuxt dev"},"dependencies":{"nuxt":"^3.0.0","vue":"^3.0.0"}}\n',
                encoding="utf-8",
            )
            (gui / "nuxt.config.ts").write_text("export default defineNuxtConfig({})\n", encoding="utf-8")
            (gui / "app.vue").write_text("<template><NuxtPage /></template>\n", encoding="utf-8")
            library = root / "packages" / "library"
            library.mkdir()
            (library / "package.json").write_text(
                '{"main":"lib/index.js","dependencies":{"express":"^4.18.0"}}\n',
                encoding="utf-8",
            )
            (library / "lib").mkdir()
            (library / "lib" / "index.js").write_text("export const helper = true\n", encoding="utf-8")

            facts = scan_project(root)
            maps = {item.test_path: item for item in facts.test_maps}
            entrypoints = {(item.kind, item.path, item.command) for item in facts.entrypoints}
            entrypoint_paths = {item.path for item in facts.entrypoints}
            data_layers = {(item.kind, item.path) for item in facts.data_layers}
            data_layer_details = {
                item.path: item.details for item in facts.data_layers if item.path == "src/db/meta.ts"
            }

            self.assertEqual("api-route", maps["tests/users.test.ts"].target_kind)
            self.assertEqual("GET /api/users", maps["tests/users.test.ts"].target)
            self.assertEqual("unmatched", maps["tests/install.bats"].target_kind)
            self.assertEqual("unmatched", maps["tests/sakila-insert-data.sql"].target_kind)
            self.assertIsNone(maps["tests/sakila-insert-data.sql"].target)
            self.assertEqual("unmatched", maps["docker-compose/tests/golden/local/docker-compose.yml"].target_kind)
            self.assertIn(("node-app-entrypoint", "src/run/docker.ts", "npm run start"), entrypoints)
            self.assertNotIn("build-utils/registerIntegrations.js", entrypoint_paths)
            self.assertNotIn("packages/library/lib/index.js", entrypoint_paths)
            self.assertIn(("nuxt-entrypoint", "packages/gui/app.vue", "npm --prefix packages/gui run dev"), entrypoints)
            self.assertIn(("knex-query-builder", "src/db/meta.ts"), data_layers)
            self.assertIn("knex-schema:hasTable", data_layer_details["src/db/meta.ts"])
            self.assertIn("meta-table:USERS", data_layer_details["src/db/meta.ts"])


if __name__ == "__main__":
    unittest.main()
