from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round22CalibrationTests(unittest.TestCase):

    def test_scan_project_refines_ruby_php_templates_tests_and_frameworks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            (root / "composer.json").write_text(
                '{"require":{"laravel/framework":"^11.0","symfony/framework-bundle":"^7.0"}}\n',
                encoding="utf-8",
            )
            config = root / "config"
            config.mkdir()
            (config / "logging.php").write_text(
                "<?php return ['url' => env('LOG_SLACK_WEBHOOK_URL')];\n",
                encoding="utf-8",
            )
            (config / "reference.php").write_text(
                "<?php /** webhook_url?: scalar */\n",
                encoding="utf-8",
            )
            (root / "admin-footer.php").write_text(
                "<?php global $hook_suffix; do_action(\"admin_footer-{$hook_suffix}\");\n",
                encoding="utf-8",
            )
            (root / "artisan").write_text(
                "#!/usr/bin/env php\n<?php\n",
                encoding="utf-8",
            )
            (root / ".htaccess").write_text(
                "RewriteEngine On\n",
                encoding="utf-8",
            )
            (root / "Procfile").write_text("web: bin/rails s\n", encoding="utf-8")
            (root / "Procfile.tunnel").write_text("web: tunnel start\n", encoding="utf-8")
            (root / ".ember-cli").write_text('{"disableAnalytics": false}\n', encoding="utf-8")
            (root / ".git-blame-ignore-revs").write_text("abc123\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir()
            (bin_dir / "rails").write_text("#!/usr/bin/env ruby\n", encoding="utf-8")
            scripts_dir = root / "core" / "scripts"
            scripts_dir.mkdir(parents=True)
            (scripts_dir / "dr").write_text("#!/usr/bin/env php\n<?php\n", encoding="utf-8")
            deployment_dir = root / "deployment"
            deployment_dir.mkdir()
            (deployment_dir / "chatwoot").write_text("%chatwoot ALL=NOPASSWD: /bin/systemctl restart chatwoot.target\n", encoding="utf-8")
            well_known = root / ".github" / ".well-known"
            well_known.mkdir(parents=True)
            (well_known / "funding-manifest-urls").write_text("https://example.com/funding.json\n", encoding="utf-8")
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True, exist_ok=True)
            (workflows / "packages.yml").write_text("name: packages\non: push\n", encoding="utf-8")
            circleci = root / ".circleci"
            circleci.mkdir()
            (circleci / "config.yml").write_text("defaults: &defaults\n  docker: []\n", encoding="utf-8")
            swagger_tags = root / "swagger" / "tag_groups"
            swagger_tags.mkdir(parents=True)
            (swagger_tags / "application.yml").write_text("Application:\n  - Users\n", encoding="utf-8")
            drupal_config = root / "core" / "modules" / "config"
            drupal_config.mkdir(parents=True)
            (drupal_config / "config-defaults.yml").write_text(
                "config.sync:\n  path: /admin/config/development/configuration\n  defaults:\n    _controller: Drupal\\\\config\\\\Controller::overview\n",
                encoding="utf-8",
            )
            claude_skills = root / ".claude" / "skills"
            claude_skills.mkdir(parents=True)
            (claude_skills / "shadcn").write_text("../../.agents/skills/shadcn\n", encoding="utf-8")

            (root / "spree.gemspec").write_text(
                "Gem::Specification.new do |s|\n  s.add_dependency 'spree_core'\nend\n",
                encoding="utf-8",
            )
            nested_controller = root / "spree" / "api" / "app" / "controllers" / "spree" / "api"
            nested_controller.mkdir(parents=True)
            (nested_controller / "users_controller.rb").write_text(
                "class Spree::Api::UsersController < ApplicationController\nend\n",
                encoding="utf-8",
            )
            factory_dir = root / "spree" / "core" / "lib" / "spree" / "testing_support" / "factories"
            factory_dir.mkdir(parents=True)
            (factory_dir / "log_entry_factory.rb").write_text(
                "FactoryBot.define do\n  factory :log_entry do\n    source { build(:order) }\n  end\nend\n",
                encoding="utf-8",
            )

            views = root / "templates" / "admin" / "blog"
            views.mkdir(parents=True)
            (views / "_delete_form.html.twig").write_text(
                "<form method=\"post\" action=\"/admin/post/delete\"><input name=\"token\"></form>\n",
                encoding="utf-8",
            )
            (root / "app" / "views" / "home").mkdir(parents=True)
            (root / "app" / "views" / "home" / "index.html.haml").write_text(
                "%h1 Hello\n",
                encoding="utf-8",
            )
            (root / "app" / "views" / "users").mkdir(parents=True)
            (root / "app" / "views" / "users" / "show.html.erb").write_text(
                "<%= @user.name %>\n",
                encoding="utf-8",
            )
            (root / "resources" / "views").mkdir(parents=True)
            (root / "resources" / "views" / "mail.liquid").write_text(
                "Hello {{ user.name }}\n",
                encoding="utf-8",
            )

            spec_dir = root / "spec" / "models"
            spec_dir.mkdir(parents=True)
            (spec_dir / "user_spec.rb").write_text(
                "RSpec.describe User do\nend\n",
                encoding="utf-8",
            )
            (root / "lib" / "tasks").mkdir(parents=True)
            (root / "lib" / "tasks" / "cleanup.rake").write_text(
                "task :cleanup\n",
                encoding="utf-8",
            )
            (root / "fixtures").mkdir()
            (root / "fixtures" / "message.eml").write_text(
                "Subject: hello\n",
                encoding="utf-8",
            )
            (root / "fixtures" / "example.gitignore").write_text("*.log\n", encoding="utf-8")
            (root / "fixtures" / "page.xtmpl").write_text("<html></html>\n", encoding="utf-8")
            (root / "fixtures" / "logo.svgz").write_text("compressed svg placeholder\n", encoding="utf-8")
            (root / "fixtures" / "javascript-2.script").write_text("<script>alert(1)</script>\n", encoding="utf-8")
            (root / "fixtures" / "test-error.log").write_text("error\n", encoding="utf-8")
            (root / "fixtures" / "image_no_extension").write_text("fake image\n", encoding="utf-8")
            (root / "fixtures" / "libreoffice-writer.odt").write_text("odt placeholder\n", encoding="utf-8")
            (root / "fixtures" / "access_test.module~").write_text("backup\n", encoding="utf-8")

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("laravel", frameworks)
            self.assertIn("symfony", frameworks)
            self.assertIn("rails", frameworks)
            self.assertIn("spree", frameworks)
            self.assertNotIn("drupal", frameworks)
            self.assertNotIn("dbt", frameworks)
            self.assertNotIn("hydra", frameworks)
            self.assertNotIn("packer", frameworks)
            self.assertNotIn("spring", frameworks)

            files = {file.path: file for file in facts.files}
            self.assertEqual("twig", files["templates/admin/blog/_delete_form.html.twig"].language)
            self.assertEqual("frontend-page", files["templates/admin/blog/_delete_form.html.twig"].role)
            self.assertEqual("haml", files["app/views/home/index.html.haml"].language)
            self.assertEqual("frontend-page", files["app/views/home/index.html.haml"].role)
            self.assertEqual("erb", files["app/views/users/show.html.erb"].language)
            self.assertEqual("frontend-page", files["app/views/users/show.html.erb"].role)
            self.assertEqual("liquid", files["resources/views/mail.liquid"].language)
            self.assertEqual("frontend-page", files["resources/views/mail.liquid"].role)
            self.assertEqual("ruby", files["lib/tasks/cleanup.rake"].language)
            self.assertEqual("php", files["artisan"].language)
            self.assertEqual("entrypoint", files["artisan"].role)
            self.assertEqual("apache-config", files[".htaccess"].language)
            self.assertEqual("config", files[".htaccess"].role)
            self.assertEqual("config", files["Procfile"].language)
            self.assertEqual("config", files["Procfile"].role)
            self.assertEqual("config", files["Procfile.tunnel"].language)
            self.assertEqual("config", files["Procfile.tunnel"].role)
            self.assertEqual("config", files[".ember-cli"].language)
            self.assertEqual("config", files[".git-blame-ignore-revs"].language)
            self.assertEqual("ruby", files["bin/rails"].language)
            self.assertEqual("php", files["core/scripts/dr"].language)
            self.assertEqual("config", files["deployment/chatwoot"].language)
            self.assertEqual("config", files[".github/.well-known/funding-manifest-urls"].language)
            self.assertEqual("config", files[".claude/skills/shadcn"].language)
            self.assertEqual("test", files["spec/models/user_spec.rb"].role)
            self.assertEqual("email", files["fixtures/message.eml"].language)
            self.assertEqual("sample", files["fixtures/message.eml"].role)
            self.assertEqual("gitignore", files["fixtures/example.gitignore"].language)
            self.assertEqual("template", files["fixtures/page.xtmpl"].language)
            self.assertEqual("svg", files["fixtures/logo.svgz"].language)
            self.assertEqual("html", files["fixtures/javascript-2.script"].language)
            self.assertEqual("log", files["fixtures/test-error.log"].language)
            self.assertEqual("data", files["fixtures/image_no_extension"].language)
            self.assertEqual("document", files["fixtures/libreoffice-writer.odt"].language)
            self.assertEqual("backup", files["fixtures/access_test.module~"].language)
            self.assertEqual("generated", files["fixtures/access_test.module~"].role)

            engines = {page.template_engine for page in facts.pages}
            self.assertTrue({"haml", "erb", "liquid"} <= engines)
            self.assertNotIn(
                "templates/admin/blog/_delete_form.html.twig",
                {page.path for page in facts.pages},
            )
            self.assertIn(
                "/admin/post/delete",
                {form.action for form in facts.forms if form.action},
            )
            self.assertIn(
                "spec/models/user_spec.rb",
                {test.test_path for test in facts.test_maps},
            )


if __name__ == "__main__":
    unittest.main()
