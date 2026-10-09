# 08 — Tower MCP server (`services/tower-mcp`)

> Load `00-conventions.md` first. Depends on: 03, 05, 06, 07; mock from 04 running. Days 5–6. This is the thing Alexa+ connects to — the centre of the submission.

## Goal

Three tools over Streamable HTTP, the `ToolResult` envelope, the refusal paths, audit-before-response, and a measured p95 against the mock written to `artifacts/latency.md`.

## Read first

- `docs/architecture/components/02-tower-mcp-server.md` — all of it
- `docs/architecture/components/01-alexa-surface.md` §2 (tool descriptions — copy them verbatim; they are the voice UX), §3 (result shaping)
- `docs/architecture/e2e-wiring.md` §3 (Path A, step by step), §2 (Alexa+ ↔ Tower edge)
- `docs/architecture/diagrams/02-request-path.drawio`
- `docs/architecture/components/04-consent-and-binding.md` §6; `07-audit-log.md` §4 (`watch_line(enable=null)` facts)
- `docs/architecture/spikes/A-alexa-plus-toolkit.md` (identity shape, if known)

## Deliverables

```
services/tower-mcp/
  src/tower_mcp/
    server.py          FastMCP app; Streamable HTTP; /healthz; auth middleware → user_id (bearer per spike A; local: static bearer + X-Tower-User when TOWER_ENV=local)
    schemas.py         ToolResult {summary, facts, reason_codes, next_step{kind: none|call_carrier|bind_line|ask_consent, ...}, checked_at}; per-tool Facts shapes (02 §2, 01 §3)
    deps.py            wiring: thresholds, CarrierClient via make_client, consent store, audit writer, cipher; built once at startup
    tools/
      line_is_ok.py    exactly 02 §2: resolve → (refuse) → facts from Watches.last_state if a Watch exists and it is within FRESH (10 min), else parallel sim_swap_check(72h)+call_forwarding with asyncio.gather, 300 ms each → evaluate_line → audit.append(source=watch|carrier) → ToolResult. STALE_DATA path uses Watches.last_state when the live call times out.
      is_reachable.py  one call; evaluate_reachability
      watch_line.py    enable true/false → upsert Watch + call alerts.subscribe/unsubscribe (an HTTP call to the Alerts service's internal endpoint; prompt 10 provides it — stub it behind a Protocol now); enable null → status facts incl. grants + recent_checks
    descriptions.py    the three descriptions from 01 §2, verbatim, as the single source for FastMCP registration and for the corpus test in 11
    next_step.py       builds next_step: bind_line → create_bind_token + BINDING_BASE_URL; call_carrier → CARRIER_SUPPORT_NUMBER from config (a public number, allowed)
    errors.py          every exception → a refusal envelope with the right code; never a stack trace or carrier text in the result
  tests/
    test_envelope.py       every tool, every reason code → valid ToolResult; summary non-empty; facts booleans/timestamps only
    test_paths.py          Path A against the mock: seeded → OK; with a fresh Watch → answered from stored state, zero carrier calls (count via the mock's /_admin/state), audit source=watch; with a Watch older than FRESH → live call; admin sim_swap → SIM_SWAPPED_RECENT with the right {time}; cf_set → CALL_FORWARDING_SET; unbound alias → NOT_BOUND + next_step.bind_line URL; revoked alias → NO_CONSENT
    test_audit_first.py    inject AuditWriteFailed → tool returns SERVICE_UNAVAILABLE refusal; crash hook between audit and return → row exists, no result
    test_failures.py       02 §6 table: consent store down → SERVICE_UNAVAILABLE; carrier timeout with Watch → STALE_DATA + last-known; without → CARRIER_ERROR
    test_privacy.py        capture all results + logs for the suite; grep E.164; grep carrier error strings from the mock's envelopes
    test_descriptions.py   descriptions registered == descriptions.py == 01 §2 text in the doc (parse the markdown block; fail if they drift)
    test_latency.py        200 calls per tool via scripts/latency.py against the mock; p95 < 400 ms gate; writes artifacts/latency.md
  Dockerfile, README.md, .env.example (TOWER_ENV, TOWER_BEARER, CARRIER_*, DYNAMO_ENDPOINT, BINDING_BASE_URL, CARRIER_SUPPORT_NUMBER, ALERTS_INTERNAL_URL)
```

## Steps

1. Server + auth + `/healthz`; MCP Inspector lists three tools with the verbatim descriptions.
2. `line_is_ok` end to end against the mock with the seeded scenario; then the refusal branches.
3. `is_reachable`; `watch_line` with the Alerts stub.
4. Audit-first and failure tests.
5. Latency: reuse `scripts/latency.py` from spike C; write the p50/p95/p99 table per tool into `artifacts/latency.md` with the date, machine, and mock version. Keep the first number even if it's bad — it's the baseline.
6. `make showcase-tower`: starts mock + DynamoDB Local + Tower; prints the §2.2 script with Inspector URL and the three admin curl lines.

## Acceptance

- `testing-and-showcase.md` §2.2 script runs as written.
- p95 < 400 ms across 200 calls per tool on the live path, and the stored-state path reported separately (expect < 50 ms), both in `artifacts/latency.md`. If not met: the report says where the time goes (per-step timings are logged at debug with `line_id` only).
- `test_descriptions.py` guards the doc ↔ code drift.
- The container runs with only env config; `docker run` + Inspector works.

## Guardrails

- No model, no LLM SDK import, in this service. A test asserts `boto3`'s Bedrock client is never constructed and no `anthropic`/`openai`/`strands` import exists.
- `summary` only from `tower_policy.phrase`. No string formatting of facts in this service.
- No phone number in any result, including `next_step` (the carrier support number is config, not a line).
- `watch_line` makes no carrier *check* (02 §2).

## Report back

`artifacts/latency.md`, the Inspector tool listing, one full `ToolResult` per reason code (redacted), and the identity assumption you coded (with the spike note it rests on).
