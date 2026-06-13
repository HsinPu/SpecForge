from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round44HapiCalibrationTests(unittest.TestCase):
    def test_hapi_routes_prefixes_and_contract_hints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"dependencies":{"hapi":"^16.0.0","hapi-auth-jwt2":"^8.0.0","mongoose":"^5.0.0"}}\n',
                encoding="utf-8",
            )
            config = root / "lib" / "config"
            users = root / "lib" / "modules" / "api" / "users"
            models = root / "lib" / "modules" / "models"
            config.mkdir(parents=True)
            users.mkdir(parents=True)
            models.mkdir(parents=True)
            (config / "manifest.js").write_text(
                """
module.exports = {
  registrations: [
    {
      plugin: { register: './api' },
      options: {
        routes: {
          prefix: '/api'
        }
      }
    }
  ]
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (users / "routes.js").write_text(
                """
const inputValidations = require('./validations/input')
const outputValidations = require('./validations/output')

module.exports = (server) => {
  const handlers = require('./handlers')(server)
  return [
    {
      method: 'GET',
      path: '/user',
      config: {
        auth: 'jwt',
        validate: inputValidations.GetCurrentPayload,
        response: outputValidations.AuthOutputValidationConfig
      },
      handler: handlers.getCurrentUser
    },
    {
      method: 'POST',
      path: '/users',
      config: {
        validate: inputValidations.RegisterPayload,
        response: outputValidations.AuthOnRegisterOutputValidationConfig
      },
      handler: handlers.registerUser
    }
  ]
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (users / "handlers.js").write_text(
                """
module.exports = (server) => {
  return {
    getCurrentUser (request, reply) {
      const { user } = request.auth.credentials
      return reply({ user })
    },

    registerUser (request, reply) {
      let payload = request.payload
      if (!payload.user) return reply({ errors: {} }).code(422)
      return reply({ user: payload.user }).code(201)
    }
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (models / "User.js").write_text(
                """
var mongoose = require('mongoose')

var UserSchema = new mongoose.Schema({
  username: { type: String, unique: true, required: true, index: true },
  email: { type: String, lowercase: true, required: [true, "can't be blank"] },
  favorites: [{ type: mongoose.Schema.Types.ObjectId, ref: 'Article' }],
  bio: String
}, { timestamps: true })

UserSchema.methods.toAuthJSON = function () {
  return { username: this.username }
}

module.exports = mongoose.model('User', UserSchema)
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("hapi", frameworks)
            self.assertIn("mongoose", frameworks)

            routes_seen = {(route.framework, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("hapi", "GET", "/api/user", "handlers.getCurrentUser"), routes_seen)
            self.assertIn(("hapi", "POST", "/api/users", "handlers.registerUser"), routes_seen)

            get_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "hapi" and contract.method == "GET" and contract.path == "/api/user"
            )
            self.assertIn("auth:jwt", get_contract.request_hints)
            self.assertIn("validate:inputValidations.GetCurrentPayload", get_contract.request_hints)
            self.assertIn("auth:request.auth.credentials", get_contract.request_hints)
            self.assertIn("response:reply", get_contract.response_hints)

            post_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "hapi" and contract.method == "POST" and contract.path == "/api/users"
            )
            self.assertIn("body:request.payload", post_contract.request_hints)
            self.assertIn("body:payload.user", post_contract.request_hints)
            self.assertIn("response-schema:outputValidations.AuthOnRegisterOutputValidationConfig", post_contract.response_hints)
            self.assertIn("201", post_contract.status_codes)
            self.assertIn("422", post_contract.status_codes)

            models_by_name = {model.name: model for model in facts.data_models}
            self.assertIn("User", models_by_name)
            self.assertEqual("mongoose-model", models_by_name["User"].kind)
            self.assertIn("username:String", models_by_name["User"].fields)
            self.assertIn("favorites:Array<ObjectId>", models_by_name["User"].fields)
            self.assertIn("ref:favorites:Article", models_by_name["User"].annotations)
            self.assertIn("timestamps:true", models_by_name["User"].annotations)

            data_layers = {(item.kind, item.name) for item in facts.data_layers}
            self.assertIn(("code-model:mongoose-model", "User"), data_layers)


if __name__ == "__main__":
    unittest.main()
