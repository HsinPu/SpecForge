from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.extractors.test_map import build_test_maps
from specforge.models import ApiRouteFact, CommandFact, ComponentFact, DataModelFact, Evidence, FileFact
from specforge.scanner import scan_project


class Round84DiscourseCalibrationTests(unittest.TestCase):
    def test_rails_scope_path_options_do_not_create_path_prefix_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'rails'\n", encoding="utf-8")
            (root / "bin").mkdir()
            (root / "bin" / "rails").write_text("#!/usr/bin/env ruby\n", encoding="utf-8")
            (root / "config.ru").write_text("run Rails.application\n", encoding="utf-8")
            (root / "config").mkdir()
            (root / "config" / "routes.rb").write_text(
                """
Rails.application.routes.draw do
  scope path: nil, constraints: { format: :json } do
    get "/404-body" => "exceptions#not_found_body"

    namespace :admin do
      scope "/logs" do
        get "/watched_words/*path", to: "admin/logs#watched_words"
      end
    end
  end

  scope path: "category/:category_id" do
    get "topics" => "topics#index"
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            entrypoints = {(entry.kind, entry.path, entry.command) for entry in facts.entrypoints}
            self.assertIn(("rails-app", "bin/rails", "bundle exec rails server"), entrypoints)
            self.assertIn(("rack-app", "config.ru", "bundle exec rackup"), entrypoints)

            paths = {route.path for route in facts.api_routes}
            self.assertIn("/404-body", paths)
            self.assertIn("/admin/logs/watched_words/*path", paths)
            self.assertIn("/category/:category_id/topics", paths)
            self.assertFalse(any(path.startswith("/path") for path in paths))

    def test_test_map_avoids_generic_component_and_model_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = {
                "frontend/tests/admin-plugins-test.js": "visit('/admin/plugins'); fillIn('input', 'x');",
                "frontend/tests/admin-plugin-words-test.js": "assert('admin plugins settings panel');",
                "frontend/tests/input-helper-test.js": "assert('input admin content user topic body');",
                "frontend/tests/plugin-list-test.js": "render(<PluginList />);",
                "spec/requests/admin_plugins_spec.rb": "expect(admin.plugins).to be_present",
                "spec/requests/users_spec.rb": "User.create!; Topic.create!; get '/not-a-known-route'",
                "spec/models/plugin_setting_spec.rb": "PluginSetting.create!(name: 'enabled')",
            }
            test_files = []
            for relative, source in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source + "\n", encoding="utf-8")
                test_files.append(
                    FileFact(
                        path=relative,
                        language="javascript" if relative.endswith(".js") else "ruby",
                        role="test",
                        size_bytes=path.stat().st_size,
                        evidence=Evidence(file=relative, kind="file", line_start=1, line_end=1),
                    )
                )

            routes = [
                ApiRouteFact(
                    method="GET",
                    path="/404-body",
                    handler=None,
                    framework="rails",
                    kind="rails-route",
                    evidence=Evidence(file="config/routes.rb", kind="backend-route", line_start=1, line_end=1),
                ),
                ApiRouteFact(
                    method="GET",
                    path="/admin/plugins",
                    handler="admin/plugins#index",
                    framework="rails",
                    kind="rails-route",
                    evidence=Evidence(file="config/routes.rb", kind="backend-route", line_start=2, line_end=2),
                ),
            ]
            components = [
                ComponentFact(
                    name="InputComponent",
                    path="frontend/discourse/app/components/input.gjs",
                    framework="ember",
                    props=[],
                    hooks=[],
                    evidence=Evidence(file="frontend/discourse/app/components/input.gjs", kind="component", line_start=1, line_end=1),
                ),
                ComponentFact(
                    name="AdminComponent",
                    path="frontend/discourse/app/components/admin.gjs",
                    framework="ember",
                    props=[],
                    hooks=[],
                    evidence=Evidence(file="frontend/discourse/app/components/admin.gjs", kind="component", line_start=1, line_end=1),
                ),
                ComponentFact(
                    name="PluginList",
                    path="frontend/discourse/app/components/plugin-list.gjs",
                    framework="ember",
                    props=[],
                    hooks=[],
                    evidence=Evidence(file="frontend/discourse/app/components/plugin-list.gjs", kind="component", line_start=1, line_end=1),
                ),
            ]
            models = [
                DataModelFact(
                    name="User",
                    path="app/models/user.rb",
                    kind="active-record-model",
                    fields=[],
                    annotations=[],
                    evidence=Evidence(file="app/models/user.rb", kind="data-model", line_start=1, line_end=1),
                ),
                DataModelFact(
                    name="Topic",
                    path="app/models/topic.rb",
                    kind="active-record-model",
                    fields=[],
                    annotations=[],
                    evidence=Evidence(file="app/models/topic.rb", kind="data-model", line_start=1, line_end=1),
                ),
                DataModelFact(
                    name="PluginSetting",
                    path="app/models/plugin_setting.rb",
                    kind="active-record-model",
                    fields=[],
                    annotations=[],
                    evidence=Evidence(file="app/models/plugin_setting.rb", kind="data-model", line_start=1, line_end=1),
                ),
            ]
            commands = [
                CommandFact(
                    path="Rakefile",
                    name="bundle exec rails test",
                    description=None,
                    arguments=[],
                    options=[],
                    evidence=Evidence(file="Rakefile", kind="command", line_start=1, line_end=1),
                )
            ]

            maps = {
                item.test_path: item
                for item in build_test_maps(root, test_files, routes, components, commands, [], [], models)
            }

            self.assertEqual("api-route", maps["frontend/tests/admin-plugins-test.js"].target_kind)
            self.assertEqual("GET /admin/plugins", maps["frontend/tests/admin-plugins-test.js"].target)
            self.assertEqual("unmatched", maps["frontend/tests/admin-plugin-words-test.js"].target_kind)
            self.assertEqual("unmatched", maps["frontend/tests/input-helper-test.js"].target_kind)
            self.assertEqual("component", maps["frontend/tests/plugin-list-test.js"].target_kind)
            self.assertEqual("PluginList", maps["frontend/tests/plugin-list-test.js"].target)
            self.assertEqual("api-route", maps["spec/requests/admin_plugins_spec.rb"].target_kind)
            self.assertEqual("GET /admin/plugins", maps["spec/requests/admin_plugins_spec.rb"].target)
            self.assertEqual("unmatched", maps["spec/requests/users_spec.rb"].target_kind)
            self.assertEqual("data-model", maps["spec/models/plugin_setting_spec.rb"].target_kind)
            self.assertEqual("PluginSetting", maps["spec/models/plugin_setting_spec.rb"].target)


if __name__ == "__main__":
    unittest.main()
