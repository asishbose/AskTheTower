# 20 — Web chat page: reference client deployed behind Cognito

> Builds the three **new** parts of `docs/architecture/bind-and-alert-flows.md` (Badhri's flows + the 2026-10-09 decisions D-A…D-J): a Cognito user pool with a user script, the reference-client agent as an HTTP endpoint on AgentCore Runtime, and a thin signed-in chat page in front. Plus the mock flag `MOCK_ASSUME_MOBILE_DATA` and `seed-aws` taking real Cognito `sub`s. Docs and diagrams change **first**, code second, tests with the code, deployment last. **No git operations**: leave every change in the working tree and list it in the final message.

## Read first

- `prompts/00-conventions.md`, `prompts/RUN-ALL.md` (Decisions table, Operating mode)
- `docs/architecture/bind-and-alert-flows.md` — the contract for this prompt; the Decisions table at its top overrides anything in its body
- `docs/architecture/components/09-reference-client.md` (esp. §6 "Deployed as the web chat page"), `components/01-alexa-surface.md` §4 (inbound identity), `components/02-tower-mcp-server.md` §2 (`next_step` envelope), `components/04-consent-and-binding.md` §5, `components/08-mock-carrier.md` §3, `components/10-scheduler-and-infra.md` §5 (make targets), `components/11-demo-ui.md` §1 (what the demo UI is *not* — this prompt must not duplicate it)
- `docs/architecture/deployment-agentcore.md`, `e2e-wiring.md` §6 (contracts) and §8 (never happens)
- `services/tower-mcp/src/tower_mcp/auth.py` (already accepts Cognito access tokens: `client_id` in place of `aud`, `TOWER_JWT_CLIENT_IDS`), `services/tower-mcp/src/tower_mcp/next_step.py`
- `services/ref-client/src/ref_client/{agent,demo,mcp_client,transcript}.py`, `prompts/ref-client/system.md`
- `services/binding-page/src/binding_page/{mobile_data,session}.py`, `services/mock-carrier/src/mock_carrier/{settings,runtime}.py`
- `deploy/terraform/{main.tf,variables.tf,outputs.tf}`, `deploy/terraform/modules/{agentcore_runtime,lambdas,network}/`, `mk/aws.mk`, `scripts/aws_seed.py`
- `.claude/rules/*.md` — architecture-fidelity (docs and diagrams first), testing, delivery, git

## Scope and non-goals

In scope: the chat page as the **Alexa+ stand-in** for the AWS demo and the prompt-15 fallback. It is the reference client (09) — same agent, prompts, stories, golden transcripts — exposed over HTTP with a page in front.

Out of scope, even if easy: a third client; SMS from the chat page (D-D); QR in the chat page (D-E); any change to the demo UI (11); any change to Tower's tool shapes, policy, consent or audit; a model producing a URL; phone numbers in prompts, logs or the repo; two-way SMS on AWS (D-I); magic-link re-entry for the binding page (D-H, roadmap).

## Decisions already taken (do not reopen)

| Point | Decision |
|---|---|
| Identity | Cognito user pool, one app client (PKCE, no secret). `user_id = sub`. Tower: `TOWER_JWKS_URL = https://cognito-idp.<region>.amazonaws.com/<pool>/.well-known/jwks.json`, `TOWER_JWT_ISSUER = https://cognito-idp.<region>.amazonaws.com/<pool>`, `TOWER_JWT_CLIENT_IDS = <app client id>`. Local compose keeps `X-Tower-User`. |
| Agent endpoint | `POST /invocations {"input": "<text>", "session_id": "<opaque>"}` → `{"text": "...", "next_step": {...} | null, "tool_calls": [{name, reason_codes}]}`. `Authorization: Bearer <Cognito access token>` required; 401 without, before any model call. The agent forwards the same bearer to Tower unchanged. `next_step` is copied from the tool result verbatim; never from model text. Streaming: not this week. |
| Where the agent runs | AWS: AgentCore Runtime as a second runtime (HTTP, not MCP), image `ref-client` already in ECR. Local: the existing `ref-client` container in compose, same endpoint on `:8083`. |
| Chat page | One static page (`services/web-chat/`): sign-in via Cognito Hosted UI (PKCE) → textbox → calls `/invocations` with the token → renders `text`, and if `next_step.kind == "bind_line"` and `next_step.url` starts with `WEB_CHAT_BINDING_BASE_URL + "/bind/"`, shows "Your line isn't connected yet" with the link (copyable) and "tap it on your phone, then ask again". Any other URL is not shown and is logged as `NEXT_STEP_REJECTED`. Plain HTML + one JS file; no framework, no build step. AWS: S3 + CloudFront; Lambda function URL (or API Gateway HTTP API) in front of the agent for CORS. Local: served by the `ref-client` container at `/`. |
| Users | `scripts/cognito_user.py create|delete|sub <name>` (boto3 `admin_create_user` + `admin_set_user_password` permanent; prints the `sub`). Password from `COGNITO_PASSWORD_<NAME>` env or prompt; never written to disk. |
| Seeding | `scripts/aws_seed.py` takes `--user asish=<sub> --user mom=<sub>` (or reads `artifacts/cognito-users.json` written by `cognito_user.py`, gitignored) and writes those ids in `Lines.owner_user_id` and `Grants.grantee_user_id`. Local seeds keep `user-asish` / `user-mom`. |
| Mock on AWS | `MOCK_ASSUME_MOBILE_DATA=1` (settings, default `0`): the number-verification authorize step treats every client as on mobile data. Logged at startup as `SIMULATION`; refused when `TOWER_ENV=local` and `?as=` is also set (one simulation at a time). Documented in `components/08` §3 and the mock README. |
| Cookie | Binding page `ATB_SESSION_TTL_H` env (default 1, AWS values 24). |
| Cost | Cognito free tier; second AgentCore runtime billed per request; CloudFront/S3 cents. Record in `artifacts/cost.md`. |

## Deliverables

```
docs/architecture/
  components/09-reference-client.md       §6 expanded: endpoint contract, auth, next_step rule, local vs AWS; §2 diagram ref
  components/08-mock-carrier.md           §3: MOCK_ASSUME_MOBILE_DATA
  components/04-consent-and-binding.md    §4: ATB_SESSION_TTL_H
  components/10-scheduler-and-infra.md    §5: new make targets (below)
  deployment-agentcore.md                 second runtime (agent, HTTP), Cognito pool, CloudFront/S3, Lambda URL; the TODO(human) list gains the Cognito steps
  e2e-wiring.md                           §6 contracts: web-chat → agent, agent → Tower (bearer pass-through); §2 Path A gains the web variant
  bind-and-alert-flows.md                 "new" → "exists" per item as it lands; 4.2 #10 dedupe lives in windows.py
  diagrams/gen/gen_extend.py              02-request-path: append the as-built web-chat lane (page → agent → Tower), original cells untouched (same mechanism as the 03/04 branches)
  diagrams/gen/gen_deploy.py              08-agentcore-deployment: Cognito pool, agent runtime, S3/CloudFront, Lambda URL
  diagrams/{02-request-path,08-agentcore-deployment}.drawio   regenerated, never hand-edited
  diagrams/png/…                          regenerated (`make diagrams-png`, needs the drawio CLI; else log TODO(human))
services/ref-client/
  src/ref_client/http.py                  FastAPI app: POST /invocations, GET /healthz, static mount of the web page at /
  src/ref_client/auth.py                  bearer extraction + pass-through (verification is Tower's; the agent only rejects a missing/malformed header)
  Dockerfile                              CMD runs the HTTP app (uvicorn) — the CLI stays available via `python -m ref_client.run`
  README.md                               "As the web chat page" section: endpoints, env, local run, AWS run
  .env.example                            REF_CLIENT_HTTP_PORT, TOWER_URL, BEDROCK_MODEL_ID, WEB_CHAT_BINDING_BASE_URL, COGNITO_* (placeholders)
  tests/test_http.py                      integration: 401 without bearer and no model call; next_step copied verbatim; foreign URL rejected; bearer forwarded unchanged to Tower (fake Tower); privacy sweep on responses and logs
services/web-chat/
  index.html, app.js, styles.css          the page (dark theme, matches the demo UI's palette; no images that need a build step)
  config.js.example                       COGNITO_DOMAIN, CLIENT_ID, REDIRECT_URI, AGENT_URL, BINDING_BASE_URL
  README.md                               run locally, deploy, what it does not do
  tests/test_static.py                    unit: config has no secrets; app.js contains the `/bind/` prefix check; no phone-number regex match in any file
services/mock-carrier/
  src/mock_carrier/settings.py, runtime.py   MOCK_ASSUME_MOBILE_DATA
  tests/test_assume_mobile_data.py        unit: default off; on → authorize succeeds without X-Mock-Client-Id; conflict with ?as= refused
services/binding-page/
  src/binding_page/session.py             ATB_SESSION_TTL_H
  tests/test_session_ttl.py               unit
scripts/
  cognito_user.py                         create | delete | sub ; writes artifacts/cognito-users.json
  aws_seed.py                             --user name=sub mapping (and the json fallback)
deploy/terraform/
  modules/cognito/{main,variables,outputs}.tf   pool, app client (PKCE), hosted-UI domain; outputs pool_id, client_id, issuer, jwks_url, hosted_ui_url
  modules/web_chat/{main,variables,outputs}.tf  S3 bucket (private) + CloudFront (OAC) + Lambda function URL proxy to the agent runtime; outputs page_url, agent_url
  modules/agentcore_runtime/              parameterised for a second runtime (protocol HTTP) — or a sibling module if the existing one is MCP-only; pick the smaller change and say which
  main.tf, variables.tf, outputs.tf       wire the three; Tower's env gets the Cognito issuer/jwks/client id; outputs cognito_*, web_chat_url, agent_url
  envs/*.tfvars.example                   new variables with placeholders
deploy/compose/docker-compose.yml         ref-client exposes :8083 and serves the page; env from .env.example
deploy/helm/ref-client/                   HTTP service + values-kind/eks (ClusterIP; ingress off by default)
mk/aws.mk                                 cognito-users (create asish + mom, write json), web-chat-sync (upload page to S3 + invalidate), web-chat-url (print)
mk/local.mk                               web-chat (open the local page URL)
artifacts/cost.md                         updated
tests/e2e/test_web_chat_story.py          e2e (ENV=local): sign-in stub → "Is my line OK?" → NOT_BOUND + link → bind via simulated phone → ask again → OK; compared to the golden on tool calls + reason codes
docs/submission/product-feedback.md       Cognito ◐, AgentCore Runtime (HTTP) ◐, CloudFront ◐
```

## Steps (in this order; use the subagents)

1. **architect** — docs and diagrams first, nothing else: every file under `docs/architecture/` above, then regenerate: `uv run python docs/architecture/diagrams/gen/gen_extend.py` and `gen_deploy.py`, `uv run python docs/architecture/diagrams/gen/check.py`, `make diagrams-png` if the CLI is present; never hand-edit XML. Then `make docs-check`. Output: the list of doc/diagram changes and the exact endpoint/env/variable names the next steps must use. Stop if any decision above conflicts with a doc you read; write the conflict and two options into the build log and pick the one closest to the doc.
2. **developer** — code in the order: mock flag → session TTL → `ref_client/http.py` + `auth.py` → `services/web-chat` → `cognito_user.py` + `aws_seed.py` → Terraform modules → compose/Helm → make targets. Write each test next to its code (tester reviews, not writes). `uv run ruff format`, `ruff check`, `mypy packages/` clean.
3. **tester** — run `uv run pytest services/ref-client services/web-chat services/mock-carrier services/binding-page -q`, then `make test-unit && make test-integration`, then `make test-e2e ENV=local`. Privacy sweep must pass over the new page, logs and responses. Record counts. Never weaken a test; a red test that encodes the doc stays red and is logged.
4. **deployer** — `make tf-check` (fmt + validate, `-backend=false`; never plan/apply), `helm lint` + `helm template | kubeconform` for `ref-client`, `docker compose config`. Write the `TODO(human)` list in `docs/submission/build-log/20.md` with exact commands: `make ecr-up` → `make push ENV=aws` → `make plan` → `make deploy` → `make cognito-users` → `make seed-aws` → `make web-chat-sync` → `make web-chat-url`; SNS sandbox number verification; Cognito Hosted UI callback URL = the CloudFront URL.
5. **reflect-and-learn** — anything durable (Cognito token quirks, AgentCore second-runtime wiring, CloudFront OAC) into the matching `.claude/skills/*` skill.

## Acceptance

- `components/09` §6, `deployment-agentcore.md`, `e2e-wiring.md` §2/§6 and diagrams 02 and 08 describe the web chat path before any code exists; `make docs-check` clean.
- `POST /invocations` without a bearer → 401 and zero Bedrock calls (asserted with a counting fake); with a bearer, the same bearer reaches the fake Tower unchanged.
- `next_step` in the response is byte-identical to the tool result's; a model reply containing a URL never produces a `next_step`.
- The page refuses to render a `next_step.url` outside `BINDING_BASE_URL/bind/`.
- `MOCK_ASSUME_MOBILE_DATA=1` lets the binding flow complete against the mock with no `X-Mock-Client-Id`; default off; conflict with `?as=` refused.
- `aws_seed.py --user mom=<sub>` writes that `sub` into `Lines` and `Grants`; the local seed is unchanged (`user-mom`).
- `make test-unit && make test-integration` green (or red tests listed by name with the doc clause they encode); e2e local story passes against its golden.
- `make tf-check` clean; `helm lint` clean; `kubeconform` clean.
- Privacy tests: no E.164, no health words, no key in any new file, log line or response.
- `bind-and-alert-flows.md` statuses updated; `build-log/20.md` written with the deferred list.

## Guardrails

- The agent is a client of Tower like any other: it never reads tables, never evaluates policy, never calls the carrier (`components/09` §5).
- No phone number anywhere in the chat path: not in prompts, not in the page, not in logs, not in tests (use the seeded roles).
- The page and the agent trust Tower's `next_step` only; no URL from the model, no URL built client-side.
- Don't touch the demo UI (11), the Alexa+ surface (01), tool shapes (02 §2), or `descriptions.py`.
- No new Python dependency beyond FastAPI/uvicorn (already in the workspace) and boto3 for the script; no JS framework, no bundler.
- No git operations. Final message: files changed (paths), test counts per layer with the command, the TODO(human) list, decisions taken beyond the table above.
