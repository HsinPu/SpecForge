from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round74RailsCalibrationTests(unittest.TestCase):
    def test_rails_models_forms_commands_and_typeorm_false_positive_are_calibrated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'rails'\n", encoding="utf-8")
            (root / "Rakefile").write_text("task :default\n", encoding="utf-8")
            (root / "bin").mkdir()
            (root / "bin" / "rails").write_text("#!/usr/bin/env ruby\n", encoding="utf-8")
            (root / "config").mkdir()
            (root / "config" / "application.rb").write_text("module Demo\nclass Application < Rails::Application\nend\nend\n", encoding="utf-8")
            (root / "config" / "routes.rb").write_text("Rails.application.routes.draw do\n  resources :issues\nend\n", encoding="utf-8")

            models = root / "app" / "models"
            views = root / "app" / "views"
            assets = root / "app" / "assets" / "javascripts"
            migrations = root / "db" / "migrate"
            sample_migrations = root / "extra" / "sample_plugin" / "db" / "migrate"
            tasks = root / "lib" / "tasks"
            models.mkdir(parents=True)
            (views / "issues").mkdir(parents=True)
            (views / "account").mkdir(parents=True)
            assets.mkdir(parents=True)
            migrations.mkdir(parents=True)
            sample_migrations.mkdir(parents=True)
            tasks.mkdir(parents=True)

            (models / "issue.rb").write_text(
                """
class Issue < ApplicationRecord
  belongs_to :project
  has_many :journals, :as => :journalized
  acts_as_watchable
  validates_presence_of :subject, :project
  before_save :set_parent_id
  scope :open, -> { where(status: 'open') }
end
""".strip(),
                encoding="utf-8",
            )
            (models / "issue_relation.rb").write_text(
                """
class IssueRelation < ApplicationRecord
  belongs_to :issue_from, class_name: 'Issue'

  class Relations < Array
  end
end
""".strip(),
                encoding="utf-8",
            )
            (models / "mail_handler.rb").write_text(
                "class MailHandler < ActionMailer::Base\nend\n",
                encoding="utf-8",
            )
            (models / "query.rb").write_text(
                """
class Query < ApplicationRecord
end

class QueryError < StandardError
end
""".strip(),
                encoding="utf-8",
            )
            (models / "search_payload.rb").write_text(
                "class SearchPayload\nend\n",
                encoding="utf-8",
            )
            (models / "wiki_diff.rb").write_text(
                "class WikiDiff < Redmine::Helpers::Diff\nend\n",
                encoding="utf-8",
            )
            (views / "issues" / "new.html.erb").write_text(
                """
<%= labelled_form_for @issue, :url => issues_path, :html => {:method => :post} do |f| %>
  <%= f.text_field :subject, :required => true %>
  <%= f.select :project_id, [] %>
  <%= submit_tag l(:button_create) %>
<% end %>
""".strip(),
                encoding="utf-8",
            )
            (views / "account" / "login.html.erb").write_text(
                """
<%= form_tag(signin_path, method: :post) do %>
  <%= text_field_tag 'username', params[:username] %>
  <%= password_field_tag 'password' %>
<% end %>
""".strip(),
                encoding="utf-8",
            )
            (assets / "application.js").write_text(
                "function DataSource(name) { return { get: function() {} }; }\n",
                encoding="utf-8",
            )
            (migrations / "001_legacy.rb").write_text(
                "class LegacyUser < ActiveRecord::Base\nend\n",
                encoding="utf-8",
            )
            (sample_migrations / "001_create_sample_meetings.rb").write_text(
                "create_table :sample_meetings do |t|\n  t.string :name\nend\n",
                encoding="utf-8",
            )
            (tasks / "import.rake").write_text(
                "class ImportUser < ActiveRecord::Base\nend\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            entrypoints = {(entry.kind, entry.path, entry.command) for entry in facts.entrypoints}
            self.assertIn(("rails-app", "bin/rails", "bundle exec rails server"), entrypoints)

            commands = {command.name for command in facts.commands}
            self.assertIn("bundle exec rails server", commands)
            self.assertIn("bundle exec rails test", commands)
            self.assertIn("bundle exec rails db:migrate", commands)
            self.assertIn("bundle exec rake", commands)

            issue = next(model for model in facts.data_models if model.name == "Issue")
            model_names = {model.name for model in facts.data_models}
            self.assertEqual("active-record-model", issue.kind)
            self.assertIn("IssueRelation", model_names)
            self.assertIn("Query", model_names)
            self.assertNotIn("LegacyUser", model_names)
            self.assertNotIn("ImportUser", model_names)
            self.assertNotIn("MailHandler", model_names)
            self.assertNotIn("Relations", model_names)
            self.assertNotIn("QueryError", model_names)
            self.assertNotIn("SearchPayload", model_names)
            self.assertNotIn("WikiDiff", model_names)
            self.assertIn("project:relation", issue.fields)
            self.assertIn("journals:relation", issue.fields)
            self.assertIn("relation:project:belongs_to:Project", issue.annotations)
            self.assertIn("validation:validates_presence_of:subject", issue.annotations)
            self.assertIn("callback:before_save:set_parent_id", issue.annotations)
            self.assertIn("scope:open", issue.annotations)
            self.assertIn("macro:acts_as_watchable", issue.annotations)

            forms = {(form.source, form.method, form.action, tuple(form.fields)) for form in facts.forms}
            self.assertIn(
                (
                    "app/views/issues/new.html.erb",
                    "POST",
                    "rails-helper:issues_path",
                    ("subject", "project_id"),
                ),
                forms,
            )
            self.assertIn(
                (
                    "app/views/account/login.html.erb",
                    "POST",
                    "rails-helper:signin_path",
                    ("username", "password"),
                ),
                forms,
            )

            self.assertNotIn("typeorm-data-source", {item.kind for item in facts.data_layers})
            self.assertFalse(any("extra/sample_plugin" in item.path for item in facts.data_layers))


if __name__ == "__main__":
    unittest.main()
