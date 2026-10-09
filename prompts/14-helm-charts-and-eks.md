# 14 — Helm charts + EKS deployment (`deploy/helm`, `deploy/terraform/modules/eks`)

> Load `00-conventions.md` first. Depends on: 12 (images green locally), 13 (ECR, DynamoDB, KMS, SNS exist). Days 12–13. The second AWS hosting target: the **same five containers** that run on AgentCore Runtime / Fargate / Lambda also run on EKS from Helm, against the same DynamoDB, KMS and SNS. That is the "production changes hosting, not architecture" claim, proven rather than asserted.

## Goal

`make deploy-eks` creates an EKS cluster, installs the umbrella chart, seeds, and `make demo ENV=eks` produces the same transcripts as local and AgentCore. `make down-eks` removes the cluster. The chart set also installs on `kind` for a no-cloud check.

## Read first

- `docs/architecture/components/10-scheduler-and-infra.md` §1 (now three columns: local, AWS/AgentCore, EKS), §6, §7 (cost)
- `docs/architecture/e2e-wiring.md` §7
- `prompts/13-aws-terraform-and-agentcore.md` (what already exists: ECR repos, tables, KMS, SNS, mock image)
- each service's `README.md` and `.env.example`

## Cost, said first

EKS is not free: the control plane is ~$0.10/h plus nodes. The deck's tracks slide says "about $12 for the month" and "no always-on instance". Both stay true only if the EKS cluster **exists for the showcase window and is torn down** (hours, not days). This prompt therefore: (a) uses a 2-node `t4g.medium`/`m7g` spot or on-demand node group, (b) records the actual cost of the showcase window in `artifacts/cost.md` as a separate line, and (c) adds one sentence to the tracks slide note: "EKS target demonstrated and torn down; cost of that window: $X". Don't hide it; don't leave the cluster up.

## Deliverables

```
deploy/helm/
  README.md                  what the charts are for; three ways to install (kind, EKS, "any k8s"); what values differ per target
  mock-carrier/              Deployment, Service, ConfigMap (scenarios), optional Ingress; values-{local,eks}.yaml
  tower-mcp/                 Deployment, Service, Ingress/ALB, HPA, PDB, ServiceAccount (IRSA on EKS); readiness /healthz; Secret ref for bearer
  binding-page/              Deployment, Service, Ingress (public, TLS)
  alerts/                    Deployment (ALERTS_MODE=k8s: hooks server + internal API), CronJobs for the 10 §3 schedules (the k8s equivalent of EventBridge Scheduler), ServiceAccount (IRSA: SNS publish, DynamoDB)
  ref-client/                Job (demo) and Deployment (optional); Bedrock via IRSA
  dynamodb-local/            kind only; disabled on EKS
  umbrella/                  `ask-the-tower` with the six as dependencies; values-kind.yaml, values-eks.yaml (DynamoDB endpoint empty → real; KMS key id; SNS ARN; ECR repos; IRSA role ARNs from Terraform outputs)
  tests/                     helm-unittest for each chart; `helm template | kubeconform` in CI
deploy/terraform/modules/eks/
  cluster (EKS 1.30+, 2-node managed node group, arm64), VPC reuse from 13, IRSA roles per service (least-privilege: DynamoDB tables by ARN, KMS key, SNS topic, Bedrock InvokeModel for ref-client only), AWS Load Balancer Controller, ECR pull, CloudWatch logs; outputs consumed by values-eks.yaml via `scripts/render_values.py`
scripts/
  render_values.py           terraform outputs → deploy/helm/umbrella/values-eks.generated.yaml (not committed)
  k8s_seed.py                same seed as compose/AWS, run as a Job
Makefile                     helm-lint, helm-template, helm-kind (kind create → load images → install → demo), deploy-eks (terraform apply eks module → render values → helm upgrade --install → seed Job → print URLs), demo ENV=eks, down-eks (helm uninstall → terraform destroy eks module only)
tests/e2e/test_eks.py        marks: runs only when ENV=eks; `make demo` transcripts vs golden; plus the CronJob fires once (shorten schedule in values for the test)
artifacts/eks-run.txt        timing + transcript match; artifacts/cost.md EKS line
```

## Steps

1. Charts from the compose definitions: identical env names, ports, healthchecks. Non-root, read-only root FS, `runAsNonRoot`, resource requests/limits, NetworkPolicy (Tower → mock, alerts → mock, nothing else east-west).
2. `make helm-kind` green: `ref-client demo` against kind via port-forward, transcripts match golden. This is the no-cloud regression and runs in CI (optional job, nightly).
3. Terraform `eks` module, applied separately from 13's root (`-target` or a second root `deploy/terraform/eks/` that reads 13's remote state) so `make down-eks` removes only the cluster.
4. IRSA per service; a test asserts each role's policy names only the ARNs from 13's outputs — no `*`.
5. `make deploy-eks` end to end; binding page reachable on a public ALB with ACM TLS; Tower reachable to the reference client (and, if 15 is on a tunnel-free path, to Alexa+ — a second registered endpoint is fine).
6. `make demo ENV=eks` → transcripts match. Run the §2.6 alerts showcase from EKS once (real SNS SMS).
7. `make down-eks`; confirm in the console; write the cost line.

## Acceptance

- `helm lint` + `kubeconform` + helm-unittest clean for every chart and the umbrella.
- `make helm-kind` and `make deploy-eks && make demo ENV=eks` both produce golden-matching transcripts — three environments, one code base, one transcript set.
- IRSA policies least-privilege by test.
- `make down-eks` leaves no EKS, no node group, no LB, no leftover ENIs; `artifacts/cost.md` has the EKS window cost and the tracks slide note is updated.

## Guardrails

- No application changes to make Kubernetes work. If one is needed, fix the service and its compose/AgentCore config in the same change.
- The EKS target is torn down after the showcase; the demo default stays local compose, and the primary AWS target stays AgentCore Runtime (the Alexa+ track's ask). EKS is the portability proof, not the main stage.
- Nothing per-line in pod labels, logs, or metrics; the privacy grep runs against `kubectl logs` output after the EKS demo.

## Report back

The three-environment transcript match, chart tree, IRSA policy summary, EKS window cost, and the one sentence added to the tracks slide note.
