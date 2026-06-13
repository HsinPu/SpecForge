from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round46SailsCalibrationTests(unittest.TestCase):
    def test_sails_routes_actions_contracts_and_waterline_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"dependencies":{"sails":"^1.5.0","sails-hook-orm":"^2.0.0"}}\n',
                encoding="utf-8",
            )
            config = root / "config"
            controllers = root / "api" / "controllers" / "users"
            models = root / "api" / "models"
            config.mkdir()
            controllers.mkdir(parents=True)
            models.mkdir(parents=True)
            (config / "routes.js").write_text(
                """
module.exports.routes = {
  'GET /': async function(req, res) {
    return res.view('pages/homepage')
  },

  '/login': {
    view: 'pages/auth/login'
  },

  'POST /api/users': {
    action: 'users/register'
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (controllers / "register.js").write_text(
                """
module.exports = {
  inputs: {
    username: {
      type: 'string',
      required: true
    },
    email: {
      type: 'string',
      required: true
    }
  },
  exits: {
    emailAlreadyExists: {
      responseType: 'badEntity'
    }
  },
  fn: async function(inputs, exits) {
    const user = await User.create({
      username: inputs.username,
      email: inputs.email
    }).intercept('E_UNIQUE', 'emailAlreadyExists').fetch()

    return exits.success({ user })
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (models / "User.js").write_text(
                """
module.exports = {
  attributes: {
    email: {
      type: 'string',
      unique: true,
      required: true
    },
    username: {
      type: 'string',
      required: true
    },
    articles: {
      collection: 'Article',
      via: 'author'
    }
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("sails", frameworks)
            self.assertIn("waterline", frameworks)

            routes = {(route.framework, route.kind, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("sails", "sails-route", "GET", "/", "inline"), routes)
            self.assertIn(("sails", "sails-view-route", "GET", "/login", "view:pages/auth/login"), routes)
            self.assertIn(("sails", "sails-route", "POST", "/api/users", "users/register"), routes)

            register_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "sails" and contract.method == "POST" and contract.path == "/api/users"
            )
            self.assertIn("body:input.username:string required", register_contract.request_hints)
            self.assertIn("body:inputs.email", register_contract.request_hints)
            self.assertIn("response:exits.success", register_contract.response_hints)
            self.assertIn("response-type:badEntity", register_contract.response_hints)
            self.assertIn("error-exit:emailAlreadyExists", register_contract.error_hints)

            models_by_name = {model.name: model for model in facts.data_models}
            self.assertIn("User", models_by_name)
            self.assertEqual("sails-waterline-model", models_by_name["User"].kind)
            self.assertIn("email:string", models_by_name["User"].fields)
            self.assertIn("articles:collection<Article>", models_by_name["User"].fields)
            self.assertIn("unique:email", models_by_name["User"].annotations)
            self.assertIn("collection:articles:Article", models_by_name["User"].annotations)

            data_layers = {(item.kind, item.name) for item in facts.data_layers}
            self.assertIn(("code-model:sails-waterline-model", "User"), data_layers)


if __name__ == "__main__":
    unittest.main()
