"""Static checks on deploy/terraform (offline; prompt 13 guardrails).

- The DynamoDB definitions Terraform applies are generated from the Python tables and are current (CI check).
- Every module named in prompt 13's Deliverables exists with main/variables/outputs.
- No metric — dashboard widget or metric filter — carries a per-line label (10 §2).
- No inline secret in any .tf file (the tf-lint rule for inline secrets; gitleaks covers the rest).
- One Gateway target per vendored spec; the specs decode and carry `{apiRoot}` servers to rewrite.
- `terraform fmt -check` and `terraform validate` (init -backend=false; never plan/apply) when terraform is present.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tests.aws.conftest import ROOT, TF

MODULES = [
    "dynamodb",
    "kms",
    "network",
    "mock_carrier",
    "agentcore_runtime",
    "agentcore_gateway",
    "agentcore_identity",
    "lambdas",
    "scheduler",
    "sns",
    "observability",
]
TF_FILES = sorted(p for p in TF.rglob("*.tf") if ".terraform" not in p.parts)


def terraform_bin() -> str | None:
    found = shutil.which("terraform")
    if found:
        return found
    home = Path.home() / "tools" / "terraform"
    return str(home) if home.exists() else None


@pytest.mark.unit
def test_tables_tfvars_is_current() -> None:
    gen = TF / "modules" / "dynamodb" / "generate.py"
    r = subprocess.run([sys.executable, str(gen), "--check"], capture_output=True, text=True, cwd=ROOT)  # noqa: S603
    assert r.returncode == 0, r.stderr
    doc = json.loads((TF / "tables.auto.tfvars.json").read_text())["dynamodb_tables"]
    assert sorted(doc) == ["AlertsState", "Audit", "BindTokens", "Grants", "Lines", "Users", "Watches"]
    assert doc["Audit"]["point_in_time_recovery"] is True
    assert doc["BindTokens"]["ttl"] == {"enabled": True, "attribute_name": "expires_at"}
    assert doc["AlertsState"]["ttl"]["enabled"] is True


@pytest.mark.unit
@pytest.mark.parametrize("module", MODULES)
def test_module_layout(module: str) -> None:
    d = TF / "modules" / module
    for f in ("main.tf", "variables.tf", "outputs.tf"):
        assert (d / f).exists(), f"{d}/{f}"


@pytest.mark.unit
def test_root_files_and_backend_placeholders() -> None:
    for f in (
        "main.tf",
        "providers.tf",
        "variables.tf",
        "outputs.tf",
        "backend.tf",
        "envs/aws.tfvars.example",
    ):
        assert (TF / f).exists(), f
    backend = (TF / "backend.tf").read_text()
    assert 'backend "s3"' in backend and "REPLACE-ME" in backend


@pytest.mark.unit
def test_ecr_is_its_own_root_and_the_main_root_only_reads_it() -> None:
    """`make down` (main root) must never delete images: the repositories live in deploy/terraform/ecr, own state."""
    ecr = TF / "ecr"
    for name in ("main.tf", "providers.tf", "variables.tf", "outputs.tf", "backend.tf"):
        assert (ecr / name).exists(), name
    keys = {
        root: re.search(r'key\s*=\s*"([^"]+)"', (root / "backend.tf").read_text()).group(1)  # type: ignore[union-attr]
        for root in (TF, ecr, TF / "eks")
    }
    assert len(set(keys.values())) == 3, keys
    repos = (ecr / "main.tf").read_text()
    assert (
        repos.count('resource "aws_ecr_repository" "service"') == 1 and "force_delete         = true" in repos
    )
    assert "scan_on_push = true" in repos and 'resource "aws_ecr_lifecycle_policy" "service"' in repos
    outputs = (ecr / "outputs.tf").read_text()
    assert all(f'output "{o}"' in outputs for o in ("ecr_repositories", "registry", "region"))
    for f in TF_FILES:
        if ecr not in f.parents:
            assert 'resource "aws_ecr_' not in f.read_text(), (
                f"{f} manages ECR; only deploy/terraform/ecr may"
            )
    assert 'data "aws_ecr_repository" "service"' in (TF / "main.tf").read_text()
    assert 'output "ecr_repositories"' in (TF / "outputs.tf").read_text()  # push_images.py / eks keep working


def _metric_arrays(widget_props: dict) -> list[list]:
    return [m for m in widget_props.get("metrics", []) if isinstance(m, list)]


@pytest.mark.unit
def test_dashboard_has_no_per_line_labels() -> None:
    tpl = (TF / "modules" / "observability" / "dashboard.json.tftpl").read_text()
    rendered = re.sub(
        r"\$\{(\w+)\}", lambda m: "400" if m.group(1) == "latency_budget_ms" else f"x-{m.group(1)}", tpl
    )
    dash = json.loads(rendered)
    assert dash["widgets"], "dashboard has widgets"
    for w in dash["widgets"]:
        props = w["properties"]
        for metric in _metric_arrays(props):
            # [namespace, metric name, dim1 name, dim1 value, dim2 name, ...(, {options})]
            parts = [x for x in metric if isinstance(x, str)]
            dims = parts[2:]
            names, values = dims[0::2], dims[1::2]
            assert not any("line" in n.lower() for n in names), metric
            assert not any(v.startswith("ln_") for v in values), metric
        query = props.get("query", "")
        for by in re.findall(r"\bby\s+([\w.,\s]+)", query):
            assert "line" not in by.lower(), query
    assert "p95" in tpl and "AuditReconcileMisses" in tpl and "AlertsSent" in tpl


@pytest.mark.unit
def test_metric_filters_have_no_dimensions_and_guard_exists() -> None:
    obs = (TF / "modules" / "observability" / "main.tf").read_text()
    blocks = re.findall(r"metric_transformation\s*\{(.*?)\n\s*\}", obs, re.S)
    assert blocks
    for b in blocks:
        assert "dimensions" not in b, b
    assert "LineIdOnMetric" in obs and 'CloudWatchMetrics\\" \\"line_id' in obs  # guard filter + alarm
    for f in TF_FILES:
        text = f.read_text()
        for m in re.finditer(r"dimensions\s*=\s*\{([^}]*)\}", text):
            assert "line" not in m.group(1).lower(), f"{f}: {m.group(0)}"


SECRET_ATTR = re.compile(
    r'^\s*(\w*(?:secret|password|token|api_key|private_key)\w*)\s*=\s*"([^"$]*)"', re.I | re.M
)
ALLOWED_LITERALS = {"", "REPLACE-ME"}


@pytest.mark.unit
def test_no_inline_secrets_in_terraform() -> None:
    offenders = []
    for f in TF_FILES + [TF / "envs" / "aws.tfvars.example"]:
        for m in SECRET_ATTR.finditer(f.read_text()):
            name, value = m.group(1), m.group(2)
            if value in ALLOWED_LITERALS or name.endswith(("_ref", "_arn", "_name", "_location", "_source")):
                continue
            if value.startswith("env:"):
                continue
            offenders.append(f"{f.relative_to(ROOT)}: {name} = {value!r}")
    assert offenders == []


@pytest.mark.unit
def test_no_carrier_secret_outside_identity_on_the_gateway_path() -> None:
    """Guardrail: with Identity in use, the carrier client secret reaches only AgentCore Identity (and the mock's
    own registry, which issues it). Tower's environment carries it only in the cut-line (direct) branch."""
    main = (TF / "main.tf").read_text()
    gateway_branch = main.split('var.tower_carrier_client == "gateway" ? {', 1)[1].split("} : {", 1)[0]
    assert "SECRET" not in gateway_branch
    mock = (TF / "modules" / "mock_carrier" / "main.tf").read_text()
    assert "aws_secretsmanager_secret" in mock  # the mock's own registry (10 §2)
    for module in ("agentcore_runtime", "lambdas", "agentcore_gateway"):
        text = (TF / "modules" / module / "main.tf").read_text()
        assert 'aws_secretsmanager_secret"' not in text, module


@pytest.mark.unit
def test_one_gateway_target_per_spec() -> None:
    specs = sorted((ROOT / "specs" / "camara").glob("*.yaml"))
    assert len(specs) == 6
    for spec in specs:
        doc = yaml.safe_load(spec.read_text())
        assert doc["servers"][0]["url"].startswith("{apiRoot}/"), spec.name
    gw = (TF / "modules" / "agentcore_gateway" / "main.tf").read_text()
    assert 'fileset(var.specs_dir, "*.yaml")' in gw and "{apiRoot}" in gw
    assert 'authorizer_type = "AWS_IAM"' in gw and "AUTHORIZATION_CODE" in gw and "CLIENT_CREDENTIALS" in gw


@pytest.mark.unit
def test_schedules_match_10_section_3() -> None:
    sched = (TF / "modules" / "scheduler" / "main.tf").read_text()
    for expr, payload in [
        ("rate(5 minutes)", 'profile = "transplant"'),
        ("rate(30 minutes)", 'profile = "care"'),
        ("cron(0 8 * * ? *)", 'profile = "self"'),
        ("cron(0 3 * * ? *)", "scheduled_time"),
    ]:
        assert expr in sched and payload in sched


@pytest.mark.unit
def test_no_phone_numbers_or_account_ids_in_deploy() -> None:
    from tests.privacy.patterns import phone_hits

    for f in TF_FILES + [TF / "envs" / "aws.tfvars.example", TF / "README.md"]:
        assert not phone_hits(f.read_text()), f


@pytest.mark.unit
def test_terraform_fmt() -> None:
    tf = terraform_bin()
    if tf is None:
        pytest.skip("terraform CLI not installed (PATH or ~/tools/terraform)")
    r = subprocess.run([tf, "fmt", "-check", "-recursive"], cwd=TF, capture_output=True, text=True)  # noqa: S603
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.integration
@pytest.mark.parametrize("root", [".", "ecr"])
def test_terraform_validate(root: str) -> None:
    """`init -backend=false` + `validate`: downloads the AWS provider (network) but never touches AWS."""
    tf = terraform_bin()
    if tf is None:
        pytest.skip("terraform CLI not installed (PATH or ~/tools/terraform)")
    env = {**os.environ, "TF_IN_AUTOMATION": "1"}
    init = subprocess.run(  # noqa: S603
        [tf, "init", "-backend=false", "-input=false", "-no-color"],
        cwd=TF / root,
        capture_output=True,
        text=True,
        env=env,
    )
    if init.returncode != 0 and ("registry.terraform.io" in init.stderr or "dial tcp" in init.stderr):
        pytest.skip("terraform init could not reach the provider registry (network)")
    assert init.returncode == 0, init.stderr
    r = subprocess.run([tf, "validate", "-no-color"], cwd=TF / root, capture_output=True, text=True, env=env)  # noqa: S603
    assert r.returncode == 0, r.stdout + r.stderr
