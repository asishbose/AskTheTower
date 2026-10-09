#!/usr/bin/env python3
"""Seed the AWS deployment (`make seed-aws`, part of `make deploy`): the same demo the local stack uses, pointed at
Terraform's outputs.

1. **Mock carrier on Fargate** — reset it to `scenarios/<scenario>.yaml` (default `demo`) through its admin API.
   The admin API is never routed by the internal ALB, so the call runs *inside* the task with ECS Exec
   (bastion-less): `aws ecs execute-command … --command "python -c '<POST 127.0.0.1:8443/_admin/scenarios/load>'"`.
   Needs the AWS CLI and the Session Manager plugin.
2. **Consent store** — the demo's people and lines in DynamoDB (`tower_mcp.seed.seed_demo`: Asish owns his line,
   Mom owns hers and has granted Asish `watch` as "mom"), with `line_id` and `msisdn_enc` made by KMS
   (TOWER_ENV=aws, the keys from the outputs). Numbers come from the scenario file and leave only as line ids
   and ciphertext. Re-running is safe: an existing binding or grant is reported, not duplicated.

    uv run python scripts/aws_seed.py                 # both steps
    uv run python scripts/aws_seed.py --dry-run       # print what would run; touches nothing
    uv run python scripts/aws_seed.py --skip-mock     # consent store only
"""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _tf_outputs import ROOT, load_outputs  # noqa: E402


def aws_cli() -> str:
    found = shutil.which("aws")
    if not found:
        raise SystemExit("the AWS CLI (and the Session Manager plugin for ECS Exec) must be on PATH")
    return found


def mock_load_command(outputs: dict[str, Any], scenario: str, task_arn: str) -> list[str]:
    if not scenario.replace("-", "").replace("_", "").isalnum():
        raise SystemExit(f"bad scenario name {scenario!r}")
    # No single quotes inside: ECS Exec passes the string to the container as `python -c '<code>'`.
    code = (
        "import json, urllib.request as u; "
        'r = u.Request("http://127.0.0.1:8443/_admin/scenarios/load", '
        f'data=json.dumps({{"name": "{scenario}"}}).encode(), '
        'headers={"content-type": "application/json"}, method="POST"); '
        "print(u.urlopen(r, timeout=10).read().decode())"
    )
    return [
        "aws", "ecs", "execute-command",
        "--region", str(outputs["region"]),
        "--cluster", str(outputs["mock_cluster_name"]),
        "--task", task_arn,
        "--container", str(outputs["mock_container_name"]),
        "--interactive",
        "--command", f"python -c '{code}'",
    ]  # fmt: skip


def mock_task_arn(outputs: dict[str, Any]) -> str:
    out = subprocess.run(  # noqa: S603
        [
            aws_cli(),
            "ecs",
            "list-tasks",
            "--region",
            str(outputs["region"]),
            "--cluster",
            str(outputs["mock_cluster_name"]),
            "--service-name",
            str(outputs["mock_service_name"]),
            "--desired-status",
            "RUNNING",
            "--output",
            "json",
        ],  # fmt: skip
        check=True,
        capture_output=True,
        text=True,
    )
    arns = json.loads(out.stdout).get("taskArns", [])
    if not arns:
        raise SystemExit("no running mock-carrier task (is the ECS service up?)")
    return str(arns[0])


def seed_mock(outputs: dict[str, Any], scenario: str, dry_run: bool) -> None:
    if not outputs.get("mock_cluster_name"):
        print("mock: carrier_backend is not mock — nothing to seed on the carrier side")
        return
    task = "<running task arn>" if dry_run else mock_task_arn(outputs)
    cmd = mock_load_command(outputs, scenario, task)
    print("+", " ".join(shlex.quote(c) for c in cmd))
    if not dry_run:
        subprocess.run([aws_cli(), *cmd[1:]], check=True)  # noqa: S603


def demo_numbers(scenario: str) -> tuple[str, str]:
    doc = yaml.safe_load((ROOT / "scenarios" / f"{scenario}.yaml").read_text("utf-8"))
    numbers = list(doc["lines"])
    if len(numbers) < 2:
        raise SystemExit(f"scenarios/{scenario}.yaml needs two lines (Asish, Mom)")
    return numbers[0], numbers[1]


def store_env(outputs: dict[str, Any]) -> dict[str, str]:
    return {
        "TOWER_ENV": "aws",
        "AWS_REGION": str(outputs["region"]),
        "TOWER_TABLE_PREFIX": str(outputs["table_prefix"]),
        "TOWER_KMS_KEY_ID": str(outputs["kms_key_arn"]),
        "TOWER_KMS_HMAC_KEY_ID": str(outputs["kms_hmac_key_arn"]),
    }


def seed_store(outputs: dict[str, Any], scenario: str, dry_run: bool) -> None:
    env = store_env(outputs)
    print(f"store: tables {env['TOWER_TABLE_PREFIX']}* in {env['AWS_REGION']}, KMS keys from outputs")
    if dry_run:
        print("store: would run tower_mcp.seed.seed_demo (users, two bound lines, Mom→Asish watch grant)")
        return
    import boto3
    from tower_consent import Store, crypto_from_env
    from tower_consent.errors import ConsentError
    from tower_mcp.seed import seed_demo

    store = Store.from_env(env)
    hasher, cipher = crypto_from_env(env, kms_client=boto3.client("kms", region_name=env["AWS_REGION"]))
    asish, mom = demo_numbers(scenario)
    try:
        seeded = seed_demo(store, hasher, cipher, asish_e164=asish, mom_e164=mom, now=datetime.now(UTC))
    except ConsentError as e:
        print(f"store: already seeded ({type(e).__name__}) — leaving it as is")
        return
    print(
        f"store: seeded users {seeded.asish_user}, {seeded.mom_user}; lines {seeded.asish_line[:12]}…, {seeded.mom_line[:12]}…"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outputs", type=Path, default=None)
    ap.add_argument("--scenario", default="demo")
    ap.add_argument("--skip-mock", action="store_true")
    ap.add_argument("--skip-store", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    outputs = load_outputs(args.outputs)
    if not args.skip_mock:
        seed_mock(outputs, args.scenario, args.dry_run)
    if not args.skip_store:
        seed_store(outputs, args.scenario, args.dry_run)
    print(f"binding page: {outputs.get('binding_url')}  Tower MCP: {outputs.get('tower_mcp_url')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
