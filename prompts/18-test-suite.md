# 18 — Test suite: unit, integration, end to end (`tests/`, per-package and per-service `tests/`)

> Load `00-conventions.md` first. Depends on: 03–14 (each prompt wrote its own tests; this one makes them one suite with gates, markers, fixtures and reports). Day 14, one day. Nothing new is *tested* here that the component prompts didn't name; what's new is the structure, the coverage gates, the environment matrix, and the reports a judge can read.

## Goal

`make test` runs three layers with clear names and one report; `make test-unit`, `make test-integration`, `make test-e2e` run each alone; the same e2e suite runs against local, EKS and AgentCore by `ENV=`; coverage, privacy, latency and conformance gates are enforced in CI; `artifacts/test-report.md` summarises all of it.

## Read first

- `docs/architecture/testing-and-showcase.md` §1, §3 (the seven layers and their gates), §5
- `docs/architecture/diagrams/06-test-topology.drawio`
- every `tests/` folder written so far (`find . -path '*/tests/*' -name 'test_*.py'`)
- `prompts/00-conventions.md` (privacy invariants as tests)

## Layer definitions (these are the words the README uses)

| Layer | Marker | What | Needs | Gate |
|---|---|---|---|---|
| **Unit** | `unit` | pure code: policy table, phrasing, windows, consent resolve logic, crypto, error map, audit canonical/chain, schemas | nothing (fakes/moto only) | 100 % pass; coverage ≥ 90 % on `packages/`, ≥ 80 % on `services/` |
| **Integration** | `integration` | component pairs over real interfaces: Tower↔consent (DynamoDB Local), Tower↔`CarrierClient`↔mock, Alerts↔mock subscriptions, binding page↔mock auth-code, audit writer↔DynamoDB Local; **conformance** (schemathesis vs vendored specs through `DirectClient` and the fake Gateway); **privacy** (log/result/SMS greps); **latency** (200 calls, p95 gate) | mock + DynamoDB Local containers (testcontainers) | 100 % pass; p95 < 400 ms; zero privacy hits |
| **End to end** | `e2e` | `make demo` transcripts vs golden; showcase targets exit 0; alerts §2.6 sequence; binding §2.4 via headless browser (Playwright) with the simulation param; chaos (mock faults → `STALE_DATA`/`CARRIER_ERROR`, never wrong outcome) | full stack: `ENV=local` (compose) \| `eks` \| `aws` | transcripts match; chaos never produces a wrong outcome |

Nightly only: `GatewayClient` conformance against real AgentCore Gateway (`ENV=aws`), chaos with Lambda cold starts, the kind install.

## Deliverables

```
pyproject.toml            pytest config: markers (unit, integration, e2e, nightly, slow), `--strict-markers`, `-p no:cacheprovider` in CI, testpaths; coverage config with per-path thresholds
conftest.py (root)        `ENV` fixture (local|eks|aws → base URLs from compose, helm outputs, or terraform outputs); `mock_admin` fixture (load scenario, fire event, advance clock, inject fault); `stack` fixture (testcontainers for integration; no-op for e2e against a running env)
tests/
  unit/                   cross-package unit tests that don't belong to one package (e.g. policy↔phrasing template-id agreement, descriptions↔corpus agreement)
  integration/            pairwise tests moved/linked here with the `integration` marker; conformance/; privacy/; latency/
  e2e/                    demo, showcase, alerts, binding (Playwright), chaos; `golden/` transcripts (one set, used by all three ENVs)
  fixtures/               scenarios used by tests (symlink to scenarios/), CloudEvents samples, fake Gateway server
  helpers/                E.164 and health-word regexes in ONE module imported by every privacy test; transcript comparator (tool calls + reason codes; ignores wording and timestamps)
scripts/test_report.py    collects junit XML + coverage + latency + conformance + privacy into artifacts/test-report.md with a layer × result table and links
.github/workflows/
  ci.yml                  push/PR: unit → integration (compose services) → e2e ENV=local; uploads junit, coverage, latency.md, conformance-report.html, test-report.md
  nightly.yml             ENV=aws integration+e2e, kind install, chaos
Makefile                  test (all three, local), test-unit, test-integration, test-e2e (honours ENV), test-nightly, test-report
docs/architecture/testing-and-showcase.md §3   updated to the three-layer vocabulary with the seven sub-kinds listed under them (don't lose the sub-kinds; judges like "conformance" and "chaos" as words)
```

## Steps

1. Inventory every existing test; tag each with exactly one marker; move cross-cutting ones under `tests/`. Package- and service-local tests stay where they are (they're part of the package) but get markers.
2. Root `conftest.py` with the `ENV` fixture and the `mock_admin` fixture; make every e2e test environment-agnostic through them.
3. Coverage thresholds per path; fail CI below them. Exclude generated code and `scripts/`.
4. Playwright test for the binding flow (local only; on EKS/AWS it's a smoke `GET /bind/<token>` = 200).
5. Chaos tests: for each fault kind × each tool, assert the outcome is a refusal with the mapped code, never `ok`/`changed`.
6. `scripts/test_report.py`; `make test-report`; wire into CI artefacts and into `make showcase-artifacts` (16).
7. Run the e2e suite against all three ENVs once; record in `artifacts/test-report.md`.

## Acceptance

- `make test` on a clean machine with Docker: unit < 10 s, integration < 3 min, e2e < 5 min; one `artifacts/test-report.md`.
- Coverage gates met; markers strict (an unmarked test fails collection).
- `make test-e2e ENV=eks` and `ENV=aws` pass against the deployed targets with the same golden set.
- Chaos: zero wrong outcomes across the fault × tool matrix.

## Guardrails

- Don't duplicate component tests into `tests/`; mark and reuse. One source of truth per test.
- No test asserts model wording (reference client or Alexa+). Tool calls, args, reason codes only.
- The privacy regexes live in one helper; a test asserts no other file defines its own.

## Report back

`artifacts/test-report.md`, the test counts per layer, coverage per path, and the e2e timing per ENV.
