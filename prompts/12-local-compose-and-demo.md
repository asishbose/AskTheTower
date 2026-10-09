# 12 — Local compose + `make demo` end to end (`deploy/compose`)

> Load `00-conventions.md` first. Depends on: 04–11. Days 9–10. The reproducibility claim: a judge clones, runs two commands, sees the transcripts the video shows.

## Goal

`make up && make demo` on a clean machine, in under five minutes including image builds. Every showcase target works locally. The end-to-end test layer is green in CI.

## Read first

- `docs/architecture/components/10-scheduler-and-infra.md` §1 (local column), §5 (targets)
- `docs/architecture/e2e-wiring.md` §7 (environments), §8
- `docs/architecture/testing-and-showcase.md` §3 (layers), §4 (order), §6 (artefacts)
- `docs/architecture/diagrams/06-test-topology.drawio`

## Deliverables

```
deploy/compose/
  docker-compose.yml     services: dynamodb-local, mock-carrier (MOCK_ADMIN=1), tower-mcp, binding-page (BIND_ADMIN=1), alerts (ALERTS_MODE=local), ref-client (profile: tools); healthchecks; depends_on with conditions; one network; ports documented
  .env.example           every variable, with the local defaults that make the demo work without edits
  seed/                  seed.py: ensure_tables; create users asish+mom; bind both lines via the mock's auth-code flow with the simulated client ids; grant watch "mom" → asish; load scenarios/demo.yaml; print the state
  logs/                  bind-mounted; the privacy grep scans it after `make demo`
Makefile                 real implementations of: up (build+up+wait healthy+seed), seed, demo, test (adds the e2e layer when the stack is up), showcase (ordered), down (compose down -v)
tests/e2e/
  test_make_demo.py      runs `make demo` as a subprocess; compares transcripts to golden (tool calls + reason codes)
  test_showcase_order.py each showcase target exits 0 against the running stack
  test_privacy_logs.py   grep deploy/compose/logs/** after the run
scripts/clean_machine.sh  a Docker-in-Docker (or a fresh VM) run of `time make up && make demo`; output captured to artifacts/clean-run.txt
```

## Steps

1. Compose with healthchecks; `make up` blocks until all healthy, then seeds. Seed is idempotent.
2. `make demo` wraps `ref-client demo`, with the mock admin and clock calls issued by the demo script itself (not by hand).
3. Wire the SMS log sink so the alerts showcase's "phone buzz" is a visible log line, and document the optional free SMS-gateway webhook for rehearsal.
4. `make showcase` runs §4 order 1–9 with a pause prompt between steps ("press enter for step 4: moment 1").
5. CI: a job that runs `make up && make test && make down` (compose in GitHub Actions). Latency and e2e results uploaded as artefacts.
6. `scripts/clean_machine.sh` once; keep its output.

## Acceptance

- Fresh clone, Docker only: `make up && make demo` < 5 min wall clock, transcripts match golden.
- `make showcase` completes 1–9 locally (steps 4–6 via the reference client here; Alexa+ is prompt 15).
- `artifacts/clean-run.txt` exists with timing.
- `make down` leaves no containers, volumes, or networks.

## Guardrails

- No manual steps between `make up` and `make demo`. If one is needed, that's a bug.
- Compose is the demo environment, not a second architecture: same images, same env var names as AWS, only values differ (10 §1).

## Report back

Timing from the clean run, the compose topology (one screenful), and anything that needed a manual step and how you removed it.
