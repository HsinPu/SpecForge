from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round103FeathersMountCalibrationTests(unittest.TestCase):
    def test_feathers_app_mount_prefix_and_directory_entrypoint_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "main": "src",
  "scripts": {
    "start": "node src/",
    "test": "mocha test/"
  },
  "dependencies": {
    "@feathersjs/feathers": "^3.3.0",
    "@feathersjs/express": "^1.3.0",
    "feathers-mongoose": "^7.3.0",
    "mongoose": "^5.4.8"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            src = root / "src"
            service = src / "services" / "articles" / "comments"
            src.mkdir()
            service.mkdir(parents=True)
            (src / "index.js").write_text(
                """
const app = require('./app');
const express = require('@feathersjs/express');
const mainApp = express().use('/api', app);
const server = mainApp.listen(3030);
app.setup(server);
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (src / "app.js").write_text(
                """
const feathers = require('@feathersjs/feathers');
const express = require('@feathersjs/express');
const app = express(feathers());
module.exports = app;
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (service / "comments.service.js").write_text(
                """
const createService = require('./comments.class.js');

module.exports = function (app) {
  app.use('/articles/:slug/comments', createService({}));
  const service = app.service('articles/:slug/comments');
  service.hooks({});
};
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (service / "comments.class.js").write_text(
                """
class Service {
  async find(params) { return []; }
  async create(data, params) { return data; }
  async remove(id, params) { return { id }; }
}

module.exports = function () {
  return new Service();
};
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(item.name, item.category) for item in facts.frameworks}
            self.assertIn(("feathers", "backend"), frameworks)
            self.assertIn(("feathers-mongoose", "data"), frameworks)

            entrypoints = {(item.kind, item.path, item.command) for item in facts.entrypoints}
            self.assertIn(("node-app-entrypoint", "src/index.js", "npm run start"), entrypoints)

            routes = {(item.method, item.path, item.handler): item for item in facts.api_routes if item.framework == "feathers"}
            self.assertIn(("GET", "/api/articles/:slug/comments", "service.find"), routes)
            self.assertIn(("POST", "/api/articles/:slug/comments", "service.create"), routes)
            self.assertIn(("DELETE", "/api/articles/:slug/comments/{id}", "service.remove"), routes)
            self.assertNotIn(("GET", "/articles/:slug/comments", "service.find"), routes)

            create_route = routes[("POST", "/api/articles/:slug/comments", "service.create")]
            self.assertEqual("data", create_route.request_body)
            self.assertEqual(["slug"], [param.name for param in create_route.parameters])


if __name__ == "__main__":
    unittest.main()
