# 19 — Makefile: the project's one CLI

> Load `00-conventions.md` first. Depends on: 12, 13, 14, 18 (every target has a real implementation by now, written piecemeal). Day 14, half a day. This prompt consolidates the Makefile into the thing the README points at for every action, with `ENV=` selecting local, EKS or AgentCore.

## Goal

A judge reads `make help` and understands the project; `make up && make demo` is the first thing that works; every showcase, test, deploy and teardown is one target; the same target name does the same thing in every environment.

## Read first

- `docs/architecture/components/10-scheduler-and-infra.md` §5 (target list — the contract), §1
- the current `Makefile` and every `make` reference in `prompts/*.md` and `docs/architecture/testing-and-showcase.md` (`grep -rho 'make [a-z-]*' prompts docs | sort -u`)
- `prompts/18-test-suite.md` (test targets), `14` (helm/eks targets), `13` (deploy/down/plan)

## Deliverables

```
Makefile                     thin; includes mk/*.mk
mk/
  vars.mk                    ENV ?= local (local|eks|aws); derived URLs/endpoints per ENV from deploy/compose/.env, helm outputs, or terraform outputs; `require-env` guard; colour/quiet toggles
  help.mk                    `make help` (default target): grouped, one line per target, generated from `## comment` annotations; prints current ENV
  stack.mk                   up, seed, down, logs, ps, shell-<service>
  demo.mk                    demo, corpus, policy-table, showcase-<x> (nine), showcase, showcase-artifacts
  test.mk                    test, test-unit, test-integration, test-e2e, test-nightly, test-report, lint, typecheck, fmt, privacy-grep, secrets-check (gitleaks over the full git history + a grep of artifacts/ and docs/ for AWS key ids, bearer tokens, E.164)
  build.mk                   build (all images), build-<service>, push (to ECR; needs ENV≠local), sbom (syft), scan (grype/trivy) — fails on critical CVEs
  aws.mk                     plan, deploy, down, seed-aws, outputs, latency-aws, register-gateway
  eks.mk                     helm-lint, helm-template, helm-kind, deploy-eks, down-eks, kube-context
  docs.mk                    diagrams-png (draw.io export), docs-check (links, make-target drift: every `make x` mentioned in docs/ and prompts/ must exist), deck-check (numbers vs artifacts, from 16)
scripts/make_check.py        used by docs-check: parses Makefile targets vs. mentions; exits non-zero on drift
README.md                    "Run it" section regenerated from `make help` output (prompt 17 owns the prose; this prompt owns the block)
```

## Target contract (names are fixed; don't rename)

| Group | Targets | Notes |
|---|---|---|
| Stack | `up` `seed` `down` `logs` `ps` | `up` is idempotent and waits for health; `down` removes volumes |
| Demo | `demo` `corpus` `policy-table` `showcase-{alexa,tower,binding,gateway,alerts,audit,mock,ref,infra}` `showcase` `showcase-artifacts` | all honour `ENV` |
| Test | `test` `test-unit` `test-integration` `test-e2e` `test-nightly` `test-report` `lint` `typecheck` `fmt` `privacy-grep` `secrets-check` | `test` = unit+integration+e2e (local); `secrets-check` is the pre-submission gate |
| Build | `build` `build-<svc>` `push` `sbom` `scan` | images tagged with git sha and `latest` |
| AWS (AgentCore) | `ecr-up` `ecr-outputs` `plan` `deploy` `down` `down-all` `seed-aws` `outputs` `latency-aws` `register-gateway` | `down` destroys the main root and keeps ECR; `down-all` is the only target that deletes images; both confirm unless `FORCE=1` |
| EKS | `helm-lint` `helm-template` `helm-kind` `deploy-eks` `down-eks` `kube-context` | `down-eks` destroys only the eks module |
| Docs | `diagrams-png` `docs-check` `deck-check` | `docs-check` runs in CI |

## Steps

1. Split the existing Makefile into `mk/*.mk`; no behaviour change; `make help` works.
2. `ENV` plumbing: every target that talks to a running system resolves its endpoints through `vars.mk`; a wrong or missing ENV fails fast with the list of valid values.
3. `docs-check` + `scripts/make_check.py`; fix every drift it finds (rename in docs, not in the Makefile).
4. `build`, `push`, `sbom`, `scan` — the supply-chain items the AWS Builder judges tend to look for; `scan` fails on critical CVEs and the base images are pinned by digest.
5. Confirmations on destructive targets; `FORCE=1` bypass for CI.
6. Regenerate the README "Run it" block from `make help`.

## Acceptance

- `make` (no args) prints grouped help with ENV shown; every target in the contract exists and is annotated.
- `make docs-check` passes: zero unknown `make` references across `docs/`, `prompts/`, `README.md`.
- `make demo ENV=local|eks|aws` all work with no other flags once the environment is up.
- `make scan` passes; `make sbom` writes `artifacts/sbom/*.json`.
- Windows note in the README: targets run under WSL2 or Git Bash; `make` on PowerShell is not supported and the README says so (the author's machine is Windows; test it).

## Guardrails

- No target does two unrelated things. `up` doesn't deploy; `deploy` doesn't test.
- No secrets in `mk/` or `.env.example`; `vars.mk` reads from the environment or `terraform output`, never from a committed file.
- Don't add targets the docs don't mention without adding them to doc 10 §5 in the same change.

## Report back

`make help` output, the `docs-check` result, `scan` summary, and the WSL2/Git Bash verification on Windows.
