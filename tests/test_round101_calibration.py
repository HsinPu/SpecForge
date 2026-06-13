from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round101GrapeCalibrationTests(unittest.TestCase):
    def test_grape_routes_rack_entrypoint_and_no_sinatra_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Gemfile").write_text(
                """
source 'https://rubygems.org'

gem 'grape'
gem 'grape-swagger'
gem 'rack'
gem 'rackup'
gem 'rspec'
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "config.ru").write_text("require './app/api'\nrun Demo::API\n", encoding="utf-8")
            (root / "Rakefile").write_text("task default: :spec\n", encoding="utf-8")
            (root / "spec").mkdir()
            app = root / "app"
            api = root / "api"
            app.mkdir()
            api.mkdir()
            (app / "api.rb").write_text(
                """
module Demo
  class API < Grape::API
    prefix 'api'
    format :json
    mount ::Demo::PostPut
    mount ::Demo::V1::Entities
    mount ::Demo::PathVersioning
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (api / "post_put.rb").write_text(
                """
module Demo
  class PostPut < Grape::API
    format :json
    resource :ring do
      get do
        { rang: 1 }
      end
      params do
        requires :count, type: Integer, documentation: { param_type: 'body' }
      end
      put do
        { rang: params[:count] }
      end
      get :fail do
        error!({ error: 'no' }, 422)
      end
    end
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (api / "entities.rb").write_text(
                """
module Demo
  module V1

    class Entities < Grape::API
      namespace :entities do
        params do
          optional :foo, type: String
        end
        get ':id' do
          present params[:id]
        end
      end
    end
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (api / "path_versioning.rb").write_text(
                """
module Demo
  class PathVersioning < Grape::API
    version 'vendor', using: :path, vendor: 'demo', format: :json
    get do
      { path: 'demo' }
    end
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {item.name for item in facts.frameworks}
            self.assertIn("grape", frameworks)
            self.assertNotIn("sinatra", frameworks)

            entrypoints = {(item.kind, item.path, item.command) for item in facts.entrypoints}
            self.assertIn(("grape-rack-app", "config.ru", "bundle exec rackup"), entrypoints)

            commands = {item.name for item in facts.commands}
            self.assertIn("bundle exec rackup", commands)
            self.assertIn("bundle exec rspec", commands)
            self.assertIn("bundle exec rake", commands)

            routes = {(item.framework, item.method, item.path, item.handler) for item in facts.api_routes}
            self.assertIn(("grape", "GET", "/api/ring", "Demo::PostPut"), routes)
            self.assertIn(("grape", "PUT", "/api/ring", "Demo::PostPut"), routes)
            self.assertIn(("grape", "GET", "/api/ring/fail", "Demo::PostPut"), routes)
            self.assertIn(("grape", "GET", "/api/entities/{id}", "Demo::V1::Entities"), routes)
            self.assertIn(("grape", "GET", "/api/vendor", "Demo::PathVersioning"), routes)

            put_route = next(item for item in facts.api_routes if item.method == "PUT" and item.path == "/api/ring")
            self.assertEqual("params", put_route.request_body)
            self.assertIn(("count", "body", "Integer"), {(param.name, param.source, param.type) for param in put_route.parameters})

            entity_route = next(item for item in facts.api_routes if item.path == "/api/entities/{id}")
            self.assertIn(("id", "path", None), {(param.name, param.source, param.type) for param in entity_route.parameters})
            self.assertIn(("foo", "query", "String"), {(param.name, param.source, param.type) for param in entity_route.parameters})

            fail_contract = next(item for item in facts.api_contracts if item.path == "/api/ring/fail")
            self.assertIn("422", fail_contract.status_codes)
            self.assertIn("error:error!", fail_contract.error_hints)


if __name__ == "__main__":
    unittest.main()
