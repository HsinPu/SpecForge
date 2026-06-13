from __future__ import annotations

import json
import re
from pathlib import Path

from specforge.models import Evidence, FileFact, RuntimeConfigFact


def extract_runtime_config_facts(root: Path, files: list[FileFact]) -> list[RuntimeConfigFact]:
    facts: list[RuntimeConfigFact] = []
    for file_fact in files:
        normalized = file_fact.path.replace("\\", "/")
        name = Path(normalized).name
        lower = normalized.lower()
        if file_fact.role in {"test", "sample", "generated"}:
            continue
        path = root / file_fact.path
        if not path.exists():
            continue
        source = _read(path)

        if name in {".env.example", ".env.sample", ".env.template"}:
            facts.append(_env_fact(file_fact, source))
        elif name == "Dockerfile" or name.startswith("Dockerfile."):
            facts.append(_dockerfile_fact(file_fact, source))
        elif name.startswith("Dockerfile-"):
            facts.append(_dockerfile_fact(file_fact, source))
        elif name in {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}:
            facts.append(_compose_fact(file_fact, source))
        elif normalized.startswith(".github/workflows/") and name.endswith((".yml", ".yaml")):
            facts.append(_github_actions_fact(file_fact, source))
        elif name.lower() in {"makefile", "gnumakefile"}:
            facts.append(_makefile_fact(file_fact, source))
        elif name.lower() == "vagrantfile":
            facts.append(_vagrantfile_fact(file_fact, source))
        elif normalized.lower().endswith((".tf", ".tfvars", ".tfvars.json", ".tofu")) or name == ".terraform.lock.hcl":
            facts.append(_terraform_fact(file_fact, source))
        elif lower.endswith(("wrangler.toml", "wrangler.json", "wrangler.jsonc")):
            facts.append(_wrangler_config_fact(file_fact, source))
        elif lower.endswith(("deno.json", "deno.jsonc")):
            facts.append(_deno_config_fact(file_fact, source))
        elif name == "terragrunt.hcl":
            facts.append(_terragrunt_fact(file_fact, source))
        elif normalized.lower().endswith(".pkr.hcl") or name == "Packerfile":
            facts.append(_packer_fact(file_fact, source))
        elif name in {"Pulumi.yaml", "Pulumi.yml"} or re.fullmatch(r"Pulumi\.[^.]+\.(?:ya?ml)", name) is not None:
            facts.append(_pulumi_project_fact(file_fact, source))
        elif name in {"dvc.yaml", "dvc.lock"}:
            facts.append(_dvc_pipeline_fact(file_fact, source))
        elif name == "MLproject":
            facts.append(_mlproject_fact(file_fact, source))
        elif name in {"params.yaml", "params.yml"}:
            facts.append(_ml_params_fact(file_fact, source))
        elif lower == ".streamlit/config.toml":
            facts.append(_streamlit_config_fact(file_fact, source))
        elif name.endswith((".yaml", ".yml")) and _looks_like_hydra_config(normalized, source):
            facts.append(_hydra_config_fact(file_fact, source))
        elif name == "Chart.yaml":
            facts.append(_helm_chart_fact(file_fact, source))
        elif name.lower() in {"openapi.yaml", "openapi.yml", "swagger.yaml", "swagger.yml", "openapi.json", "swagger.json"} or _looks_like_openapi_spec(source):
            facts.append(_openapi_spec_fact(file_fact, source))
        elif name.endswith((".yml", ".yaml")) and _looks_like_kubernetes_manifest(source):
            facts.append(_kubernetes_manifest_fact(file_fact, source))
        elif name.endswith((".yml", ".yaml")) and _looks_like_ansible_file(normalized, source):
            facts.append(_ansible_fact(file_fact, source))
        elif normalized.lower().endswith(".j2") and _looks_like_ansible_template_file(normalized, source):
            facts.append(_ansible_template_fact(file_fact, source))
        elif name.lower() == "ansible.cfg":
            facts.append(_ansible_config_fact(file_fact, source))
        elif _looks_like_ansible_inventory_or_vars_file(normalized, source):
            facts.append(_ansible_inventory_fact(file_fact, source))
        elif _looks_like_ktor_config(name, source):
            facts.append(_ktor_config_fact(file_fact, source))
        elif _looks_like_spring_config_path(normalized):
            facts.append(_spring_config_fact(file_fact, source))
        elif name in {"dbt_project.yml", "dbt_project.yaml"}:
            facts.append(_dbt_project_config_fact(file_fact, source))
        elif name in {"prefect.yaml"}:
            facts.append(_prefect_config_fact(file_fact, source))
        elif name in {"dagster.yaml", "workspace.yaml", "workspace.yml"}:
            facts.append(_dagster_config_fact(file_fact, source))
        elif name in {"great_expectations.yml", "great_expectations.yaml"} or normalized.startswith(("great_expectations/", "gx/")) and name.endswith((".yml", ".yaml", ".json")):
            facts.append(_great_expectations_config_fact(file_fact, source))
        elif name in {"catalog.yml", "catalog.yaml"} and ("/conf/" in f"/{normalized}" or normalized.startswith("conf/")):
            facts.append(_kedro_catalog_fact(file_fact, source))
        elif _looks_like_rails_config(normalized):
            facts.append(_rails_config_fact(file_fact, source))
        elif _looks_like_phoenix_config(normalized):
            facts.append(_phoenix_config_fact(file_fact, source))
        elif _looks_like_aspnet_appsettings(normalized):
            appsettings_fact = _aspnet_appsettings_fact(file_fact, source)
            if appsettings_fact:
                facts.append(appsettings_fact)
        elif _looks_like_node_runtime_json_config(normalized):
            node_json_fact = _node_runtime_json_config_fact(file_fact, source)
            if node_json_fact:
                facts.append(node_json_fact)
        elif name in {"vite.config.js", "vite.config.ts", "vite.config.mjs"}:
            facts.append(_js_config_fact(file_fact, source, "vite-config"))
        elif name in {"next.config.js", "next.config.ts", "next.config.mjs"}:
            facts.append(_js_config_fact(file_fact, source, "next-config"))
        elif name == "tauri.conf.json":
            facts.append(_tauri_config_fact(file_fact, source))
        elif name == "package.json":
            package_fact = _package_scripts_fact(file_fact, source)
            if package_fact:
                facts.append(package_fact)
        elif file_fact.language in {"javascript", "typescript"} and _looks_like_electron_runtime_source(source):
            facts.append(_electron_runtime_fact(file_fact, source))
        elif normalized.startswith("src-tauri/") and file_fact.language == "rust" and _looks_like_tauri_runtime_source(source):
            facts.append(_tauri_runtime_fact(file_fact, source))
        elif file_fact.language == "python" and _looks_like_airflow_source(source):
            facts.append(_airflow_dag_fact(file_fact, source))
        elif file_fact.language == "python" and _looks_like_prefect_source(source):
            facts.append(_prefect_source_fact(file_fact, source))
        elif file_fact.language == "python" and _looks_like_dagster_source(source):
            facts.append(_dagster_source_fact(file_fact, source))
        elif file_fact.language == "python" and _looks_like_kedro_source(source):
            facts.append(_kedro_source_fact(file_fact, source))
        elif file_fact.language == "notebook":
            facts.append(_notebook_config_fact(file_fact, source))
        elif file_fact.language == "python" and _looks_like_ml_runtime_source(source):
            facts.append(_ml_source_runtime_fact(file_fact, source))
        elif file_fact.language in {"python", "typescript", "javascript", "go", "csharp", "java"} and _looks_like_pulumi_source(source):
            facts.append(_pulumi_source_fact(file_fact, source))
        elif file_fact.language == "python" and _looks_like_celery_source(source):
            facts.append(_celery_fact(file_fact, source))

        security_fact = _security_source_fact(file_fact, source)
        if security_fact:
            facts.append(security_fact)

    return _dedupe_facts(facts)


def _env_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    keys = []
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            keys.append(f"env-key:{key}")
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="env-example",
        name=Path(file_fact.path).name,
        values=_dedupe(keys),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _dockerfile_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = []
    values.extend(f"base:{item}" for item in re.findall(r"^\s*FROM\s+([^\s]+)", source, re.MULTILINE | re.IGNORECASE))
    values.extend(f"port:{item}" for item in re.findall(r"^\s*EXPOSE\s+(.+)$", source, re.MULTILINE | re.IGNORECASE))
    values.extend(f"cmd:{item.strip()}" for item in re.findall(r"^\s*CMD\s+(.+)$", source, re.MULTILINE | re.IGNORECASE))
    values.extend(f"entrypoint:{item.strip()}" for item in re.findall(r"^\s*ENTRYPOINT\s+(.+)$", source, re.MULTILINE | re.IGNORECASE))
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="dockerfile",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _compose_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = []
    in_services = False
    for line in source.splitlines():
        if re.match(r"^services:\s*$", line):
            in_services = True
            continue
        if in_services and line and not line.startswith((" ", "\t")):
            in_services = False
        if in_services:
            service_match = re.match(r"^\s{2}([A-Za-z0-9_.-]+):\s*$", line)
            if service_match:
                values.append(f"service:{service_match.group(1)}")
            port_match = re.search(r"['\"]?(\d{2,5}:\d{2,5})['\"]?", line)
            if port_match:
                values.append(f"port:{port_match.group(1)}")
            image_match = re.match(r"^\s+image:\s*([^\s#]+)", line)
            if image_match:
                values.append(f"image:{image_match.group(1)}")
            command_match = re.match(r"^\s+command:\s*(.+)$", line)
            if command_match:
                values.append(f"command:{command_match.group(1).strip()}")
            env_match = re.match(r"^\s+-\s*([A-Za-z_][A-Za-z0-9_]*)=", line)
            if env_match:
                values.append(f"env-key:{env_match.group(1)}")
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="docker-compose",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _github_actions_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = []
    values.extend(f"job:{name}" for name in re.findall(r"^\s{2}([A-Za-z0-9_-]+):\s*$", source, re.MULTILINE))
    values.extend(f"run:{command.strip()}" for command in re.findall(r"^\s*run:\s*(.+)$", source, re.MULTILINE))
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="github-actions",
        name=Path(file_fact.path).stem,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _makefile_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:make"]
    values.extend(
        f"target:{target}"
        for target in re.findall(r"^([A-Za-z0-9_.%/-]+)\s*:(?!=)", source, re.MULTILINE)[:80]
        if not target.startswith(".")
    )
    values.extend(f"include:{item.strip()}" for item in re.findall(r"^\s*include\s+(.+)$", source, re.MULTILINE)[:20])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="makefile",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=_first_runtime_line(source), line_end=_first_runtime_line(source)),
    )


def _vagrantfile_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:vagrant"]
    values.extend(f"box:{item}" for item in re.findall(r'config\.vm\.box\s*=\s*["\']([^"\']+)["\']', source)[:20])
    values.extend(f"hostname:{item}" for item in re.findall(r'config\.vm\.hostname\s*=\s*["\']([^"\']+)["\']', source)[:20])
    values.extend(f"provider:{item}" for item in re.findall(r'config\.vm\.provider\s+["\']([^"\']+)["\']', source)[:20])
    values.extend(f"provisioner:{item}" for item in re.findall(r'config\.vm\.provision\s+["\']([^"\']+)["\']', source)[:20])
    values.extend(f"forwarded-port:{guest}->{host}" for guest, host in re.findall(r"guest:\s*(\d+),\s*host:\s*(\d+)", source)[:20])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="vagrantfile",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=_first_runtime_line(source), line_end=_first_runtime_line(source)),
    )


def _terraform_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    normalized = file_fact.path.replace("\\", "/").lower()
    is_opentofu = (
        normalized.endswith(".tofu")
        or "opentofu" in source.lower()
        or re.search(r"\btofu\b", source.lower()) is not None
    )
    if normalized.endswith(".tfvars") or normalized.endswith(".tfvars.json"):
        kind = "terraform-vars"
        values = ["runtime:terraform"]
        values.extend(f"var:{name}" for name in re.findall(r"^\s*([A-Za-z_][\w-]*)\s*=", source, re.MULTILINE)[:80])
    elif Path(normalized).name == ".terraform.lock.hcl":
        kind = "terraform-lock"
        values = ["runtime:terraform"]
        values.extend(f"provider:{name}" for name in re.findall(r'^\s*provider\s+"([^"]+)"\s*{', source, re.MULTILINE)[:80])
    else:
        if is_opentofu:
            kind = "opentofu-module" if _looks_like_terraform_module_file(source) else "opentofu"
            values = ["runtime:opentofu", "runtime:terraform"]
        else:
            kind = "terraform-module" if _looks_like_terraform_module_file(source) else "terraform"
            values = ["runtime:terraform"]
        values.extend(f"provider:{name}" for name in re.findall(r'^\s*provider\s+"([^"]+)"\s*{', source, re.MULTILINE)[:80])
        values.extend(f"required-provider:{name}" for name in re.findall(r"^\s*([A-Za-z_][\w-]*)\s*=\s*{", _hcl_block_body(source, "required_providers"), re.MULTILINE)[:80])
        values.extend(f"backend:{name}" for name in re.findall(r'^\s*backend\s+"([^"]+)"\s*{', source, re.MULTILINE)[:20])
        values.extend(f"resource:{resource_type}.{name}" for resource_type, name in re.findall(r'^\s*resource\s+"([^"]+)"\s+"([^"]+)"\s*{', source, re.MULTILINE)[:100])
        values.extend(f"data:{data_type}.{name}" for data_type, name in re.findall(r'^\s*data\s+"([^"]+)"\s+"([^"]+)"\s*{', source, re.MULTILINE)[:80])
        values.extend(f"module:{name}" for name in re.findall(r'^\s*module\s+"([^"]+)"\s*{', source, re.MULTILINE)[:80])
        values.extend(f"variable:{name}" for name in re.findall(r'^\s*variable\s+"([^"]+)"\s*{', source, re.MULTILINE)[:80])
        values.extend(f"output:{name}" for name in re.findall(r'^\s*output\s+"([^"]+)"\s*{', source, re.MULTILINE)[:80])
        required_version = _first_match(source, r"^\s*required_version\s*=\s*([^\n#]+)")
        if required_version:
            values.append(f"required-version:{required_version.strip().strip('\"')}")
    return RuntimeConfigFact(
        path=file_fact.path,
        kind=kind,
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=_first_runtime_line(source), line_end=_first_runtime_line(source)),
    )


def _wrangler_config_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:cloudflare-workers"]
    parsed = _jsonc_object(source) if file_fact.path.lower().endswith((".json", ".jsonc")) else {}
    if parsed:
        values.extend(_json_scalar_values(parsed, ("name", "main", "compatibility_date")))
        dev = parsed.get("dev") if isinstance(parsed.get("dev"), dict) else {}
        port = dev.get("port")
        if isinstance(port, (int, str)):
            values.append(f"port:{port}")
        values.extend(_cloudflare_binding_values(parsed))
    else:
        values.extend(_toml_scalar_values(source, ("name", "main", "compatibility_date")))
        values.extend(f"port:{item}" for item in re.findall(r"^\s*port\s*=\s*['\"]?(\d{2,5})['\"]?", source, re.MULTILINE))
        values.extend(f"binding:{item}" for item in re.findall(r"^\s*binding\s*=\s*['\"]([^'\"]+)['\"]", source, re.MULTILINE))
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="wrangler-config",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _deno_config_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:deno"]
    data = _jsonc_object(source)
    tasks = data.get("tasks") if isinstance(data.get("tasks"), dict) else {}
    values.extend(f"task:{name}" for name in tasks)
    imports = data.get("imports") if isinstance(data.get("imports"), dict) else {}
    values.extend(f"import:{name}" for name in imports)
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="deno-config",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _terragrunt_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:terragrunt", "runtime:terraform"]
    values.extend(f"include:{name or 'root'}" for name in re.findall(r'^\s*include(?:\s+"([^"]+)")?\s*{', source, re.MULTILINE)[:30])
    values.extend(f"dependency:{name}" for name in re.findall(r'^\s*dependency\s+"([^"]+)"\s*{', source, re.MULTILINE)[:50])
    values.extend(f"dependency-path:{path}" for path in re.findall(r'config_path\s*=\s*"([^"]+)"', source)[:50])
    terraform_block = _hcl_block_body(source, "terraform")
    values.extend(f"source:{item}" for item in re.findall(r'^\s*source\s*=\s*"([^"]+)"', terraform_block, re.MULTILINE)[:20])
    if "inputs" in source:
        values.append("section:inputs")
    values.extend(f"input:{name}" for name in re.findall(r"^\s{2,}([A-Za-z_][\w-]*)\s*=", _hcl_assignment_block(source, "inputs"), re.MULTILINE)[:60])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="terragrunt",
        name=Path(file_fact.path).parent.name or "terragrunt",
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=_first_runtime_line(source), line_end=_first_runtime_line(source)),
    )


def _packer_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:packer"]
    values.extend(f"source:{kind}.{name}" for kind, name in re.findall(r'^\s*source\s+"([^"]+)"\s+"([^"]+)"\s*{', source, re.MULTILINE)[:60])
    values.extend(f"variable:{name}" for name in re.findall(r'^\s*variable\s+"([^"]+)"\s*{', source, re.MULTILINE)[:60])
    values.extend(f"build-source:{name}" for name in re.findall(r'^\s*sources\s*=\s*\[([^\]]+)\]', source, re.MULTILINE)[:20])
    values.extend(f"provisioner:{name}" for name in re.findall(r'^\s*provisioner\s+"([^"]+)"\s*{', source, re.MULTILINE)[:60])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="packer",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=_first_runtime_line(source), line_end=_first_runtime_line(source)),
    )


def _pulumi_project_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    name = Path(file_fact.path).name
    is_stack = re.fullmatch(r"Pulumi\.[^.]+\.(?:ya?ml)", name) is not None
    values = ["runtime:pulumi"]
    values.extend(_yaml_scalar_values(source, ("name", "runtime", "description", "main", "template")))
    config = _yaml_section(source, "config")
    values.extend(f"config-key:{key.strip()}" for key in re.findall(r"^\s{2}([^:\n#]+):", config, re.MULTILINE)[:80])
    values.extend(f"plugin:{plugin}" for plugin in re.findall(r"^\s*-\s+name:\s*([^#\n]+)", _yaml_section(source, "plugins"), re.MULTILINE)[:40])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="pulumi-stack" if is_stack else "pulumi-project",
        name=_yaml_scalar(source, "name") or Path(file_fact.path).parent.name or "pulumi",
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _pulumi_source_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:pulumi"]
    values.extend(f"provider:{name}" for name in _pulumi_provider_names(source)[:80])
    values.extend(f"resource:{name}" for name in _pulumi_resource_names(source)[:100])
    values.extend(f"export:{name}" for name in re.findall(r"\bpulumi\.export\(\s*['\"]([^'\"]+)['\"]", source)[:60])
    values.extend(f"config:{name}" for name in re.findall(r"\b(?:pulumi\.)?Config\(\s*['\"]?([^'\")]+)?", source)[:40] if name)
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="pulumi-program",
        name=Path(file_fact.path).stem,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=_first_runtime_line(source), line_end=_first_runtime_line(source)),
    )


def _ansible_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    normalized = file_fact.path.replace("\\", "/").lower()
    parent_name = Path(normalized).parent.name
    values = ["runtime:ansible"]
    if "/molecule/" in f"/{normalized}":
        values.append("test:molecule")
    if "/roles/" in f"/{normalized}" or parent_name in {"tasks", "handlers", "defaults", "vars", "meta"}:
        values.append(f"role-section:{parent_name}")
    values.extend(f"play:{name}" for name in _ansible_play_names(source)[:40])
    values.extend(f"hosts:{hosts.strip()}" for hosts in re.findall(r"^\s*-?\s*hosts:\s*([^#\n]+)", source, re.MULTILINE)[:40])
    roles_section = _yaml_section(source, "roles")
    values.extend(f"role:{role}" for role in re.findall(r"^\s*-\s+([^#\n{]+)", roles_section, re.MULTILINE)[:60])
    if parent_name == "handlers":
        values.extend(f"handler:{handler}" for handler in _ansible_task_names(source)[:80])
    elif _looks_like_ansible_task_file(normalized, source):
        values.extend(f"task:{task}" for task in _ansible_task_names(source)[:80])
    if _looks_like_ansible_task_file(normalized, source):
        values.extend(f"module:{module}" for module in _ansible_module_names(source)[:80])
    values.extend(
        f"include:{name.strip()}"
        for name in re.findall(
            r"^\s*-?\s*(?:include_tasks|import_tasks|include_role|import_role):\s*([^#\n]+)",
            source,
            re.MULTILINE,
        )[:60]
    )
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="ansible-molecule" if "/molecule/" in f"/{normalized}" else "ansible",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _ansible_template_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:ansible", "template:jinja2"]
    values.extend(
        f"template-var:{name.split('.')[0]}"
        for name in re.findall(r"{{\s*([A-Za-z_][\w.]*)", source)[:80]
    )
    values.extend(f"template-tag:{tag}" for tag in re.findall(r"{%\s*([A-Za-z_][\w]*)", source)[:40])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="ansible-template",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=_first_runtime_line(source), line_end=_first_runtime_line(source)),
    )


def _ansible_inventory_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    normalized = file_fact.path.replace("\\", "/").lower()
    is_vars_file = "/group_vars/" in f"/{normalized}" or "/host_vars/" in f"/{normalized}"
    values = ["runtime:ansible"]
    if is_vars_file:
        values.append("inventory-vars")
        values.extend(f"var:{name}" for name in re.findall(r"^\s*([A-Za-z_][\w.-]+):\s*", source, re.MULTILINE)[:80])
        kind = "ansible-vars"
    elif _looks_like_ansible_ini_config(normalized, source):
        values.append("inventory-config")
        values.extend(f"section:{name}" for name in _ini_sections(source)[:80])
        values.extend(f"config-key:{name}" for name in _ini_keys(source)[:80])
        kind = "ansible-inventory-config"
    else:
        values.append("inventory:hosts")
        values.extend(f"group:{name}" for name in re.findall(r"^\s*\[([A-Za-z0-9_.:-]+)\]\s*$", source, re.MULTILINE)[:80])
        values.extend(f"host:{name}" for name in _ansible_inventory_hosts(source)[:80])
        kind = "ansible-inventory"
    return RuntimeConfigFact(
        path=file_fact.path,
        kind=kind,
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _ansible_config_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:ansible", "config:ansible.cfg"]
    values.extend(f"section:{name}" for name in _ini_sections(source)[:80])
    values.extend(f"config-key:{name}" for name in _ini_keys(source)[:80])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="ansible-config",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _dvc_pipeline_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:dvc"]
    stages = _yaml_section(source, "stages")
    values.extend(f"stage:{name}" for name in re.findall(r"^\s{2}([A-Za-z_][\w.-]+):\s*$", stages, re.MULTILINE)[:50])
    values.extend(f"cmd:{item.strip()}" for item in re.findall(r"^\s*cmd:\s*(.+)$", source, re.MULTILINE)[:30])
    for key, prefix in [("deps", "deps"), ("outs", "outs"), ("metrics", "metrics"), ("params", "params")]:
        section = _yaml_section(source, key)
        if section:
            values.append(f"section:{prefix}")
        values.extend(f"{prefix}:{item}" for item in re.findall(r"^\s*-\s+([^#\n]+)", section, re.MULTILINE)[:40])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="dvc-pipeline",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _mlproject_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:mlflow"]
    values.extend(_yaml_scalar_values(source, ("name", "python_env", "conda_env", "docker_env")))
    entry_points = _yaml_section(source, "entry_points")
    values.extend(f"entry-point:{name}" for name in re.findall(r"^\s{2}([A-Za-z_][\w.-]+):\s*$", entry_points, re.MULTILINE)[:40])
    values.extend(f"command:{command.strip()}" for command in re.findall(r"^\s*command:\s*(.+)$", source, re.MULTILINE)[:20])
    values.extend(f"param:{name}" for name in re.findall(r"^\s{6}([A-Za-z_][\w.-]+):\s*$", entry_points, re.MULTILINE)[:40])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="mlproject",
        name=_yaml_scalar(source, "name") or "MLproject",
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _ml_params_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:ml-params"]
    values.extend(f"param:{name}" for name in re.findall(r"^([A-Za-z_][\w.-]+):\s*", source, re.MULTILINE)[:80])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="ml-params",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _hydra_config_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:hydra"]
    defaults = _yaml_section(source, "defaults")
    values.extend(f"default:{item.strip()}" for item in re.findall(r"^\s*-\s+([^#\n]+)", defaults, re.MULTILINE)[:40])
    values.extend(f"target:{item.strip()}" for item in re.findall(r"^\s*_target_:\s*([^#\n]+)", source, re.MULTILINE)[:30])
    values.extend(f"config-key:{item}" for item in re.findall(r"^([A-Za-z_][\w.-]+):\s*", source, re.MULTILINE)[:40])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="hydra-config",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _streamlit_config_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:streamlit"]
    values.extend(f"section:{item}" for item in re.findall(r"^\s*\[([A-Za-z_][\w.-]*)\]\s*$", source, re.MULTILINE)[:30])
    values.extend(f"config-key:{item}" for item in re.findall(r"^\s*([A-Za-z_][\w.-]+)\s*=", source, re.MULTILINE)[:50])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="streamlit-config",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _spring_config_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = []
    values.extend(f"port:{item}" for item in re.findall(r"(?:server\.port\s*=\s*|port:\s*)(\d{2,5})", source))
    values.extend(f"profile:{item}" for item in re.findall(r"spring\.profiles\.active\s*=\s*([A-Za-z0-9_,.-]+)", source))
    values.extend(f"config-key:{item}" for item in re.findall(r"^([A-Za-z][A-Za-z0-9_.-]+)\s*=", source, re.MULTILINE)[:50])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="spring-config",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _ktor_config_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = []
    values.extend(f"port:{item}" for item in re.findall(r"\bport\s*[=:]\s*(\d{2,5})", source))
    values.extend(f"host:{item}" for item in re.findall(r"\bhost\s*[=:]\s*['\"]?([A-Za-z0-9_.:-]+)", source))
    for modules in re.findall(r"\bmodules\s*[=:]\s*\[([^\]]+)\]", source, re.DOTALL):
        values.extend(f"module:{item}" for item in re.findall(r"[A-Za-z_][\w.]*", modules))
    values.extend(f"module:{item}" for item in re.findall(r"\bmodule\s*[=:]\s*([A-Za-z_][\w.]*)", source))
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="ktor-config",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _looks_like_rails_config(path: str) -> bool:
    lower = path.lower()
    return (
        lower in {
            "config/application.rb",
            "config/boot.rb",
            "config/cable.yml",
            "config/database.yml",
            "config/puma.rb",
            "config/secrets.yml",
            "config/storage.yml",
        }
        or lower.startswith("config/environments/") and lower.endswith(".rb")
    )


def _looks_like_phoenix_config(path: str) -> bool:
    lower = path.lower()
    return lower.startswith("config/") and lower.endswith((".exs", ".exs.example"))


def _rails_config_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = []
    values.extend(f"env-key:{item}" for item in _env_keys(source))
    values.extend(f"profile:{item}" for item in re.findall(r"^([A-Za-z_][\w-]*):\s*$", source, re.MULTILINE))
    values.extend(f"config-key:{item}" for item in re.findall(r"^\s{2,}([A-Za-z_][\w-]*):", source, re.MULTILINE))
    values.extend(f"config-key:{item}" for item in re.findall(r"\bconfig\.([A-Za-z_][\w.]*)\s*=", source))
    normalized = file_fact.path.replace("\\", "/").lower()
    if "/environments/" in f"/{normalized}":
        values.append(f"environment:{Path(file_fact.path).stem}")
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="rails-config",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=_first_runtime_line(source), line_end=_first_runtime_line(source)),
    )


def _phoenix_config_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = []
    values.extend(f"env-key:{item}" for item in _env_keys(source))
    values.extend(
        f"config-target:{app}{'.' + target if target else ''}"
        for app, target in re.findall(r"^\s*config\s+:([A-Za-z_]\w*)(?:,\s*([A-Za-z_][\w.]*))?", source, re.MULTILINE)
    )
    values.extend(f"config-key:{item}" for item in re.findall(r"^\s*([A-Za-z_]\w*):\s*", source, re.MULTILINE))
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="phoenix-config",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=_first_runtime_line(source), line_end=_first_runtime_line(source)),
    )


def _js_config_fact(file_fact: FileFact, source: str, kind: str) -> RuntimeConfigFact:
    values = []
    values.extend(f"env-prefix:{item}" for item in re.findall(r"envPrefix\s*:\s*['\"]([^'\"]+)['\"]", source))
    values.extend(f"plugin:{item}" for item in re.findall(r"\b([A-Za-z_]\w*)\s*\(", source)[:20])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind=kind,
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _looks_like_node_runtime_json_config(normalized: str) -> bool:
    name = Path(normalized).name.lower()
    return (
        name in {"jest.json", "nestconfig.json", "nest-cli.json", ".nest-cli.json", "nodemon.json"}
        or name.startswith("ormconfig")
        or name.startswith("typeorm.config")
        or name in {"typeorm.json", "sequelize.config.json"}
    )


def _node_runtime_json_config_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact | None:
    try:
        data = json.loads(source)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    name = Path(file_fact.path).name
    values = [f"config-key:{key}" for key in data if isinstance(key, str)]
    values.extend(_node_runtime_json_values(data))
    return RuntimeConfigFact(
        path=file_fact.path,
        kind=_node_runtime_json_config_kind(name),
        name=name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _looks_like_aspnet_appsettings(normalized: str) -> bool:
    name = Path(normalized).name.lower()
    return name == "appsettings.json" or name.startswith("appsettings.") and name.endswith(".json")


def _aspnet_appsettings_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact | None:
    try:
        data = json.loads(source)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    name = Path(file_fact.path).name
    values = _aspnet_appsettings_values(data, name)
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="aspnet-appsettings",
        name=name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _aspnet_appsettings_values(data: dict[str, object], name: str) -> list[str]:
    values: list[str] = []
    environment = _aspnet_appsettings_environment(name)
    if environment:
        values.append(f"environment:{environment}")
    for key in data:
        if isinstance(key, str):
            values.append(f"config-section:{key}")
    for key_path, value in _json_leaf_items(data):
        lowered = key_path.lower()
        if lowered.startswith("connectionstrings."):
            values.append(f"connection-string-key:{key_path.split('.')[-1]}")
            continue
        values.append(f"config-key:{key_path}")
        if isinstance(value, str) and "url" in lowered:
            values.append(f"url-key:{key_path}")
            port_match = re.search(r":(?P<port>[0-9]{2,5})(?:/|$)", value)
            if port_match:
                values.append(f"port:{port_match.group('port')}")
        if lowered.startswith("logging.loglevel.") and isinstance(value, str):
            values.append(f"log-level:{key_path.removeprefix('Logging.LogLevel.')}={value}")
        if lowered == "allowedhosts" and isinstance(value, str):
            values.append("allowed-hosts:configured")
    return values


def _aspnet_appsettings_environment(name: str) -> str | None:
    match = re.match(r"appsettings\.([^.]+)\.json$", name, re.IGNORECASE)
    return match.group(1) if match else None


def _json_leaf_items(data: object, prefix: str = "") -> list[tuple[str, object]]:
    items: list[tuple[str, object]] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if not isinstance(key, str):
                continue
            next_prefix = f"{prefix}.{key}" if prefix else key
            items.extend(_json_leaf_items(value, next_prefix))
    elif isinstance(data, list):
        for index, value in enumerate(data[:20]):
            next_prefix = f"{prefix}[{index}]"
            items.extend(_json_leaf_items(value, next_prefix))
    elif prefix:
        items.append((prefix, data))
    return items


def _node_runtime_json_config_kind(name: str) -> str:
    lower = name.lower()
    suffix = "-template" if lower.endswith((".example", ".sample", ".template")) else ""
    if lower.startswith("ormconfig") or lower.startswith("typeorm.config") or lower == "typeorm.json":
        return f"typeorm-config{suffix}"
    if lower in {"nestconfig.json", "nest-cli.json", ".nest-cli.json"}:
        return "nestjs-config"
    if lower == "nodemon.json":
        return "nodemon-config"
    if lower == "jest.json":
        return "jest-config"
    if lower == "sequelize.config.json":
        return f"sequelize-config{suffix}"
    return f"node-json-config{suffix}"


def _node_runtime_json_values(data: dict[str, object]) -> list[str]:
    values: list[str] = []
    for key, value in data.items():
        if not isinstance(key, str):
            continue
        lower = key.lower()
        if lower == "port" and isinstance(value, int):
            values.append(f"port:{value}")
        elif lower in {"type", "dialect"} and isinstance(value, str):
            values.append(f"database-driver:{value}")
        elif lower in {"entryfile", "entry"} and isinstance(value, str):
            values.append(f"entrypoint:{value}")
        elif lower == "exec" and isinstance(value, str):
            values.append(f"command:{value}")
        elif lower in {"ext", "extension"} and isinstance(value, str):
            values.append(f"extension:{value}")
        elif lower in {"language", "compiler"} and isinstance(value, str):
            values.append(f"{lower}:{value}")
        elif lower in {"testregex", "testmatch"} and isinstance(value, str):
            values.append(f"test-pattern:{value}")
        elif lower in {"entities", "migrations", "subscribers"}:
            glob_kind = {"entities": "entity", "migrations": "migration", "subscribers": "subscriber"}[lower]
            values.extend(f"{glob_kind}-glob:{item}" for item in _json_string_list(value))
        elif lower in {"watch", "ignore"}:
            values.extend(f"{lower}-path:{item}" for item in _json_string_list(value))
        elif lower == "modulefileextensions":
            values.extend(f"extension:{item}" for item in _json_string_list(value))
        elif lower == "coveragereporters":
            values.extend(f"coverage-reporter:{item}" for item in _json_string_list(value))
        elif lower == "collectcoveragefrom":
            values.extend(f"coverage-glob:{item}" for item in _json_string_list(value))
        elif lower == "transform" and isinstance(value, dict):
            values.extend(f"transform-pattern:{item}" for item in value if isinstance(item, str))
    return values


def _json_string_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _package_scripts_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact | None:
    try:
        data = json.loads(source)
    except json.JSONDecodeError:
        return None
    scripts = data.get("scripts", {})
    if not isinstance(scripts, dict):
        return None
    values = [f"script:{name}" for name in scripts]
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="package-scripts",
        name="package.json",
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _tauri_config_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:tauri"]
    try:
        data = json.loads(source)
    except json.JSONDecodeError:
        data = {}
    if isinstance(data, dict):
        for key, prefix in [
            ("productName", "product"),
            ("version", "version"),
            ("identifier", "identifier"),
        ]:
            value = data.get(key)
            if isinstance(value, str) and value:
                values.append(f"{prefix}:{value}")
        build = data.get("build")
        if isinstance(build, dict):
            for key, prefix in [("frontendDist", "frontend-dist"), ("devUrl", "dev-url")]:
                value = build.get(key)
                if isinstance(value, str) and value:
                    values.append(f"{prefix}:{value}")
        app = data.get("app")
        if isinstance(app, dict):
            windows = app.get("windows")
            if isinstance(windows, list):
                for window in windows:
                    if not isinstance(window, dict):
                        continue
                    label = window.get("label")
                    title = window.get("title")
                    if isinstance(label, str) and label:
                        values.append(f"window:{label}")
                    if isinstance(title, str) and title:
                        values.append(f"window-title:{title}")
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="tauri-config",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _electron_runtime_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:electron"]
    if re.search(r"\bnew\s+BrowserWindow\b|\bBrowserWindow\s*\(", source):
        values.append("window:BrowserWindow")
    if re.search(r"\bpreload\s*:", source) or "preload." in source:
        values.append("preload:configured")
    if ".loadURL(" in source:
        values.append("load:loadURL")
    if ".loadFile(" in source:
        values.append("load:loadFile")
    if "Menu.buildFromTemplate" in source:
        values.append("menu:buildFromTemplate")
    if "Menu.setApplicationMenu" in source:
        values.append("menu:setApplicationMenu")
    if "context-menu" in source:
        values.append("menu:context")
    if "shell.openExternal" in source:
        values.append("shell:openExternal")
    values.extend(f"env-key:{key}" for key in re.findall(r"\bprocess\.env\.([A-Za-z_][A-Za-z0-9_]*)", source))
    values.extend(f"ipc-main:{channel}" for channel in re.findall(r"\bipcMain\.(?:on|once|handle)\(\s*['\"]([^'\"]+)['\"]", source))
    values.extend(
        f"ipc-renderer:{channel}"
        for channel in re.findall(r"\bipcRenderer\.(?:send|sendSync|invoke|on|once)\(\s*['\"]([^'\"]+)['\"]", source)
    )
    values.extend(f"context-bridge:{name}" for name in re.findall(r"\bcontextBridge\.exposeInMainWorld\(\s*['\"]([^'\"]+)['\"]", source))
    values.extend(f"window-api:{name}" for name in re.findall(r"\bwindow\.([A-Za-z_$][\w$]*)\??\.", source))
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="desktop-runtime",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=_first_desktop_runtime_line(source), line_end=_first_desktop_runtime_line(source)),
    )


def _tauri_runtime_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:tauri"]
    values.extend(f"command:{name}" for name in re.findall(r"#\s*\[\s*tauri::command\s*\]\s*(?:pub\s+)?fn\s+([A-Za-z_]\w*)", source))
    values.extend(f"plugin:{name}" for name in re.findall(r"\b(tauri_plugin_[A-Za-z_]\w*)::init\(\)", source))
    for handlers in re.findall(r"generate_handler!\s*\[\s*([^\]]+)\]", source):
        for name in re.findall(r"\b([A-Za-z_]\w*)\b", handlers):
            values.append(f"invoke-handler:{name}")
    if "Builder::default()" in source or "tauri::Builder" in source:
        values.append("builder:default")
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="desktop-runtime",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=_first_desktop_runtime_line(source), line_end=_first_desktop_runtime_line(source)),
    )


def _dbt_project_config_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:dbt"]
    values.extend(_yaml_scalar_values(source, ("name", "profile", "model-paths", "seed-paths", "macro-paths", "snapshot-paths")))
    values.extend(f"var:{name}" for name in re.findall(r"^\s{2,}([A-Za-z_][\w.-]+):\s*", _yaml_section(source, "vars"), re.MULTILINE)[:30])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="dbt-project",
        name=_yaml_scalar(source, "name") or Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _prefect_config_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:prefect"]
    values.extend(_yaml_scalar_values(source, ("name", "prefect-version")))
    values.extend(f"deployment:{name}" for name in re.findall(r"^\s*-\s+name:\s*([^#\n]+)", _yaml_section(source, "deployments"), re.MULTILINE)[:30])
    values.extend(f"work-pool:{name.strip()}" for name in re.findall(r"^\s*work_pool:\s*([^#\n]+)", source, re.MULTILINE)[:20])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="prefect-config",
        name=_yaml_scalar(source, "name") or "prefect",
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _dagster_config_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:dagster"]
    values.extend(_yaml_scalar_values(source, ("module_name", "python_file", "working_directory")))
    values.extend(f"code-location:{name.strip()}" for name in re.findall(r"^\s*location_name:\s*([^#\n]+)", source, re.MULTILINE)[:30])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="dagster-config",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _great_expectations_config_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:great-expectations"]
    values.extend(_yaml_scalar_values(source, ("config_version", "datasource_name", "name")))
    values.extend(f"suite:{name}" for name in re.findall(r"expectation_suite_name['\"]?\s*:\s*['\"]?([^,'\"\n}]+)", source)[:30])
    values.extend(f"datasource:{name}" for name in re.findall(r"^\s{2,}([A-Za-z_][\w.-]+):\s*$", _yaml_section(source, "datasources"), re.MULTILINE)[:30])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="great-expectations-config",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _kedro_catalog_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:kedro"]
    for match in re.finditer(r"^([A-Za-z_][\w.-]+):\s*$", source, re.MULTILINE):
        block = source[match.end() : _next_yaml_top_level(source, match.end())]
        values.append(f"dataset:{match.group(1)}")
        dataset_type = _yaml_scalar(block, "type")
        filepath = _yaml_scalar(block, "filepath")
        if dataset_type:
            values.append(f"type:{dataset_type}")
        if filepath:
            values.append(f"filepath:{filepath}")
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="kedro-catalog",
        name=Path(file_fact.path).name,
        values=_dedupe(values[:80]),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _airflow_dag_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:airflow"]
    values.extend(f"dag:{name}" for name in re.findall(r"\bdag_id\s*=\s*['\"]([^'\"]+)['\"]", source))
    values.extend(f"dag:{name}" for name in re.findall(r"\bDAG\(\s*['\"]([^'\"]+)['\"]", source))
    values.extend(f"dag:{name}" for name in _decorated_function_names(source, "dag"))
    values.extend(f"task:{name}" for name in re.findall(r"\btask_id\s*=\s*['\"]([^'\"]+)['\"]", source)[:50])
    values.extend(f"task:{name}" for name in _decorated_function_names(source, "task")[:50])
    values.extend(f"operator:{name}" for name in re.findall(r"\b([A-Za-z_]\w*Operator)\s*\(", source)[:50])
    values.extend(f"operator-class:{name}" for name in _airflow_operator_classes(source)[:50])
    schedule = _first_match(source, r"\bschedule(?:_interval)?\s*=\s*['\"]([^'\"]+)['\"]")
    if schedule:
        values.append(f"schedule:{schedule}")
    has_dag_marker = any(value.startswith("dag:") for value in values) or re.search(r"\bDAG\s*\(|@dag\b", source) is not None
    has_task_marker = any(value.startswith("task:") for value in values)
    kind = "airflow-dag" if has_dag_marker or has_task_marker else "airflow-operator"
    return RuntimeConfigFact(
        path=file_fact.path,
        kind=kind,
        name=(
            _first_value(values, "dag:")
            or (Path(file_fact.path).stem if kind == "airflow-dag" else None)
            or _first_value(values, "operator-class:")
            or Path(file_fact.path).stem
        ),
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=_first_runtime_line(source), line_end=_first_runtime_line(source)),
    )


def _prefect_source_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:prefect"]
    values.extend(f"flow:{name}" for name in _decorated_function_names(source, "flow"))
    values.extend(f"task:{name}" for name in _decorated_function_names(source, "task")[:50])
    values.extend(f"deployment:{name}" for name in re.findall(r"\.deploy\(\s*name\s*=\s*['\"]([^'\"]+)['\"]", source)[:20])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="prefect-flow",
        name=_first_value(values, "flow:") or Path(file_fact.path).stem,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=_first_runtime_line(source), line_end=_first_runtime_line(source)),
    )


def _dagster_source_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:dagster"]
    for decorator, prefix in [("asset", "asset"), ("op", "op"), ("job", "job"), ("schedule", "schedule"), ("sensor", "sensor")]:
        values.extend(f"{prefix}:{name}" for name in _decorated_function_names(source, decorator)[:50])
    if "Definitions(" in source:
        values.append("definitions:Definitions")
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="dagster-code",
        name=Path(file_fact.path).stem,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=_first_runtime_line(source), line_end=_first_runtime_line(source)),
    )


def _kedro_source_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:kedro"]
    values.extend(f"node:{name}" for name in re.findall(r"\bnode\(\s*(?:func\s*=\s*)?([A-Za-z_]\w*)", source)[:50])
    values.extend(f"pipeline:{name}" for name in re.findall(r"\b([A-Za-z_]\w*)\s*=\s*Pipeline\(", source)[:30])
    if "register_pipelines" in source:
        values.append("registry:register_pipelines")
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="kedro-pipeline",
        name=Path(file_fact.path).stem,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=_first_runtime_line(source), line_end=_first_runtime_line(source)),
    )


def _notebook_config_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = ["runtime:notebook"]
    try:
        data = json.loads(source)
    except json.JSONDecodeError:
        data = {}
    if isinstance(data, dict):
        cells = data.get("cells")
        if isinstance(cells, list):
            values.append(f"cells:{len(cells)}")
        metadata = data.get("metadata")
        kernelspec = metadata.get("kernelspec") if isinstance(metadata, dict) else None
        if isinstance(kernelspec, dict):
            if kernelspec.get("name"):
                values.append(f"kernel:{kernelspec['name']}")
            if kernelspec.get("language"):
                values.append(f"language:{kernelspec['language']}")
    values.extend(f"import:{name}" for name in re.findall(r"^\s*(?:import|from)\s+([A-Za-z_][\w.]*)", _notebook_code(source), re.MULTILINE)[:30])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="notebook",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _ml_source_runtime_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = _python_ml_runtime_values(source)
    kind = "ml-app" if any(value in {"framework:streamlit", "framework:gradio"} for value in values) else "ml-source"
    return RuntimeConfigFact(
        path=file_fact.path,
        kind=kind,
        name=Path(file_fact.path).stem,
        values=_dedupe(["runtime:ml", *values]),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=_first_runtime_line(source), line_end=_first_runtime_line(source)),
    )


def _helm_chart_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = []
    values.extend(f"chart:{item}" for item in re.findall(r"^\s*name:\s*([^\s#]+)", source, re.MULTILINE)[:1])
    values.extend(f"version:{item}" for item in re.findall(r"^\s*version:\s*([^\s#]+)", source, re.MULTILINE)[:1])
    values.extend(f"api-version:{item}" for item in re.findall(r"^\s*apiVersion:\s*([^\s#]+)", source, re.MULTILINE)[:1])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="helm-chart",
        name=Path(file_fact.path).parent.name or "Chart.yaml",
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _kubernetes_manifest_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = []
    values.extend(f"api-version:{item}" for item in re.findall(r"^\s*apiVersion:\s*([^\s#]+)", source, re.MULTILINE)[:5])
    values.extend(f"kind:{item}" for item in re.findall(r"^\s*kind:\s*([A-Za-z][\w.-]*)", source, re.MULTILINE)[:10])
    values.extend(f"name:{item}" for item in re.findall(r"^\s*name:\s*([A-Za-z0-9_.-]+)", source, re.MULTILINE)[:10])
    values.extend(f"image:{_manifest_value(item)}" for item in re.findall(r"^\s*image:\s*([^\s#]+)", source, re.MULTILINE)[:10])
    values.extend(f"port:{item}" for item in re.findall(r"^\s*(?:containerPort|port|targetPort):\s*(\d{2,5})", source, re.MULTILINE)[:20])
    values.extend(f"env-key:{item}" for item in re.findall(r"^\s*name:\s*([A-Z_][A-Z0-9_]*)", source, re.MULTILINE)[:20])
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="kubernetes-manifest",
        name=_first_value(values, "kind:") or Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=_first_runtime_line(source), line_end=_first_runtime_line(source)),
    )


def _openapi_spec_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = []
    values.extend(f"title:{item.strip()}" for item in re.findall(r"^\s*title:\s*(.+)$", source, re.MULTILINE)[:1])
    values.extend(f"version:{item.strip()}" for item in re.findall(r"^\s*version:\s*([^\s#]+)", source, re.MULTILINE)[:1])
    values.extend(f"server:{item.strip()}" for item in re.findall(r"^\s*-\s*url:\s*(.+)$", source, re.MULTILINE)[:5])
    if source.lstrip().startswith("{"):
        try:
            data = json.loads(source)
        except json.JSONDecodeError:
            data = {}
        if isinstance(data, dict):
            info = data.get("info") if isinstance(data.get("info"), dict) else {}
            if isinstance(info, dict):
                if info.get("title"):
                    values.append(f"title:{info['title']}")
                if info.get("version"):
                    values.append(f"version:{info['version']}")
            servers = data.get("servers")
            if isinstance(servers, list):
                for server in servers[:5]:
                    if isinstance(server, dict) and server.get("url"):
                        values.append(f"server:{server['url']}")
            paths = data.get("paths")
            if isinstance(paths, dict):
                values.append(f"paths:{len(paths)}")
    else:
        path_count = len(re.findall(r"^\s{2}/[^:\n]+:\s*$", source, re.MULTILINE))
        if path_count:
            values.append(f"paths:{path_count}")
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="openapi-spec",
        name=Path(file_fact.path).name,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=1, line_end=1),
    )


def _celery_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact:
    values = []
    values.extend(f"task:{item}" for item in re.findall(r"@(?:shared_task|\w+\.task)\s*(?:\([^)]*\))?\s*\n\s*def\s+([A-Za-z_]\w*)", source))
    values.extend(f"celery-app:{item}" for item in re.findall(r"\bCelery\(\s*['\"]([^'\"]+)['\"]", source)[:5])
    values.extend(f"env-key:{item}" for item in _env_keys(source))
    if "beat_schedule" in source or "crontab(" in source:
        values.append("schedule:celery-beat")
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="celery-worker",
        name=Path(file_fact.path).stem,
        values=_dedupe(values),
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=_first_runtime_line(source), line_end=_first_runtime_line(source)),
    )


def _looks_like_openapi_spec(source: str) -> bool:
    return bool(re.search(r"^\s*['\"]?(openapi|swagger)['\"]?\s*[:\"]", source[:5000], re.MULTILINE))


def _looks_like_kubernetes_manifest(source: str) -> bool:
    head = source[:8000]
    return bool(
        re.search(r"^\s*apiVersion\s*:", head, re.MULTILINE)
        and re.search(r"^\s*kind\s*:\s*[A-Za-z]", head, re.MULTILINE)
    )


def _looks_like_terraform_module_file(source: str) -> bool:
    return bool(
        re.search(r'^\s*(?:resource|data|module|variable|output|provider|terraform)\b', source, re.MULTILINE)
    )


def _hcl_block_body(source: str, block_name: str) -> str:
    match = re.search(rf"^\s*{re.escape(block_name)}\s*{{", source, re.MULTILINE)
    if not match:
        return ""
    return _balanced_body(source, match.end() - 1)


def _hcl_assignment_block(source: str, assignment_name: str) -> str:
    match = re.search(rf"^\s*{re.escape(assignment_name)}\s*=\s*{{", source, re.MULTILINE)
    if not match:
        return ""
    return _balanced_body(source, match.end() - 1)


def _balanced_body(source: str, open_brace_offset: int) -> str:
    depth = 0
    for index in range(open_brace_offset, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[open_brace_offset + 1 : index]
    return source[open_brace_offset + 1 :]


def _looks_like_pulumi_source(source: str) -> bool:
    lower = source.lower()
    return (
        "import pulumi" in lower
        or "from pulumi" in lower
        or "@pulumi/" in source
        or "new pulumi." in lower
        or re.search(r"\bpulumi\.(?:export|Config|Output|ResourceOptions)\b", source) is not None
    )


def _pulumi_provider_names(source: str) -> list[str]:
    names: list[str] = []
    names.extend(re.findall(r"from\s+['\"]@pulumi/([^'\"]+)['\"]", source))
    names.extend(re.findall(r"import\s+\*\s+as\s+\w+\s+from\s+['\"]@pulumi/([^'\"]+)['\"]", source))
    names.extend(re.findall(r"^\s*import\s+pulumi_([A-Za-z_]\w*)", source, re.MULTILINE))
    names.extend(re.findall(r"^\s*from\s+pulumi_([A-Za-z_]\w*)\s+import\b", source, re.MULTILINE))
    names.extend(re.findall(r'github\.com/pulumi/pulumi-([^/\s"]+)/sdk', source))
    return _dedupe([name.replace("_", "-") for name in names if name != "pulumi"])


_PULUMI_CORE_HELPERS = {
    "Config",
    "Output",
    "Input",
    "AssetArchive",
    "FileArchive",
    "FileAsset",
    "StringAsset",
}

_PULUMI_NON_RESOURCE_METHODS = {
    "Add",
    "Apply",
    "ApplyT",
    "Create",
    "CreateSecret",
    "Export",
    "First",
    "Format",
    "Get",
    "GetBoolean",
    "GetFiles",
    "GetInt32",
    "GetMimeType",
    "ID",
    "Invoke",
    "InvokeAsync",
    "Replace",
    "Require",
    "RequireSecret",
    "Serialize",
    "Split",
    "Sprintf",
    "StartsWith",
    "Substring",
    "ToOutput",
    "ToString",
    "ToStringOutput",
}

_PULUMI_NON_RESOURCE_NAMES = {
    "ArgumentException",
    "BigInteger",
    "Config",
    "Date",
    "Error",
    "Exception",
    "FileArchive",
    "FileAsset",
    "InputStream",
    "Map",
    "Promise",
    "ResourceOptions",
    "Set",
    "StackReference",
    "StringAsset",
    "TokenCredentials",
}

_PULUMI_UTILITY_PREFIXES = {
    "args",
    "awsConfig",
    "c",
    "clientConfig",
    "config",
    "console",
    "ctx",
    "credentials",
    "deploymentDeps",
    "file",
    "fmt",
    "id",
    "image",
    "JsonSerializer",
    "MimeTypes",
    "Output",
    "repoCreds",
    "resourceGroup",
    "rid",
    "roleToAssumeARN",
    "server",
    "string",
    "this",
}


def _pulumi_resource_names(source: str) -> list[str]:
    names: list[str] = []
    names.extend(re.findall(r"\bnew\s+([A-Za-z_][\w.]*\.[A-Z][A-Za-z_]\w*)\s*\(", source))
    names.extend(re.findall(r"\b([A-Za-z_][\w.]*\.[A-Z][A-Za-z_]\w*)\s*\(", source))
    names.extend(re.findall(r"\bnew\s+([A-Z][A-Za-z_]\w*)\s*\(", source))
    return _dedupe([name for name in names if _is_pulumi_resource_name(name)])


def _is_pulumi_resource_name(name: str) -> bool:
    parts = [part for part in name.split(".") if part]
    if not parts:
        return False
    first = parts[0]
    last = parts[-1]
    if name.startswith(("pulumi.", "console.")):
        return False
    if last in _PULUMI_NON_RESOURCE_NAMES or last.endswith(("Args", "Options")):
        return False
    if len(parts) > 1 and (
        first in _PULUMI_UTILITY_PREFIXES
        or last in _PULUMI_NON_RESOURCE_METHODS
        or last.startswith(("Get", "List"))
    ):
        return False
    if first in {"pulumi", "Pulumi"} and len(parts) > 1 and parts[1] in _PULUMI_CORE_HELPERS:
        return False
    return True


_ANSIBLE_CONTROL_KEYS = {
    "always",
    "any_errors_fatal",
    "args",
    "become",
    "become_method",
    "become_user",
    "block",
    "changed_when",
    "check_mode",
    "collections",
    "connection",
    "debugger",
    "delay",
    "delegate_to",
    "diff",
    "environment",
    "failed_when",
    "gather_facts",
    "handlers",
    "hosts",
    "ignore_errors",
    "import_role",
    "import_tasks",
    "import_playbook",
    "include_role",
    "include_tasks",
    "listen",
    "loop",
    "loop_control",
    "name",
    "no_log",
    "notify",
    "post_tasks",
    "pre_tasks",
    "register",
    "remote_user",
    "rescue",
    "retries",
    "role",
    "roles",
    "run_once",
    "tags",
    "tasks",
    "throttle",
    "timeout",
    "until",
    "vars",
    "when",
    "with_items",
}


def _looks_like_ansible_file(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    parts = normalized.split("/")
    if any(part in {"tasks", "handlers", "defaults", "vars", "meta", "playbooks", "group_vars", "host_vars"} for part in parts):
        return True
    if "/molecule/" in f"/{normalized}" or Path(normalized).name in {"galaxy.yml", "galaxy.yaml", "requirements.yml", "requirements.yaml"}:
        return True
    return _looks_like_ansible_source(source)


def _looks_like_ansible_source(source: str) -> bool:
    return bool(
        re.search(r"^\s*-\s+hosts\s*:", source, re.MULTILINE)
        or re.search(r"^\s*hosts\s*:", source, re.MULTILINE) and re.search(r"^\s*(?:tasks|roles)\s*:", source, re.MULTILINE)
        or "ansible.builtin." in source
        or re.search(r"^\s*-\s+name\s*:", source, re.MULTILINE) and re.search(r"^\s*(?:apt|yum|dnf|copy|template|service|package|lineinfile|include_tasks|import_tasks|debug)\s*:", source, re.MULTILINE)
    )


def _looks_like_ansible_template_file(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return (
        normalized.endswith(".j2")
        and (
            "/templates/" in f"/{normalized}"
            or "/roles/" in f"/{normalized}"
            or "{{" in source
            or "{%" in source
        )
    )


def _looks_like_ansible_inventory_or_vars_file(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    name = Path(normalized).name
    suffix = Path(normalized).suffix
    allowed_inventory_suffixes = {"", ".ini", ".cfg", ".yml", ".yaml", ".json"}
    if suffix not in allowed_inventory_suffixes:
        return False
    if "/group_vars/" in f"/{normalized}" or "/host_vars/" in f"/{normalized}":
        return True
    if name in {"hosts", "inventory"} or name.startswith(("inventory-", "inventory_")):
        return True
    if "/inventory/" in f"/{normalized}/":
        return True
    return bool(
        name.endswith((".ini", ".cfg"))
        and (
            re.search(r"^\s*\[[A-Za-z0-9_.:-]+\]\s*$", source, re.MULTILINE)
            or "ansible_host" in source
            or "ansible_user" in source
        )
    )


def _looks_like_ansible_ini_config(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    name = Path(normalized).name
    if name == "ansible.cfg":
        return True
    if not name.endswith((".ini", ".cfg")):
        return False
    non_comment_lines = [
        line.strip()
        for line in source.splitlines()
        if line.strip() and not line.lstrip().startswith(("#", ";", "["))
    ]
    if not non_comment_lines:
        return False
    key_value_lines = [line for line in non_comment_lines if "=" in line and "ansible_" not in line]
    return len(key_value_lines) >= max(1, len(non_comment_lines) // 2)


def _ini_sections(source: str) -> list[str]:
    return _dedupe(re.findall(r"^\s*\[([A-Za-z0-9_.:-]+)\]\s*$", source, re.MULTILINE))


def _ini_keys(source: str) -> list[str]:
    return _dedupe(re.findall(r"^\s*([A-Za-z_][\w.-]+)\s*=", source, re.MULTILINE))


def _ansible_inventory_hosts(source: str) -> list[str]:
    hosts: list[str] = []
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "[")):
            continue
        if "=" in stripped and "ansible_" not in stripped:
            continue
        host = stripped.split()[0]
        if "=" in host:
            continue
        if host and host not in {"children", "vars"} and not host.endswith(":"):
            hosts.append(host)
    return _dedupe(hosts)


def _looks_like_ansible_task_file(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    parent_name = Path(normalized).parent.name
    return (
        parent_name in {"tasks", "handlers", "playbooks"}
        or re.search(r"^\s*(?:tasks|handlers|pre_tasks|post_tasks):\s*$", source, re.MULTILINE) is not None
        or re.search(r"^\s*-\s+hosts\s*:", source, re.MULTILINE) is not None
        or "ansible.builtin." in source
    )


def _ansible_play_names(source: str) -> list[str]:
    names: list[str] = []
    lines = source.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^\s*-\s+name:\s*(.+)$", line)
        if not match:
            continue
        window = "\n".join(lines[index + 1 : index + 5])
        if re.search(r"^\s*hosts\s*:", window, re.MULTILINE):
            names.append(_manifest_value(match.group(1)))
    return _dedupe(names)


def _ansible_task_names(source: str) -> list[str]:
    return _dedupe(
        [
            _manifest_value(match.group(1))
            for match in re.finditer(r"^\s*-\s+name:\s*(.+)$", source, re.MULTILINE)
        ]
    )


def _ansible_module_names(source: str) -> list[str]:
    modules: list[str] = []
    current_task_indent: int | None = None
    for raw_line in source.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        direct_task = re.match(r"^(\s*)-\s+([A-Za-z_][\w.]*):\s*", raw_line)
        if direct_task:
            current_task_indent = len(direct_task.group(1))
            name = direct_task.group(2)
            if name != "name" and name not in _ANSIBLE_CONTROL_KEYS:
                modules.append(name)
            continue
        named_task = re.match(r"^(\s*)-\s+name\s*:", raw_line)
        if named_task:
            current_task_indent = len(named_task.group(1))
            continue
        key_match = re.match(r"^(\s+)([A-Za-z_][\w.]*):\s*(?:$|[^/])", raw_line)
        if current_task_indent is None or not key_match:
            continue
        indent = len(key_match.group(1))
        if indent <= current_task_indent:
            current_task_indent = None
            continue
        if indent != current_task_indent + 2:
            continue
        name = key_match.group(2)
        if name in _ANSIBLE_CONTROL_KEYS:
            continue
        modules.append(name)
    return _dedupe(modules)


def _looks_like_celery_source(source: str) -> bool:
    return (
        "from celery import" in source
        or "import celery" in source
        or "@shared_task" in source
        or re.search(r"@\w+\.task\s*\(", source) is not None
        or "Celery(" in source
    )


def _looks_like_airflow_source(source: str) -> bool:
    return "from airflow" in source or "import airflow" in source or "DAG(" in source or "@dag" in source


def _airflow_operator_classes(source: str) -> list[str]:
    return [
        name
        for name in re.findall(r"^\s*class\s+([A-Za-z_]\w*(?:Operator|Sensor|Hook))\s*\([^)]*(?:Operator|Sensor|Hook)[^)]*\)", source, re.MULTILINE)
    ]


def _looks_like_hydra_config(path: str, source: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    if "/.circleci/" in f"/{normalized}" or "/.github/workflows/" in f"/{normalized}":
        return False
    in_hydra_config_dir = "/conf/" in f"/{normalized}" or "/configs/" in f"/{normalized}"
    has_defaults = re.search(r"^\s*defaults\s*:", source, re.MULTILINE) is not None
    has_explicit_hydra = (
        re.search(r"^\s*_target_\s*:", source, re.MULTILINE) is not None
        or re.search(r"^\s*hydra\s*:", source, re.MULTILINE) is not None
    )
    return has_explicit_hydra or (in_hydra_config_dir and has_defaults)


def _looks_like_spring_config_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    name = Path(normalized).name
    if name not in {"application.properties", "application.yml", "application.yaml"}:
        return False
    return (
        "/" not in normalized
        or normalized.startswith("config/")
        or normalized.startswith("src/main/resources/")
        or "/src/main/resources/" in f"/{normalized}"
    )


def _looks_like_ktor_config(name: str, source: str) -> bool:
    if name not in {"application.conf", "application.yaml", "application.yml"}:
        return False
    lowered = source.lower()
    return "ktor" in lowered and ("deployment" in lowered or "application" in lowered or "modules" in lowered)


def _looks_like_ml_runtime_source(source: str) -> bool:
    return bool(_python_ml_runtime_values(source))


def _python_ml_runtime_values(source: str) -> list[str]:
    values: list[str] = []
    markers = [
        ("framework:pytorch", re.search(r"^(?:import|from)\s+torch\b", source, re.MULTILINE) is not None or "nn.Module" in source),
        ("framework:pytorch-lightning", "LightningModule" in source or "pytorch_lightning" in source or "lightning.pytorch" in source),
        ("framework:tensorflow", re.search(r"^(?:import|from)\s+tensorflow\b", source, re.MULTILINE) is not None or "tf.keras" in source),
        ("framework:keras", re.search(r"^(?:import|from)\s+keras\b", source, re.MULTILINE) is not None or "keras.models" in source),
        ("framework:scikit-learn", re.search(r"^(?:import|from)\s+sklearn\b", source, re.MULTILINE) is not None),
        ("framework:transformers", re.search(r"^(?:import|from)\s+transformers\b", source, re.MULTILINE) is not None or "AutoModel" in source or "AutoTokenizer" in source),
        ("framework:mlflow", re.search(r"^(?:import|from)\s+mlflow\b", source, re.MULTILINE) is not None or "mlflow." in source),
        ("framework:wandb", re.search(r"^(?:import|from)\s+wandb\b", source, re.MULTILINE) is not None or "wandb." in source),
        ("framework:hydra", "@hydra.main" in source or "hydra.compose" in source or "OmegaConf" in source),
        ("framework:streamlit", "import streamlit" in source or "streamlit." in source or re.search(r"\bst\.(?:title|write|sidebar|button|dataframe|plotly_chart)\b", source) is not None),
        ("framework:gradio", "import gradio" in source or "gradio." in source or re.search(r"\bgr\.(?:Interface|Blocks|ChatInterface|TabbedInterface)\b", source) is not None),
    ]
    values.extend(value for value, matched in markers if matched)
    values.extend(f"model-class:{name}" for name in re.findall(r"^\s*class\s+([A-Za-z_]\w*)\s*\([^)]*(?:nn\.Module|LightningModule|tf\.keras\.Model|keras\.Model)[^)]*\)", source, re.MULTILINE)[:40])
    values.extend(f"dataset-class:{name}" for name in re.findall(r"^\s*class\s+([A-Za-z_]\w*)\s*\([^)]*Dataset[^)]*\)", source, re.MULTILINE)[:40])
    has_ml_context = bool(values)
    if has_ml_context:
        values.extend(f"train-function:{name}" for name in re.findall(r"^\s*def\s+(train(?:_[A-Za-z_]\w*)?|fit(?:_[A-Za-z_]\w*)?)\s*\(", source, re.MULTILINE)[:40])
        values.extend(f"eval-function:{name}" for name in re.findall(r"^\s*def\s+((?:evaluate|eval|test|validate)(?:_[A-Za-z_]\w*)?)\s*\(", source, re.MULTILINE)[:40])
    if has_ml_context and "DataLoader(" in source:
        values.append("data-loader:DataLoader")
    if has_ml_context and ("mlflow.log_metric" in source or "mlflow.log_param" in source or "mlflow.start_run" in source):
        values.append("tracking:mlflow")
    if has_ml_context and ("wandb.log" in source or "wandb.init" in source):
        values.append("tracking:wandb")
    if has_ml_context and re.search(r"\.(?:save|save_model|save_pretrained)\s*\(", source):
        values.append("artifact:model-save")
    if has_ml_context and re.search(r"\.(?:load|load_state_dict|from_pretrained)\s*\(", source):
        values.append("artifact:model-load")
    return _dedupe(values)


def _looks_like_prefect_source(source: str) -> bool:
    return "from prefect" in source or "import prefect" in source or "@flow" in source or "@task" in source and "prefect" in source.lower()


def _looks_like_dagster_source(source: str) -> bool:
    return "from dagster" in source or "import dagster" in source or "@asset" in source or "@op" in source or "@job" in source or "Definitions(" in source


def _looks_like_kedro_source(source: str) -> bool:
    return "from kedro" in source or "import kedro" in source or "Pipeline(" in source and "node(" in source or "KedroSession" in source


def _looks_like_electron_runtime_source(source: str) -> bool:
    return (
        "from 'electron'" in source
        or 'from "electron"' in source
        or "require('electron')" in source
        or 'require("electron")' in source
        or "BrowserWindow" in source
        or "ipcMain." in source
        or "ipcRenderer." in source
        or "contextBridge.exposeInMainWorld" in source
    )


def _looks_like_tauri_runtime_source(source: str) -> bool:
    return (
        "#[tauri::command]" in source
        or "tauri::Builder" in source
        or "Builder::default()" in source
        or "generate_handler!" in source
        or "tauri_plugin_" in source
    )


def _security_source_fact(file_fact: FileFact, source: str) -> RuntimeConfigFact | None:
    if file_fact.role in {"test", "sample", "generated", "documentation"}:
        return None
    if file_fact.language not in {"javascript", "typescript", "python", "java", "kotlin", "csharp", "php", "json"}:
        return None
    values: list[str] = []
    lower = source.lower()
    normalized_path = file_fact.path.replace("\\", "/").lower()

    for name, marker in [
        ("nextauth", "NextAuth("),
        ("authjs", "from 'auth'"),
        ("authjs", 'from "auth"'),
        ("passport", "passport"),
        ("bcrypt", "bcrypt"),
        ("spring-security", "springframework.security"),
        ("spring-security", "SecurityFilterChain"),
        ("django-simplejwt", "rest_framework_simplejwt"),
        ("fastapi-oauth2", "OAuth2PasswordBearer"),
        ("aspnetcore-jwt", "JwtBearer"),
        ("helmet", "helmet("),
        ("cors", "cors("),
        ("csrf", "csrf"),
    ]:
        if marker.lower() in lower:
            values.append(f"security-signal:{name}")
    if _has_jwt_security_signal(source):
        values.append("security-signal:jwt")

    values.extend(f"env-key:{key}" for key in _security_env_keys(source))
    values.extend(f"auth-guard:{guard}" for guard in re.findall(r"@UseGuards\(\s*([^)]+)\)", source))
    values.extend(f"auth-guard:{guard}" for guard in re.findall(r"AuthGuard\(\s*['\"]([^'\"]+)['\"]", source))
    values.extend(
        f"auth-provider:{provider}Provider"
        for provider in re.findall(r"\b([A-Za-z_]\w*)Provider\s*\(", source)
        if not _is_ui_provider_name(f"{provider}Provider")
    )
    values.extend(f"permission:{item}" for item in re.findall(r"\b(?:hasRole|hasAuthority)\(\s*['\"]([^'\"]+)['\"]", source))
    values.extend(f"authorize-pattern:{item}" for item in re.findall(r"\.requestMatchers\(\s*['\"]([^'\"]+)['\"]", source))
    if file_fact.language == "csharp":
        values.extend(f"aspnet-policy:{item}" for item in re.findall(r"\[Authorize(?:\([^)]*Policy\s*=\s*['\"]([^'\"]+)['\"][^)]*\))?\]", source))
    if file_fact.language == "python":
        values.extend(f"django-auth-class:{item}" for item in re.findall(r"\b([A-Za-z_]\w*Authentication)\b", source))
        values.extend(f"fastapi-security:{item}" for item in re.findall(r"\b(OAuth2PasswordBearer|HTTPBearer|OAuth2PasswordRequestForm)\b", source))

    if "auth" in normalized_path and any(token in normalized_path for token in ("middleware", "guard", "strategy", "security", "jwt", "passport")):
        values.append(f"security-file:{Path(file_fact.path).stem}")

    values = _dedupe(values)
    if not values:
        return None
    line = _first_security_line(source)
    return RuntimeConfigFact(
        path=file_fact.path,
        kind="security-surface",
        name=Path(file_fact.path).name,
        values=values[:30],
        evidence=Evidence(file=file_fact.path, kind="runtime-config", line_start=line, line_end=line),
    )


def _security_env_keys(source: str) -> list[str]:
    keys = []
    patterns = [
        r"\bprocess\.env\.([A-Za-z_][A-Za-z0-9_]*)",
        r"\bos\.getenv\(\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]",
        r"\bEnvironment\.GetEnvironmentVariable\(\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]",
        r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}",
    ]
    for pattern in patterns:
        keys.extend(re.findall(pattern, source))
    return [
        key
        for key in _dedupe(keys)
        if any(marker in key.upper() for marker in ("AUTH", "JWT", "TOKEN", "SECRET", "SESSION", "COOKIE", "OAUTH", "CLIENT_ID", "CLIENT_SECRET"))
    ]


def _has_jwt_security_signal(source: str) -> bool:
    lower = source.lower()
    return (
        "jsonwebtoken" in lower
        or "jwtservice" in source
        or "jwtbearer" in lower
        or "jwt_" in lower
        or "simplejwt" in lower
        or "jwt.encode" in lower
        or "jwt.decode" in lower
        or "jwt.sign" in lower
        or "jwt.verify" in lower
        or "io.jsonwebtoken" in lower
        or "jwts." in lower
        or "jwtbearerdefaults" in lower
        or "bearer token" in lower
        or re.search(r"^(?:import|from)\s+jwt\b", source, re.MULTILINE) is not None
    )


def _first_security_line(source: str) -> int:
    patterns = [
        r"NextAuth\(",
        r"Auth\(",
        r"passport",
        r"jwt",
        r"JwtBearer",
        r"SecurityFilterChain",
        r"springframework\.security",
        r"@UseGuards",
        r"AuthGuard\(",
        r"OAuth2PasswordBearer",
        r"rest_framework_simplejwt",
        r"process\.env\.",
    ]
    offsets = [match.start() for pattern in patterns for match in [re.search(pattern, source, re.IGNORECASE)] if match]
    return source.count("\n", 0, min(offsets)) + 1 if offsets else 1


def _manifest_value(value: str) -> str:
    stripped = value.strip().strip("'\"")
    if stripped.startswith("{{") or "{{" in stripped:
        return "templated"
    return stripped


def _first_value(values: list[str], prefix: str) -> str | None:
    for value in values:
        if value.startswith(prefix):
            return value.removeprefix(prefix)
    return None


def _first_match(source: str, pattern: str) -> str | None:
    match = re.search(pattern, source, re.MULTILINE)
    return match.group(1) if match else None


def _yaml_scalar(source: str, key: str) -> str | None:
    return _first_match(source, rf"^\s*{re.escape(key)}:\s*(.+?)\s*(?:#.*)?$")


def _yaml_scalar_values(source: str, keys: tuple[str, ...]) -> list[str]:
    values = []
    for key in keys:
        value = _yaml_scalar(source, key)
        if value:
            cleaned = value.strip().strip("\"'")
            values.append(f"{key}:{cleaned}")
    return values


def _toml_scalar_values(source: str, keys: tuple[str, ...]) -> list[str]:
    values = []
    for key in keys:
        match = re.search(rf"^\s*{re.escape(key)}\s*=\s*['\"]?([^'\"\n#]+)['\"]?", source, re.MULTILINE)
        if match:
            values.append(f"{key}:{match.group(1).strip()}")
    return values


def _json_scalar_values(data: dict[str, object], keys: tuple[str, ...]) -> list[str]:
    values = []
    for key in keys:
        value = data.get(key)
        if isinstance(value, (str, int, float)) and str(value):
            values.append(f"{key}:{value}")
    return values


def _jsonc_object(source: str) -> dict[str, object]:
    stripped = re.sub(r"/\*[\s\S]*?\*/", "", source)
    stripped = re.sub(r"^\s*//.*$", "", stripped, flags=re.MULTILINE)
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _cloudflare_binding_values(data: dict[str, object]) -> list[str]:
    values: list[str] = []
    for key in ("kv_namespaces", "r2_buckets", "d1_databases", "queues", "services"):
        raw_items = data.get(key)
        if not isinstance(raw_items, list):
            continue
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            binding = item.get("binding")
            if isinstance(binding, str) and binding:
                values.append(f"binding:{binding}")
    assets = data.get("assets") if isinstance(data.get("assets"), dict) else {}
    asset_binding = assets.get("binding") if isinstance(assets, dict) else None
    if isinstance(asset_binding, str) and asset_binding:
        values.append(f"binding:{asset_binding}")
    return values


def _yaml_section(source: str, section: str) -> str:
    match = re.search(rf"^\s*{re.escape(section)}:\s*$", source, re.MULTILINE)
    if not match:
        return ""
    return source[match.end() : _next_yaml_top_level(source, match.end())]


def _next_yaml_top_level(source: str, offset: int) -> int:
    match = re.search(r"^\S[^:\n]*:\s*$", source[offset:], re.MULTILINE)
    return offset + match.start() if match else len(source)


def _decorated_function_names(source: str, decorator: str) -> list[str]:
    names: list[str] = []
    pattern = rf"^\s*@{re.escape(decorator)}\b"
    for match in re.finditer(pattern, source, re.MULTILINE):
        function = re.search(r"^\s*def\s+([A-Za-z_]\w*)\s*\(", source[match.end() :], re.MULTILINE)
        if function:
            names.append(function.group(1))
    return _dedupe(names)


def _notebook_code(source: str) -> str:
    try:
        data = json.loads(source)
    except json.JSONDecodeError:
        return source
    cells = data.get("cells") if isinstance(data, dict) else None
    if not isinstance(cells, list):
        return source
    snippets: list[str] = []
    for cell in cells:
        if not isinstance(cell, dict) or cell.get("cell_type") != "code":
            continue
        raw_source = cell.get("source", "")
        if isinstance(raw_source, list):
            snippets.append("".join(str(line) for line in raw_source))
        elif isinstance(raw_source, str):
            snippets.append(raw_source)
    return "\n".join(snippets)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _env_keys(source: str) -> list[str]:
    keys = []
    keys.extend(re.findall(r"\bENV\[\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\]", source))
    keys.extend(re.findall(r"\bSystem\.get_env\(\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\)", source))
    keys.extend(re.findall(r"\bMap\.fetch!\(\s*System\.get_env\(\)\s*,\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\)", source))
    keys.extend(re.findall(r"\{:\s*system\s*,\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\}", source))
    return _dedupe(keys)


def _is_ui_provider_name(name: str) -> bool:
    return name in {
        "CompositionLocalProvider",
        "PreviewParameterProvider",
        "Provider",
    }


def _first_runtime_line(source: str) -> int:
    candidates = []
    for pattern in (
        r"\bENV\[",
        r"\bSystem\.get_env",
        r"\bMap\.fetch!",
        r"^\s*config\s+:",
        r"^\s*[A-Za-z_][\w-]*:\s*$",
        r"\bconfig\.",
        r"\bDAG\(",
        r"\bdag_id\s*=",
        r"@(?:dag|flow|task|asset|op|job|schedule|sensor)\b",
        r"^\s*class\s+[A-Za-z_]\w*(?:Operator|Sensor|Hook)\s*\(",
        r"\bDefinitions\(",
        r"\bPipeline\(",
        r"\bnode\(",
        r"^(?:import|from)\s+(?:torch|tensorflow|keras|sklearn|transformers|mlflow|wandb|streamlit|gradio)\b",
        r"@hydra\.main",
        r"\b(?:LightningModule|nn\.Module|DataLoader|gr\.Interface|gr\.Blocks)\b",
        r"\bst\.(?:title|write|sidebar|button|dataframe|plotly_chart)\b",
        r'^\s*(?:terraform|provider|resource|data|module|variable|output|backend)\b',
        r'^\s*(?:include|dependency)\s+"?[^"{]*"?\s*{',
        r'^\s*(?:packer|source|build)\s*{',
        r"^(?:import|from)\s+pulumi\b",
        r"@pulumi/",
        r"^\s*-\s+hosts\s*:",
        r"^\s*-\s+name\s*:",
        r"^[A-Za-z0-9_.%/-]+\s*:(?!=)",
        r"config\.vm\.",
        r"{{\s*[A-Za-z_]",
        r"{%\s*[A-Za-z_]",
        r"^\s*\[[A-Za-z0-9_.:-]+\]\s*$",
    ):
        match = re.search(pattern, source, re.MULTILINE)
        if match:
            candidates.append(match.start())
    if not candidates:
        return 1
    return source.count("\n", 0, min(candidates)) + 1


def _first_desktop_runtime_line(source: str) -> int:
    candidates = []
    for pattern in (
        r"BrowserWindow",
        r"ipcMain\.",
        r"ipcRenderer\.",
        r"contextBridge\.exposeInMainWorld",
        r"#\s*\[\s*tauri::command",
        r"tauri::Builder",
        r"Builder::default\(",
        r"generate_handler!",
        r"tauri_plugin_",
    ):
        match = re.search(pattern, source)
        if match:
            candidates.append(match.start())
    if not candidates:
        return 1
    return source.count("\n", 0, min(candidates)) + 1


def _dedupe_facts(facts: list[RuntimeConfigFact]) -> list[RuntimeConfigFact]:
    seen: set[tuple[str, str, str]] = set()
    result: list[RuntimeConfigFact] = []
    for fact in facts:
        key = (fact.path, fact.kind, fact.name)
        if key in seen:
            continue
        seen.add(key)
        result.append(fact)
    return result
