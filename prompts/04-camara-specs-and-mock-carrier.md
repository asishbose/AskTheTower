# 04 — CAMARA specs + mock carrier (`specs/camara`, `services/mock-carrier`)

> Load `00-conventions.md` first. Depends on: 01. Days 2–3. This is the fixture everything else tests against; build it well.

## Goal

A CAMARA-conformant carrier in one container: six APIs, OAuth, subscriptions with CloudEvents, a controllable clock, a scenario engine, and an admin API — deterministic, with conformance tests generated from the vendored specs.

## Read first

- `docs/architecture/components/08-mock-carrier.md` — all of it
- `docs/architecture/components/05-carrier-gateway.md` §2 (which operations are used), §5 (error mapping the mock must make testable)
- `docs/architecture/diagrams/05-mock-carrier.drawio`
- `docs/architecture/components/04-consent-and-binding.md` §1 (why Number Verification needs the client-id simulation)

## Part 1 — vendor the specs

```
specs/camara/
  README.md              meta-release name/date, per-file source URL + commit, the exact version segment of each path
  sim-swap.yaml
  sim-swap-subscriptions.yaml
  call-forwarding-signal.yaml
  number-verification.yaml
  device-reachability-status.yaml
  device-reachability-status-subscriptions.yaml
  cloudevents/ (if the subscriptions specs reference an external schema, vendor it)
```

Pick **one** CAMARA meta-release and take every file from it. Record the choice in the README. Do not hand-edit a spec; if one needs a fix to be served by FastAPI, patch at load time in code and document the patch.

## Part 2 — the mock

```
services/mock-carrier/
  src/mock_carrier/
    app.py               FastAPI; mounts routers; serves /openapi.json merged from the vendored specs (not FastAPI's generated one); /docs
    specs.py             loads specs/camara/*.yaml; exposes path+version per operation so routers never hard-code a path
    oauth.py             /oauth2/token (client credentials, scopes per API), /authorize + /token (auth code; network-auth simulated via X-Mock-Client-Id), /bc-authorize (CIBA; optional, behind MOCK_CIBA=1)
    clock.py             controllable clock; all timestamps derive from it
    state.py             lines, subscriptions, faults, delivery log; in memory; loaded from scenarios/*.yaml
    scenarios.py         YAML loader; timeline events fire on advance
    routers/
      sim_swap.py        check (maxAge honoured, >2400 h → 400 INVALID_ARGUMENT), retrieve-date (nullable)
      sim_swap_subs.py   POST/GET/DELETE; CloudEvents on sim_swap events
      call_forwarding.py unconditional-call-forwardings → {active}; call-forwardings → {forwardingTypes[]}
      number_verification.py  verify (requires auth-code token bound to a client id matching the line's mobile_data_client_ids; else 422 UNIDENTIFIABLE_DEVICE), device-phone-number
      reachability.py    retrieve → {reachable, connectivity, lastStatusTime}
      reachability_subs.py
      admin.py           /_admin/* per 08 §3; enabled only when MOCK_ADMIN=1
    errors.py            CAMARA error envelope {status, code, message}; one exception class per code in 08 §1
    webhooks.py          CloudEvents sender; retry 3× with backoff; delivery recorded in state
  scenarios -> ../../scenarios (symlink or copy at build; `scenarios/demo.yaml` is the canonical file at repo root)
  tests/
    test_conformance.py  schemathesis against the running app for every operation, incl. error envelopes
    test_scenario.py     load demo.yaml; advance 12 min; check → swapped true; retrieve-date → expected ts; advance to 20 min → cf active
    test_subscriptions.py create → fire admin event → CloudEvent at a local sink with the right type and subscriptionId; expiry; delete
    test_attribution.py  verify: no header → 422; wrong id → 422; right id → verified
    test_faults.py       faults {timeout,1} → next call > 400 ms; {500,2} → two 5xx then clean; {429,1}
    test_determinism.py  same scenario + same admin calls, twice → identical /_admin/state
  Dockerfile, README.md, .env.example (MOCK_ADMIN, MOCK_JITTER_MS, MOCK_CIBA, MOCK_PORT, MOCK_TLS_CERT/KEY)
scenarios/demo.yaml      exactly 08 §2 — both lines, both timeline events on +16135550101
scenarios/care.yaml      Mom's line going unreachable for 4 h in a daytime window
scenarios/transplant.yaml 20 min dark, then reachable at minute 10 in a second variant
```

## Steps

1. Spec loader + `/openapi.json` first; `schemathesis` must be able to point at the running mock and find every operation. Routers register their path from the loader.
2. OAuth: a client registry in config (`clients.yaml`: id, secret, allowed scopes, `mobile_data_client_ids` are on lines, not clients). Tokens are signed JWTs with scope and, for auth-code, the attributed client id.
3. Clock + state + scenario loader; timeline fires on `advance`.
4. Routers, one at a time, each with its conformance run green before the next.
5. Subscriptions + CloudEvents sender; test with a sink inside the test process.
6. Admin API; faults; determinism test last.
7. `make showcase-mock` = start the mock with `MOCK_ADMIN=1`, print the §7 script with curl lines ready to paste.

## Acceptance

- `schemathesis run --checks all` against every vendored spec passes against the running mock (CI).
- The §2.8 showcase script works as written: `check` false → advance 12 min → true; `retrieve-date` moves with the clock.
- `/openapi.json` diffed against the vendored specs shows only the `/_admin` and `/oauth2` additions.
- `artifacts/conformance-report.html` is produced by `make test` (schemathesis report or equivalent).
- Image < 200 MB; starts in < 2 s; `GET /healthz`.

## Guardrails

- The mock issues credentials; it never consumes any. No calls out except to subscription sinks.
- No randomness unless `MOCK_JITTER_MS` is set. No wall-clock reads outside `clock.py`.
- `/_admin` and `X-Mock-Client-Id` are simulation aids; every README mention says so in one line.
- Don't model carriers' quirks. Spec-conformant, not realistic.

## Report back

Conformance summary (operations × checks), the diff of `/openapi.json` vs specs, startup time, and any spec construct you had to patch at load time (with the patch).
