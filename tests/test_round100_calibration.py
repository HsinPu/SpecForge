from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round100SinatraCalibrationTests(unittest.TestCase):
    def test_sinatra_routes_entrypoint_and_active_record_without_rails_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Gemfile").write_text(
                """
source 'https://rubygems.org'

gem 'sinatra'
gem 'sinatra-activerecord'
gem 'activerecord'
gem 'rake'
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "Procfile").write_text("web: bundle exec ruby app.rb -p $PORT\n", encoding="utf-8")
            (root / "config.ru").write_text("require './app'\nrun Sinatra::Application\n", encoding="utf-8")
            (root / "Rakefile").write_text("require 'sinatra/activerecord/rake'\n", encoding="utf-8")
            (root / "db" / "migrate").mkdir(parents=True)
            (root / "db" / "migrate" / "20260101000000_create_lists.rb").write_text(
                """
class CreateLists < ActiveRecord::Migration
  def change
    create_table :lists do |t|
      t.string :name
    end
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "config").mkdir()
            (root / "config" / "cors.rb").write_text(
                """
options "*" do
  response.headers["Allow"] = "HEAD,GET,PUT,POST,DELETE,OPTIONS"
end
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "app.rb").write_text(
                """
require 'sinatra'
require 'sinatra/activerecord'
require './config/cors'
require 'json'

before do
  content_type :json
end

get '/' do
  content_type :html
  send_file './public/index.html'
end

get '/lists/:id' do
  List.where(id: params['id']).first.to_json
end

post '/lists' do
  list = List.new(params)
  halt 422, list.errors.full_messages.to_json unless list.save
  list.to_json
end

put '/lists/:id' do
  list = List.where(id: params['id']).first
  list.name = params['name'] if params.has_key?('name')
  list.to_json
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {item.name for item in facts.frameworks}
            self.assertIn("sinatra", frameworks)
            self.assertIn("active-record", frameworks)
            self.assertNotIn("rails", frameworks)

            entrypoints = {(item.kind, item.path, item.command) for item in facts.entrypoints}
            self.assertIn(("sinatra-rack-app", "config.ru", "bundle exec ruby app.rb -p $PORT"), entrypoints)

            commands = {item.name for item in facts.commands}
            self.assertIn("bundle exec ruby app.rb -p $PORT", commands)
            self.assertIn("bundle exec rake", commands)
            self.assertIn("bundle exec rake db:migrate", commands)

            routes = {(item.framework, item.method, item.path, item.handler) for item in facts.api_routes}
            self.assertIn(("sinatra", "GET", "/", "Sinatra::Application"), routes)
            self.assertIn(("sinatra", "GET", "/lists/{id}", "Sinatra::Application"), routes)
            self.assertIn(("sinatra", "POST", "/lists", "Sinatra::Application"), routes)
            self.assertIn(("sinatra", "PUT", "/lists/{id}", "Sinatra::Application"), routes)
            self.assertIn(("sinatra", "OPTIONS", "*", "Sinatra::Application"), routes)

            show_route = next(item for item in facts.api_routes if item.method == "GET" and item.path == "/lists/{id}")
            self.assertEqual([param.name for param in show_route.parameters], ["id"])

            create_route = next(item for item in facts.api_routes if item.method == "POST" and item.path == "/lists")
            self.assertEqual("params", create_route.request_body)
            self.assertEqual("json", create_route.response_type)

            root_route = next(item for item in facts.api_routes if item.method == "GET" and item.path == "/")
            self.assertEqual("html", root_route.response_type)

            create_contract = next(item for item in facts.api_contracts if item.method == "POST" and item.path == "/lists")
            self.assertIn("422", create_contract.status_codes)
            self.assertIn("error:halt", create_contract.error_hints)


if __name__ == "__main__":
    unittest.main()
