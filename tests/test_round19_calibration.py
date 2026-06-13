from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round19CalibrationTests(unittest.TestCase):

    def test_scan_project_detects_iac_runtime_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            (root / "main.tf").write_text(
                """
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
  backend "s3" {}
}

provider "aws" {
  region = var.region
}

resource "aws_s3_bucket" "logs" {}

data "aws_caller_identity" "current" {}

module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
}

variable "region" {}

output "bucket_name" {
  value = aws_s3_bucket.logs.id
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "terraform.tfvars").write_text("region = \"us-east-1\"\n", encoding="utf-8")
            (root / "main.tftest.hcl").write_text(
                """
run "plan" {
  command = plan
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "terragrunt.hcl").write_text(
                """
include "root" {
  path = find_in_parent_folders()
}

dependency "vpc" {
  config_path = "../vpc"
}

terraform {
  source = "../modules/app"
}

inputs = {
  instance_type = "t3.micro"
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "image.pkr.hcl").write_text(
                """
source "amazon-ebs" "ubuntu" {}

build {
  sources = ["source.amazon-ebs.ubuntu"]
  provisioner "shell" {
    inline = ["echo ok"]
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            (root / "Pulumi.yaml").write_text(
                """
name: platform
runtime: nodejs
description: platform stack
config:
  aws:region:
    default: us-east-1
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "Pulumi.dev.yaml").write_text(
                """
config:
  platform:replicas: 2
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "index.ts").write_text(
                """
import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";

const bucket = new aws.s3.Bucket("logs");
if (!bucket) {
  throw new Error("missing bucket");
}
pulumi.export("bucketName", bucket.id);
""".strip()
                + "\n",
                encoding="utf-8",
            )

            tasks = root / "tasks"
            tasks.mkdir()
            (tasks / "main.yml").write_text(
                """
- name: Install nginx
  ansible.builtin.package:
    name: nginx
    state: present

- name: Include vhosts
  include_tasks: vhosts.yml
""".strip()
                + "\n",
                encoding="utf-8",
            )
            molecule = root / "molecule" / "default"
            molecule.mkdir(parents=True)
            (molecule / "molecule.yml").write_text(
                """
platforms:
  - name: instance
    image: ubuntu:22.04
provisioner:
  name: ansible
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (molecule / "converge.yml").write_text(
                """
- hosts: all
  roles:
    - role: demo.nginx
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertTrue(
                {"ansible", "packer", "pulumi", "terraform", "terragrunt"} <= frameworks
            )

            roles = {file.path: file.role for file in facts.files}
            self.assertEqual("config", roles["main.tf"])
            self.assertEqual("config", roles["terraform.tfvars"])
            self.assertEqual("test", roles["main.tftest.hcl"])
            self.assertEqual("test", roles["molecule/default/molecule.yml"])
            self.assertEqual("test", roles["molecule/default/converge.yml"])

            runtime_kinds = {fact.kind for fact in facts.runtime_configs}
            self.assertTrue(
                {
                    "ansible",
                    "packer",
                    "pulumi-program",
                    "pulumi-project",
                    "pulumi-stack",
                    "terraform-module",
                    "terraform-vars",
                    "terragrunt",
                }
                <= runtime_kinds
            )
            runtime_values = {value for fact in facts.runtime_configs for value in fact.values}
            self.assertIn("resource:aws_s3_bucket.logs", runtime_values)
            self.assertIn("module:vpc", runtime_values)
            self.assertIn("variable:region", runtime_values)
            self.assertIn("input:instance_type", runtime_values)
            self.assertIn("source:amazon-ebs.ubuntu", runtime_values)
            self.assertIn("resource:aws.s3.Bucket", runtime_values)
            self.assertIn("export:bucketName", runtime_values)
            self.assertIn("config-key:aws", runtime_values)
            self.assertIn("module:ansible.builtin.package", runtime_values)
            self.assertIn("include:vhosts.yml", runtime_values)
            self.assertNotIn("resource:Error", runtime_values)
            self.assertNotIn("module:state", runtime_values)
            self.assertNotIn("module:include_tasks", runtime_values)

            test_paths = {test.test_path for test in facts.test_maps}
            self.assertIn("main.tftest.hcl", test_paths)
            self.assertIn("molecule/default/molecule.yml", test_paths)
            self.assertIn("molecule/default/converge.yml", test_paths)


if __name__ == "__main__":
    unittest.main()
