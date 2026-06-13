from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round21CalibrationTests(unittest.TestCase):

    def test_scan_project_classifies_residual_ops_and_template_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            files = {
                ".dockerignore": "node_modules\n",
                ".gitmodules": "[submodule \"demo\"]\n\tpath = demo\n",
                "web.config": "<configuration />\n",
                "main.cue": "package main\n",
                "view.jbuilder": "json.name @user.name\n",
                "page.astro": "---\n---\n<div />\n",
                "recording.cast": "{\"version\": 2}\n",
                "cat.mp4": "",
                "ffmpeg.tar.xz": "",
                "setup.mysql": "CREATE DATABASE demo;\n",
                "module.psd1": "@{}\n",
                "Gemfile": "source 'https://rubygems.org'\n",
                "Rakefile": "task :default\n",
                ".ruby-version": "3.3.0\n",
                ".keep": "",
                "credentials.yml.enc": "encrypted\n",
                "config.ru": "run Rails.application\n",
                "settings.json5": "{name: 'demo'}\n",
                "todo.coffee": "alert 'ok'\n",
                "env": "RAILS_ENV=development\n",
                "start": "#!/bin/sh\nbundle exec rails s\n",
                "hosts.example": "[web]\nweb1\n",
                "inventory.example": "[db]\ndb1\n",
                ".tfswitchrc": "1.9.0\n",
                ".opentofu-version": "1.8.0\n",
                "RPM-GPG-KEY-EPEL-7": "key\n",
                "secret": "do-not-read\n",
                "METADATA": "name: demo\n",
            }
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            template_dir = root / "roles" / "firewall" / "templates"
            template_dir.mkdir(parents=True)
            (template_dir / "iptables-save").write_text("*filter\nCOMMIT\n", encoding="utf-8")

            test_dir = root / "tests" / "workflow"
            test_dir.mkdir(parents=True)
            (test_dir / "backend_config").write_text('bucket = "demo"\n', encoding="utf-8")
            (test_dir / "nope").write_text("", encoding="utf-8")

            facts = scan_project(root)
            files_by_path = {file.path: file for file in facts.files}

            expected = {
                ".dockerignore": ("dockerignore", "config"),
                ".gitmodules": ("gitmodules", "config"),
                "web.config": ("xml", "config"),
                "main.cue": ("cue", "source"),
                "view.jbuilder": ("jbuilder", "source"),
                "page.astro": ("astro", "source"),
                "recording.cast": ("asciinema", "source"),
                "cat.mp4": ("video", "asset"),
                "ffmpeg.tar.xz": ("archive", "asset"),
                "setup.mysql": ("sql", "source"),
                "module.psd1": ("powershell", "source"),
                "Gemfile": ("ruby-manifest", "config"),
                "Rakefile": ("ruby", "config"),
                ".ruby-version": ("config", "config"),
                ".keep": ("marker", "generated"),
                "credentials.yml.enc": ("encrypted", "generated"),
                "config.ru": ("ruby", "source"),
                "settings.json5": ("json5", "source"),
                "todo.coffee": ("coffeescript", "source"),
                "env": ("config", "config"),
                "start": ("shell", "source"),
                "hosts.example": ("ansible-inventory", "config"),
                "inventory.example": ("ansible-inventory", "config"),
                ".tfswitchrc": ("config", "config"),
                ".opentofu-version": ("config", "config"),
                "RPM-GPG-KEY-EPEL-7": ("certificate", "asset"),
                "secret": ("secret", "generated"),
                "METADATA": ("config", "config"),
                "roles/firewall/templates/iptables-save": ("shell", "config"),
                "tests/workflow/backend_config": ("config", "test"),
                "tests/workflow/nope": ("text", "test"),
            }
            for path, (language, role) in expected.items():
                self.assertEqual(language, files_by_path[path].language, path)
                self.assertEqual(role, files_by_path[path].role, path)

            runtime_paths = {fact.path for fact in facts.runtime_configs}
            self.assertNotIn("secret", runtime_paths)


if __name__ == "__main__":
    unittest.main()
