from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round20CalibrationTests(unittest.TestCase):

    def test_scan_project_detects_common_ops_support_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            (root / "Makefile").write_text(
                "build:\n\tgo build ./...\n\ntest:\n\tgo test ./...\n",
                encoding="utf-8",
            )
            (root / "Vagrantfile").write_text(
                """
Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/jammy64"
  config.vm.hostname = "demo"
  config.vm.network "forwarded_port", guest: 80, host: 8080
  config.vm.provider "virtualbox" do |vb|
  end
  config.vm.provision "ansible"
end
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "hosts").write_text(
                "[web]\nweb1 ansible_host=127.0.0.1\n",
                encoding="utf-8",
            )
            (root / "ansible.cfg").write_text(
                "[defaults]\ninventory = hosts\nroles_path = roles\n",
                encoding="utf-8",
            )
            inventory_dir = root / "inventory"
            inventory_dir.mkdir()
            (inventory_dir / "digital_ocean.ini").write_text(
                "[digital_ocean]\ncache_path = /tmp/ansible\ncache_max_age = 300\n",
                encoding="utf-8",
            )
            group_vars = root / "group_vars"
            group_vars.mkdir()
            (group_vars / "all").write_text("app_port: 8080\n", encoding="utf-8")
            templates = root / "roles" / "web" / "templates"
            templates.mkdir(parents=True)
            (templates / "nginx.conf.j2").write_text(
                "listen {{ nginx_port }};\n{% if enable_tls %}ssl on;{% endif %}\n",
                encoding="utf-8",
            )
            (root / "main.tofu").write_text(
                'resource "null_resource" "demo" {}\n',
                encoding="utf-8",
            )
            (root / "terraform.tfstate").write_text(
                '{"outputs":{"secret":{"value":"do-not-read"}}}\n',
                encoding="utf-8",
            )
            (root / "Dockerfile-base").write_text(
                "FROM alpine:3.20\n",
                encoding="utf-8",
            )
            (root / "go.mod").write_text(
                "module example.com/demo\n\ngo 1.22\n",
                encoding="utf-8",
            )
            (root / "go.sum").write_text("", encoding="utf-8")
            (root / "Program.fs").write_text(
                "printfn \"hello\"\n",
                encoding="utf-8",
            )
            (root / "app.fsproj").write_text(
                "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n",
                encoding="utf-8",
            )
            (root / "app.sln").write_text(
                "Microsoft Visual Studio Solution File\n",
                encoding="utf-8",
            )
            (root / ".editorconfig").write_text(
                "root = true\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            files = {file.path: file for file in facts.files}
            self.assertEqual("makefile", files["Makefile"].language)
            self.assertEqual("config", files["Makefile"].role)
            self.assertEqual("vagrant", files["Vagrantfile"].language)
            self.assertEqual("config", files["Vagrantfile"].role)
            self.assertEqual("ansible-inventory", files["hosts"].language)
            self.assertEqual("config", files["hosts"].role)
            self.assertEqual("ini", files["ansible.cfg"].language)
            self.assertEqual("config", files["ansible.cfg"].role)
            self.assertEqual("ansible-inventory", files["inventory/digital_ocean.ini"].language)
            self.assertEqual("config", files["inventory/digital_ocean.ini"].role)
            self.assertEqual("yaml", files["group_vars/all"].language)
            self.assertEqual("config", files["group_vars/all"].role)
            self.assertEqual("jinja", files["roles/web/templates/nginx.conf.j2"].language)
            self.assertEqual("config", files["roles/web/templates/nginx.conf.j2"].role)
            self.assertEqual("hcl", files["main.tofu"].language)
            self.assertEqual("config", files["main.tofu"].role)
            self.assertEqual("terraform-state", files["terraform.tfstate"].language)
            self.assertEqual("generated", files["terraform.tfstate"].role)
            self.assertEqual("dockerfile", files["Dockerfile-base"].language)
            self.assertEqual("config", files["Dockerfile-base"].role)
            self.assertEqual("gomod", files["go.mod"].language)
            self.assertEqual("gosum", files["go.sum"].language)
            self.assertEqual("fsharp", files["Program.fs"].language)
            self.assertEqual("msbuild", files["app.fsproj"].language)
            self.assertEqual("solution", files["app.sln"].language)
            self.assertEqual("config", files[".editorconfig"].language)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("opentofu", frameworks)

            runtime_kinds = {fact.kind for fact in facts.runtime_configs}
            self.assertTrue(
                {
                    "ansible-inventory",
                    "ansible-inventory-config",
                    "ansible-template",
                    "ansible-vars",
                    "ansible-config",
                    "dockerfile",
                    "makefile",
                    "opentofu-module",
                    "vagrantfile",
                }
                <= runtime_kinds
            )
            runtime_values = {value for fact in facts.runtime_configs for value in fact.values}
            self.assertIn("target:build", runtime_values)
            self.assertIn("box:ubuntu/jammy64", runtime_values)
            self.assertIn("provider:virtualbox", runtime_values)
            self.assertIn("provisioner:ansible", runtime_values)
            self.assertIn("group:web", runtime_values)
            self.assertIn("host:web1", runtime_values)
            self.assertIn("config:ansible.cfg", runtime_values)
            self.assertIn("config-key:roles_path", runtime_values)
            self.assertIn("inventory-config", runtime_values)
            self.assertIn("config-key:cache_path", runtime_values)
            self.assertNotIn("host:roles_path", runtime_values)
            self.assertNotIn("host:cache_path", runtime_values)
            self.assertIn("var:app_port", runtime_values)
            self.assertIn("template-var:nginx_port", runtime_values)
            self.assertIn("template-tag:if", runtime_values)
            self.assertIn("resource:null_resource.demo", runtime_values)
            self.assertNotIn("value:do-not-read", runtime_values)
            self.assertNotIn(
                "terraform.tfstate",
                {fact.path for fact in facts.runtime_configs},
            )


if __name__ == "__main__":
    unittest.main()
