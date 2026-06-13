from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round102HapiRealworldCalibrationTests(unittest.TestCase):
    def test_hapi_server_route_inline_handler_entrypoint_and_path_params(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "main": "index.js",
  "scripts": {
    "start": "nodemon --ignore test/",
    "test": "lab"
  },
  "dependencies": {
    "hapi": "^16.4.3",
    "glue": "^4.1.0",
    "mongoose": "^4.11.1"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "index.js").write_text("require('./lib')\n", encoding="utf-8")
            lib = root / "lib"
            config = lib / "config"
            api = lib / "modules" / "api"
            articles = api / "articles"
            config.mkdir(parents=True)
            articles.mkdir(parents=True)
            (lib / "index.js").write_text(
                """
const Glue = require('glue')
const manifest = require('./config/manifest')

Glue.compose(manifest, { relativeTo: process.cwd() + '/lib/modules' }, (err, server) => {
  if (err) throw err
  server.start()
})
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (config / "manifest.js").write_text(
                """
module.exports = {
  registrations: [
    {
      plugin: { register: './api' },
      options: { routes: { prefix: '/api' } }
    }
  ]
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (api / "index.js").write_text(
                """
const register = (server, options, next) => {
  server.register(require('./articles'))

  server.route({
    method: 'GET',
    path: '/status',
    config: {
      description: 'Status endpoint',
      tags: ['api', 'status']
    },
    handler: (request, reply) => {
      return reply({ status: 'UP' })
    }
  })

  return next()
}

register.attributes = { pkg: require('./package.json') }
module.exports = register
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (articles / "routes.js").write_text(
                """
module.exports = (server) => {
  const handlers = require('./handlers')(server)
  return [
    {
      method: 'GET',
      path: '/articles/{slug}',
      config: {
        response: outputValidations.ArticleOnGetOutputValidationsConfig
      },
      handler: handlers.getArticle
    }
  ]
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (articles / "handlers.js").write_text(
                """
module.exports = (server) => ({
  getArticle (request, reply) {
    return reply({ article: request.params.slug })
  }
})
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {item.name for item in facts.frameworks}
            self.assertIn("hapi", frameworks)
            self.assertIn("mongoose", frameworks)

            entrypoints = {(item.kind, item.path, item.command) for item in facts.entrypoints}
            self.assertIn(("node-app-entrypoint", "index.js", "npm run start"), entrypoints)

            routes = {(item.method, item.path, item.handler): item for item in facts.api_routes if item.framework == "hapi"}
            self.assertIn(("GET", "/api/status", "inline-handler"), routes)
            self.assertIn(("GET", "/api/articles/{slug}", "handlers.getArticle"), routes)

            article_route = routes[("GET", "/api/articles/{slug}", "handlers.getArticle")]
            self.assertEqual(["slug"], [param.name for param in article_route.parameters])
            self.assertTrue(all(param.source == "path" for param in article_route.parameters))


if __name__ == "__main__":
    unittest.main()
