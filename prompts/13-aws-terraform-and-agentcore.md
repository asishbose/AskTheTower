# 13 — AWS: Terraform + AgentCore (`deploy/terraform`)

> Load `00-conventions.md` first. Depends on: 12 (local green), spike 02B (Gateway verdict), 05 (`tables.py`). Days 10–12. **Cut line applies** (00): if not green by day 12, reduce to Runtime + `DirectClient` → Fargate mock.

## Goal

All five service images pushed to ECR (`make push`). `make deploy` brings up the AWS column of 10 §1; `make down` returns the account to zero. Tower runs on AgentCore Runtime; carrier calls go through AgentCore Gateway with Identity holding the OAuth client; the mock runs on Fargate; Alerts on Lambda + EventBridge + SNS; the binding page on Lambda + API Gateway. Latency measured again, against this.

## Read first

- `docs/architecture/components/10-scheduler-and-infra.md` — all of it
- `docs/architecture/components/05-carrier-gateway.md` §3–4
- `docs/architecture/components/06-alerts-service.md` §6 (hooks endpoint), §3 (SNS)
- `docs/architecture/spikes/B-agentcore-gateway.md`, `C-latency.md`
- `docs/architecture/e2e-wiring.md` §7 (AWS column)
- deck notes on the tracks slide (cost basis) — `docs/Decks/`

## Deliverables

```
deploy/terraform/
  ecr/                 SEPARATE ROOT with its own state: the five ECR repositories (+ lifecycle policy, scan on push, force_delete). Created once by `make ecr-up`; survives `make down`; removed only by `make down-all`. The main root reads them with `data "aws_ecr_repository"` by name, never manages them.
  main.tf, providers.tf, variables.tf, outputs.tf, backend.tf (S3 state, documented; one key per root: ecr, main, eks)
  modules/
    dynamodb/        six tables generated from `python -m tower_consent.tables --terraform` (a `generate.py` writes tables.auto.tfvars.json; CI checks it's current); PITR on Audit; TTL on BindTokens
    kms/             one CMK; aliases; key policy for the three Lambdas + Runtime role
    network/         VPC, private subnets, VPC link for Gateway → ALB
    mock_carrier/    Fargate task + service (image from the ecr root's repository URL), internal ALB, ACM cert (private CA or a public hostname — document), Secrets Manager for the mock's client registry
    agentcore_runtime/  Tower container → Bedrock AgentCore Runtime; the ref-client container as a second Runtime agent (optional, for the Strands-on-Bedrock showcase); inbound auth per spike A; env from outputs; log group
    agentcore_gateway/  Gateway from specs/camara/*.yaml; target = mock ALB (or sandbox URL via var); outbound auth via Identity (client credentials; auth-code provider for Number Verification); writes gateway-tools.json for GatewayClient
    agentcore_identity/ credential providers; nothing in Secrets Manager carrier-side
    lambdas/         binding-page, alerts, reconcile (arm64, Python 3.12, container images from ECR); API Gateway HTTP API with routes /bind/*, /me/*, /hooks/*; WAF rate rule on /hooks/*
    scheduler/       EventBridge Scheduler: rate(5m) transplant, rate(30m) care, cron 08:00 self+care, cron 03:00 reconcile
    sns/             SMS topic; sandbox opt-in numbers as a variable; optional push topic
    observability/   CloudWatch dashboards: latency SLI p95 per tool, alert counts, audit reconcile misses; metric filter asserts no line_id label
  envs/aws.tfvars.example
Makefile              ecr-up (apply the ecr root only), plan, deploy (init/plan/apply of the main root + register specs + seed Fargate mock + print outputs), down (destroy the main root — images and repositories stay), down-all (down + down-eks + destroy the ecr root; the only target that deletes images)
scripts/aws_seed.py   same as compose seed, pointed at outputs (Tower URL, binding URL, mock admin via a bastion-less `aws ecs execute-command`)
packages/camara-client  GatewayClient live wiring: tool names from gateway-tools.json; Identity-provided auth
packages/tower-consent  KMS implementations of the hasher/cipher
tests/aws/            nightly: conformance fixtures via GatewayClient → Gateway → mock (05 §7); latency run; backend swap by changing the Gateway target var
artifacts/latency-aws.md, artifacts/terraform-plan.txt, artifacts/cost.md (Cost Explorer after 48 h + the calculator)
```

## Steps

1. State backend, KMS, DynamoDB from the generated definitions. `terraform plan` clean.
2. Mock on Fargate; reach it from a Lambda in the VPC; seed it.
3. Runtime with Tower pointed at `DirectClient` → Fargate mock first. Inspector against the Runtime URL. This is the cut-line configuration; get it green before touching Gateway.
4. Gateway + Identity; switch Tower to `GatewayClient`; run the conformance fixtures through it; if spike B said no, stop here and document per the cut line.
5. Lambdas, API Gateway, Scheduler, SNS; register the demo phone numbers for SMS sandbox; run §2.6 with a real phone.
6. Latency against the mock on Fargat via Runtime → `artifacts/latency-aws.md`. Compare to local.
7. `make down`; confirm the five ECR repositories are still there (`aws ecr describe-repositories`) and nothing else is; screenshot billing after 24 h (ECR storage for five ~150 MB images is cents); `artifacts/cost.md`. `make down-all` is for the very end, after judging.

## Acceptance

- `make deploy` from a clean account with only the tfvars filled; outputs include the Tower MCP URL, the binding URL, the hooks base.
- §2.5 showcase (Gateway tool list, backend swap via variable) works — or the cut-line note exists in `components/05` §3 and the deck slide is updated.
- §2.6 on a real phone with SNS.
- p95 recorded; if > 400 ms, the per-hop breakdown is in the artefact and the deck's "measured not assumed" note is updated to the real number.
- `make down` → zero resources except the five ECR repositories; `make down-all` → zero; cost sheet filled.

## Guardrails

- No carrier-side secret in Secrets Manager when Identity is in use; `gitleaks` + a tf-lint rule for inline secrets.
- Metrics never carry `line_id` or any per-line label (10 §2). A test on the dashboard definitions asserts it.
- Don't build a second mock path for AWS; same image, same scenarios.

## Report back

Outputs (redacted), the Gateway verdict and what was cut if anything, `latency-aws.md`, and the cost sheet vs the "about $12" claim — with the deck slide edited if the number moved.
