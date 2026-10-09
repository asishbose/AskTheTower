# RUN-ALL — build the whole project autonomously

> One prompt that executes `prompts/00` through `prompts/19` in order, without asking anything, and leaves a complete repository: every package, service, chart, Terraform module, Makefile target, test file, document and artefact that the prompts specify. **Verification against live environments is deferred**: nothing is deployed to AWS, nothing is registered with Alexa+, no video is recorded. Tests are *written* in full and *run where they can run offline*; failures are recorded, not fixed by weakening the test.

## Resuming a partial run

Check `docs/submission/build-log.md` and `docs/submission/build-log/NN.md` first: prompts with a ✅ section in the build log are done — **skip them and start at the next step in the table below**. On a machine with Docker, Terraform, Helm and AWS credentials, the "Deferred" column shrinks: run what the environment allows and update the Decisions table's environment-dependent rows accordingly (DynamoDB Local via testcontainers, `docker compose build`, `terraform validate`/`plan`, `helm lint`, `make helm-kind`). Also read `docs/submission/agent-brief.md`, which is the brief for delegated build agents; update its "Environment facts" to the machine you are on before delegating.

## Operating mode

You are a build agent working in the repository root of **Ask the Tower**. Read `prompts/00-conventions.md` and `prompts/README.md` first, then execute the prompts in the order below. Rules for this run:

1. **Never ask a question.** Every choice a prompt leaves open is settled by the Decisions table below; anything not covered there is settled by the most conservative reading of the architecture docs, and written down.
2. **Never stop on a blocker.** If a step cannot be done here (needs AWS credentials, an Alexa+ account, a phone, Docker, the network), write the step as far as it can be written (code, config, script, doc), add a `TODO(human)` entry to `docs/submission/build-log.md` with what is missing and the exact command to run later, and continue.
3. **Never weaken a test to make it pass.** A failing test that encodes the spec stays failing and is logged; a test that is wrong against the docs is fixed against the docs.
4. **Docs stay true.** Any deviation from `docs/architecture/` is applied to the doc in the same change, with a `docs:` line in the build log (rule 5 of 00's definition of done).
5. **No git operations.** After each prompt, append its section to `docs/submission/build-log.md` listing acceptance items as ✅ done / ⏸ deferred / ❌ failing and the files touched; the human reviews and commits.
6. **Product feedback as you go.** For every tool you actually touch in this run (FastMCP, pydantic, schemathesis, uv, Terraform, Helm, …), draft its section in `docs/submission/product-feedback.md` (◐). Sections for tools you could not touch (Alexa+ MCP Toolkit, AgentCore, SNS, EKS) stay ☐ with a one-line "not exercised in the autonomous build".
7. **No secrets, ever.** `.env.example` placeholders only; `gitleaks` must be clean at the end of the run.

## Decisions (pre-made so nothing waits)

| Open point | Decision for this run |
|---|---|
| DynamoDB for tests | `moto` (in-process) when Docker is unavailable; `testcontainers` + DynamoDB Local when it is. Detect with `docker info`; record which. |
| Alexa+ inbound identity (01 §7, spike A) | Bearer JWT; `user_id` = `sub` claim; verification key from `TOWER_JWKS_URL`; local mode accepts `X-Tower-User`. Documented as an assumption in `components/01` §4. |
| AgentCore Gateway tool naming (06, spike B) | `<api>__<operationId>` (e.g. `sim-swap__createCheckSimSwap`); `GatewayClient` reads the real names from `gateway-tools.json` at startup, so the assumption costs nothing. |
| CAMARA meta-release | The most recent meta-release whose specs can be fetched; if the network is unavailable, write the six spec files from the operation tables in `components/05` §2 and `components/08` §1 and mark them `# RECONSTRUCTED — replace with vendored originals` at the top; log it. |
| Mock carrier CIBA | Behind `MOCK_CIBA=1`, implemented. |
| Licence | Apache-2.0. |
| Bedrock model for the reference client | `BEDROCK_MODEL_ID` env, default a Nova Micro id; corpus test skipped (not failed) when no AWS credentials. |
| EKS node type / size | 2 × arm64 `t4g.medium` managed node group; spot off. |
| Terraform state | S3 backend with placeholders in `backend.tf`; `terraform validate` only, never `plan`/`apply`. |
| Helm | `helm lint` and `helm template | kubeconform` only; no cluster. |
| Video | `artifacts/video/script.md` written; recording deferred. |
| Alexa+ registration | `docs/architecture/alexa/registration.md` written as a runbook with the exact steps to take; `simulator-run.md` is a template with the utterance list; feedback section ☐. |
| Statistics on the numbers slide | Not re-verified here; `TODO(human)` in the build log. |
| Items on `docs/pitch-v3-reconciliation.xlsx` | Untouched. Open decisions stay open; nothing from the Discuss/Decline rows is implemented. |

## Execution order and the scope of each in this run

| Step | Prompt | Build | Run | Deferred (logged) |
|---|---|---|---|---|
| 1 | 01 repo scaffold | everything | `uv sync`, `make test` (smoke), `gitleaks` | CI run on a remote (write the workflow) |
| 2 | 03 policy engine | everything | unit tests; `make policy-table` → `artifacts/policy-table.md` | — |
| 3 | 04 specs + mock carrier | everything incl. scenarios | unit + scenario + subscription + attribution + fault tests in-process (ASGI test client); schemathesis if installed | Docker image build if no Docker |
| 4 | 05 consent library | everything | tests on moto / Local | — |
| 5 | 06 carrier client | everything incl. fixtures, fake Gateway | tests against the in-process mock | live Gateway |
| 6 | 07 audit log | everything | tests | Observability trace source |
| 7 | 08 Tower MCP server | everything | tests with in-process mock + moto; `scripts/latency.py` against the in-process stack → `artifacts/latency.md` labelled "in-process, not representative" | Docker image, real latency run |
| 8 | 09 binding page | everything incl. templates | tests (ASGI client); Playwright test written, skipped if no browser | phone run |
| 9 | 10 alerts service | everything | tests with fake carrier + log sender | SNS, real phone |
| 10 | 11 reference client | everything incl. `prompts/ref-client/system.md`, corpus (≥ 40 entries), transcript tooling | corpus test skipped without credentials | Bedrock run, golden transcripts (write them by hand from the policy table — tool calls + reason codes only — and mark `GOLDEN: hand-written`) |
| 11 | 12 compose + demo | everything: compose file, seed, `make demo` wiring, e2e tests | `docker compose config`; `make up && make demo` if Docker | clean-machine run |
| 12 | 02 week-one spikes | the three spike *scripts* and note templates, `scripts/latency.py` | latency harness in-process | Alexa+ access, Gateway, AWS |
| 13 | 13 AWS Terraform + AgentCore | all modules, `GatewayClient` live wiring, KMS impls, `scripts/aws_seed.py`, `tests/aws/` | `terraform fmt`, `terraform validate` (providers mocked / `-backend=false`) | plan/apply, latency-aws, cost |
| 14 | 14 Helm + EKS | all charts, umbrella, eks module, `render_values.py`, `k8s_seed.py` | `helm lint`, `helm template`, `kubeconform` if installed | kind, EKS |
| 15 | 15 Alexa+ surface | runbook, templates, `auth.py` final per Decisions, README section | — | registration, simulator, recording |
| 16 | 18 test suite | markers, root conftest, `tests/{unit,integration,e2e}` layout, Playwright/chaos tests, `scripts/test_report.py`, CI + nightly workflows | `make test-unit`; `make test-integration` where in-process; `make test-report` | e2e against eks/aws |
| 17 | 19 Makefile | `mk/*.mk`, `make help`, `docs-check`, `secrets-check`, `sbom`/`scan` targets | `make help`, `make docs-check`, `make secrets-check`, `make lint`, `make typecheck` | `scan` if no scanner |
| 18 | 16 showcase artefacts | `script.md`, `docs/submission/checklist.md`, `deck-consistency.md`, `make showcase-artifacts` | `make showcase-artifacts` for the generated ones | video, screenshots, clean-run timing |
| 19 | 17 submission README + prior art | root `README.md` (full structure), `docs/prior-art.md`, `docs/submission/form.md`, diagram PNGs (if a draw.io exporter is available; else log), LICENSE, CONTRIBUTING, SECURITY, Open Source mini sections | `make docs-check`, `make deck-check` (against the PPTX in `docs/Decks/` if a reader is available; else log) | tag (leave untagged; humans tag after verification) |

Prompts 02 and 15 are placed where their outputs are first needed in this mode; their live parts are the first items in the build log's deferred list.

## What this run must leave behind

- A repository where `uv sync && make test-unit` passes, `make help` lists every target in `docs/architecture/components/10` §5, and `make docs-check` and `make secrets-check` are clean.
- Every file named in the Deliverables block of every prompt exists (a `scripts/check_deliverables.py` that parses those blocks and reports missing paths — write it in step 1 and run it last; its output is the last section of the build log).
- `docs/submission/build-log.md`: per prompt — what was built, what ran, what passed, what failed (test names), what was deferred with the exact command to run, and every decision taken beyond the table above.
- `docs/submission/product-feedback.md` with ◐ sections for every tool touched.
- The build log's final section: the deferred list in full, so the human run starts from it.

## Final report (the last message of the run)

Five lines: test counts per layer (passed / failed / skipped), the missing-deliverables count from `check_deliverables.py`, the number of `TODO(human)` items, the first three of them, and the list of files touched.
