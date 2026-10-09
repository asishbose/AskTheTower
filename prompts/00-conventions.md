# 00 — Conventions (load before any numbered prompt)

You are building **Ask the Tower**: an MCP server for Alexa+ that lets a person ask their carrier about their own phone line (and lines others have consented to share) over standard CAMARA network APIs. The design is finished and lives in `docs/architecture/`. Your job is to implement it as specified, prove it with tests, and keep the docs true.

## The seven rules (from `docs/architecture/README.md`) — never violate, never "improve"

1. Alexa+ phrases; Tower returns structured results. No model in the request path.
2. Policy is deterministic code. The model never decides whether a call is allowed or what a fact means.
3. Verification, not retrieval: booleans and timestamps only. No location, no content, no history beyond the audit.
4. Consent is per line, per tool, revocable, audited.
5. Alexa+ cannot speak first. Proactive = SMS/push from the Alerts service.
6. The mock carrier is the demo default; a sandbox is a config swap the gateway cannot see.
7. Binding needs one tap on the phone over mobile data. Say so wherever it matters.

Plus the six "never happens" in `e2e-wiring.md` §8. If a shortcut would break any of these, the shortcut is wrong, not the rule.

## Repo layout (fixed; prompt 01 creates it)

```
ask-the-tower/
  docs/                      architecture (spec), decks, review-response, prior-art
  prompts/                   these build prompts
  specs/camara/              vendored CAMARA OpenAPI YAMLs — the only source of paths/versions
  packages/                  libraries imported by more than one service
    tower-policy/            03 — rules, thresholds.yaml, phrasing templates, Facts/ConsentView/Outcome
    tower-consent/           04 — table models, HMAC/KMS helpers, resolve()
    tower-audit/             07 — append(), verify(), trim()
    camara-client/           05 — CarrierClient protocol, DirectClient, GatewayClient, error map
  services/                  one deployable per folder; each has Dockerfile, README.md, helm/ (via deploy/helm), tests/
    mock-carrier/            08
    tower-mcp/               02
    binding-page/            04 (web app)
    alerts/                  06
    ref-client/              09 (+ prompts/ref-client/system.md — runtime prompt, one file per role)
  deploy/
    compose/                 docker-compose.yml, env templates
    terraform/               AWS
    helm/<service>/          one chart per service + umbrella; values-kind.yaml / values-eks.yaml
  mk/                        Makefile includes (prompt 19)
  scenarios/                 demo.yaml and friends (loaded by the mock)
  artifacts/                 generated evidence: policy-table.md, latency.md, conformance-report.html, transcripts/
  Makefile                   the targets in docs/architecture/components/10 §5 — exact names
  README.md                  the submission README (prompt 17)
```

## Stack (fixed)

- Python 3.12, `uv` workspace (one `pyproject.toml` at root, members under `packages/*` and `services/*`), `ruff` + `mypy --strict` on packages, `pytest`.
- MCP server: FastMCP, Streamable HTTP. Mock and binding page: FastAPI. Alerts: plain handlers callable from Lambda and from a local loop.
- Pydantic v2 for every wire shape. `datetime` is always timezone-aware UTC. The policy engine takes `now` as an argument; nothing in `packages/` reads a clock.
- Containers: one `Dockerfile` per service, multi-stage, non-root, `python:3.12-slim`, arm64-compatible.
- Config: environment variables, documented in each service README, with a `.env.example`. No secrets in the repo; `gitleaks` runs in CI.

## Privacy invariants enforced by tests, not by reviewers

- A raw E.164 number appears in exactly three places at runtime: the mock's own state, inside a carrier call (decrypted in memory from `msisdn_enc`), and inside the SNS send. Everywhere else — logs, metrics labels, tool results, audit rows, transcripts, SMS bodies — a regex for `\+?\d{10,15}` must find nothing. Add the grep to `make test` (`tests/privacy/`).
- Keys and ids: `line_id = HMAC-SHA256(E.164, key)`; tables are keyed on it. Health words (`fall`, `emergency`, `unwell`, `911`) never appear in alert or summary templates; a test asserts it.
- Alerts are never sent to the line's own number after a SIM swap. A test asserts it.

## Product feedback is part of every prompt (hackathon requirement)

The organisers require, for every tool, API or SDK used: what it was used for, what worked, what needs work, how onboarding felt (zero to hello world), and whether we'd build with it again and why — specific, naming the tool. `docs/submission/product-feedback.md` holds one section per tool. **Each prompt that touches a tool fills that tool's section while the experience is fresh**, and the prompt's Report back quotes the entry. "The docs were confusing" is not an entry; "the Gateway console rejected `oneOf` on `device` in sim-swap.yaml with error X; workaround Y took 40 min" is.

## Secrets (hackathon requirement, and ours)

No key, token or secret in code, config, images, compose files, Terraform state stored in git, screenshots or the video. `.env` is gitignored; `.env.example` has placeholders only. `gitleaks` runs in CI over the diff and `make secrets-check` runs it over the **full history** before submission; a leaked key means a rotated key *and* a rewritten history, so don't leak one.

## Definition of done, every prompt

1. Code + tests + the service/package `README.md` (purpose, run, config, how to showcase).
2. The product-feedback section for every tool this prompt touched is drafted (◐) in `docs/submission/product-feedback.md`.
3. `make test` green on a clean checkout. The named `make showcase-<x>` target runs.
4. Latency, where the prompt names it, is *measured* and written to `artifacts/latency.md`.
5. Any deviation from the docs is applied to the docs in the same change, with a one-line note in the final message: `docs: <file> — <what changed and why>`.
6. No git operations: leave changes in the working tree and list them in the final message; the human reviews and commits.

## Working style

- Read the **Read first** list in full before writing code. The docs are terse on purpose; the detail is in the tables.
- Build the smallest vertical slice that passes the acceptance test, then widen. Don't scaffold abstractions the docs don't name.
- If something in the docs is impossible as written (a library can't do it, an API shape differs), **stop at that point**, write down the conflict and two options, and report back. Don't pick silently.
- Keep the tone of READMEs plain: what it does, what it doesn't, how to run it. No marketing.

## Cut line (decided now, so it isn't decided on the day)

If on day 12 (16 Oct) prompt 13 is not green: the demo runs on local compose with the reference client; prompt 13 is reduced to "Tower on AgentCore Runtime only, `DirectClient` to the mock on Fargate"; Gateway and Identity become a documented experiment in `docs/architecture/components/05` §3; prompt 14 is reduced to `make helm-kind` (charts proven on kind, no EKS cluster). The deck's architecture and tracks slides are edited to match. Nothing else changes.

## Three hosting targets, one code base

Every service is a container. The same images run on local compose (the demo default), on AWS with Tower on Bedrock AgentCore Runtime and the rest on Lambda/Fargate (the Alexa+ track's shape), and on EKS from Helm (the portability proof, created for the showcase window and torn down). Configuration differs; code does not. `make demo ENV=local|eks|aws` must produce the same transcripts, and that match is the claim.
