# Build prompts — Ask the Tower

Executable prompts, one per increment, in dependency order. Each is written to be handed to a coding agent (or read by a human) with no other context than the repo. Every prompt points at the architecture documents it implements; the documents are the spec, the prompt is the work order.

Deadline: **23 Oct 2026, 12:00 PT.** Written 5 Oct. Eighteen days, with day 18 kept as buffer.

## Run everything at once

`RUN-ALL.md` executes every prompt below in dependency order without asking questions, builds every artefact, writes and runs the offline tests, and defers anything that needs AWS, Alexa+, a phone or a camera to `docs/submission/build-log.md`. Use it for the first full pass; use the individual prompts to redo one increment or to run the deferred live steps.

Live AWS checklist (the deferred steps of 13, in order): `make ecr-up` (once; the repositories survive `make down`) → `make build` → `make push ENV=aws` → `make plan` (read it) → `make deploy` → smoke (`/healthz`, MCP Inspector, `make demo ENV=aws`) → `make latency-aws` → `make down ENV=aws`. `make down-all` only after judging; it is the only target that deletes images.

## How to run one

1. Open the repo root. Paste `00-conventions.md` first, then the numbered prompt. (If the agent can read files, say: "Load `prompts/00-conventions.md`, then execute `prompts/NN-….md`.")
2. The prompt's **Read first** list is mandatory reading before any code.
3. The agent stops at **Report back** and lists deviations from the docs. Deviations are fixed in the docs *in the same change*, never left implicit.
4. Nothing is done until **Acceptance** passes on a clean checkout: `make test` green, the named `make showcase-<x>` target works, and the artefact it names exists.

## Order and dependencies

| # | Prompt | Builds | Needs | Day |
|---|---|---|---|---|
| 00 | [conventions](00-conventions.md) | the shared rules every prompt assumes | — | — |
| 01 | [repo scaffold](01-repo-scaffold.md) | monorepo layout, tooling, CI skeleton, Makefile stubs | — | 1 |
| 02 | [week-one spikes](02-week-one-spikes.md) | the three unknowns, answered with evidence | 01 | 1–2 (in parallel) |
| 03 | [policy engine](03-policy-engine.md) | `tower-policy`: rules, thresholds, templates, decision table | 01 | 1 |
| 04 | [CAMARA specs + mock carrier](04-camara-specs-and-mock-carrier.md) | `specs/camara/`, `services/mock-carrier` | 01 | 2–3 |
| 05 | [consent library + store](05-consent-library-and-store.md) | `tower-consent`: tables, crypto, `resolve` | 01 | 3 |
| 06 | [carrier client](06-carrier-client.md) | `camara-client`: `DirectClient`, error map, conformance fixtures | 04 | 4 |
| 07 | [audit log](07-audit-log.md) | `tower-audit`: writer, chain, verify | 05 | 4 |
| 08 | [Tower MCP server](08-tower-mcp-server.md) | `services/tower-mcp`: three tools, envelope, latency harness | 03 05 06 07 | 5–6 |
| 09 | [binding page](09-binding-page.md) | `services/binding-page`: one tap, grants, revoke, admin view | 05 06 | 7 |
| 10 | [alerts service](10-alerts-service.md) | `services/alerts`: hooks, polls, windows, escalation, SNS | 03 05 06 07 | 8 |
| 11 | [reference client + corpus](11-reference-client-and-corpus.md) | `services/ref-client`: Strands agent on Bedrock, corpus test, transcripts | 08 | 9 |
| 12 | [local compose + `make demo`](12-local-compose-and-demo.md) | `deploy/compose`, seed, the three moments end to end | 04–11 | 9–10 |
| 13 | [AWS: Terraform + AgentCore](13-aws-terraform-and-agentcore.md) | `deploy/terraform`: all five images in ECR; Tower (and ref client) on **Bedrock AgentCore Runtime**, Gateway, Identity, Lambda, Fargate, DynamoDB, SNS | 12, spike 02b | 10–12 |
| 14 | [Helm charts + EKS](14-helm-charts-and-eks.md) | `deploy/helm/*`, the `eks` Terraform module, `make deploy-eks` — the same containers on **EKS**, torn down after the showcase | 12 13 | 12–13 |
| 15 | [Alexa+ surface](15-alexa-plus-surface.md) | toolkit registration, simulator run, phrasing corpus on Alexa+ | 13, spike 02a | 13–14 |
| 18 | [test suite](18-test-suite.md) | **unit / integration / e2e** as one suite with gates, `ENV=` matrix, `artifacts/test-report.md` | 03–14 | 14 |
| 19 | [Makefile](19-makefile.md) | the one CLI: `make help`, `ENV=local\|eks\|aws`, build/scan/sbom, docs-check | 12 13 14 18 | 14 |
| 20 | [Web chat page](20-web-chat-page.md) | reference client behind Cognito on AgentCore Runtime + a thin page: the Alexa+ stand-in for the AWS demo; `MOCK_ASSUME_MOBILE_DATA`; Cognito `sub` seeding | 09 11 13 15 | — |
| 16 | [showcase artefacts + video](16-showcase-artefacts-and-video.md) | `artifacts/*`, the nine-step run, the recording | all | 15–16 |
| 17 | [submission README + prior art](17-submission-readme-and-prior-art.md) | the pitch-and-run README, `docs/prior-art.md`, form text, licence | 16 18 19 | 17 |

Numbers are stable identifiers, not the execution order: 18 and 19 run before 16 and 17 (they were added after the first cut). Day 14 carries three prompts; 18 and 19 are each half a day of consolidation, not new code.

Day 18 (22 Oct) is buffer. If day 12 arrives and 13 is not green, the demo is local compose + reference client, prompt 13 is cut to "Runtime only", and 14 is cut to `make helm-kind` (charts proven on kind, EKS not deployed). That decision is written in 00 so nobody has to make it on the day.

## Cross-cutting, from the organisers' mid-period note (5 Oct)

- **Product feedback is required, per tool.** `docs/submission/product-feedback.md` has a section per tool; each prompt fills its tools' sections as it runs (rule in 00). Prompt 17 refuses to finish with any section blank.
- **No keys in the repo.** `.env` ignored from prompt 01; `make secrets-check` (full-history gitleaks) before tagging.
- **The track tool must be impossible to miss.** "Alexa+ MCP Toolkit" in the description's first sentences, in Built With, on the README's first screen, spoken and captioned in the video (16, 17).
- **The video is a pitch.** Problem → who it's for → it working → how it uses the track tool → what the app does; script positions fixed in 16.

## Two kinds of `prompts/`

This folder holds **build** prompts. Runtime prompts for agents that ship (the reference client's system prompt) live beside their service, at `services/ref-client/prompts/ref-client/system.md`, one file per role, as the architecture doc specifies. Don't mix them.
