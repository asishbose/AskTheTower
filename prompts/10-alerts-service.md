# 10 — Alerts service (`services/alerts`)

> Load `00-conventions.md` first. Depends on: 03, 05, 06, 07; mock from 04; Tower stub endpoint from 08. Day 8. The proactive path — the part Alexa+ can't do.

## Goal

Webhook receiver + poller + sender, one evaluation function for both triggers, window arithmetic in `Watches.last_state`, re-resolve before send, escalation, rate limit, quiet hours, SNS on AWS / log + optional SMS gateway locally. Phone buzzes on camera.

## Read first

- `docs/architecture/components/06-alerts-service.md` — all of it
- `docs/architecture/e2e-wiring.md` §4 (Path B), §2 (Carrier → Alerts, Alerts → SNS edges)
- `docs/architecture/diagrams/03-proactive-path.drawio`
- `docs/architecture/components/03-policy-engine.md` §3 thresholds table (windows and escalation live here), §4 (SMS forms)
- `docs/architecture/components/10-scheduler-and-infra.md` §3 (schedules → `profile`)

## Deliverables

```
services/alerts/
  src/alerts/
    handler.py         Lambda entry: routes by event source — API Gateway (hooks), EventBridge Scheduler ({profile}), internal HTTP (subscribe/unsubscribe from Tower's watch_line)
    local.py           local runner: FastAPI for hooks + internal API, and an in-process scheduler calling the same poll function on the 10 §3 cadences (scaled by ALERTS_CLOCK_SCALE for demos)
    hooks.py           POST /hooks/{kind}/{sink_token}: validate CloudEvent against vendored schema; token → line_id (unknown → 200, logged, counted); idempotent on event_id (DynamoDB conditional put in a small `Events` dedupe table or a TTL attribute on Watches — choose and document)
    evaluate.py        evaluate(line_id, trigger, now): fetch facts (CarrierClient, proactive profile) → policy.evaluate_line / evaluate_reachability → diff vs last_state (06 §2) → windows (06 §2: continuous-false, reset on any true; stored in last_state.unreachable_since) → decision {notify: bool, reason, recipients}
    windows.py         pure functions over last_state + now for UNREACHABLE_ALERT per profile and daytime window for care
    send.py            re-resolve grant (06 §4) → SUPPRESSED_REVOKED if gone; rate limit per (line, reason, 6 h) via last_state.last_alert_at; recipients per 06 §3 incl. the SIM-swap rule (never the swapped line; backup phone if any); SNS publish on AWS, log + optional webhook locally; retry once → ALERT_FAILED
    escalation.py      ack tracking (SMS reply "OK" via SNS inbound topic, or link tap); ESCALATE_NEXT 15 min → next recipient; state in last_state; an ack or cancel from a line within ACK_DISTRUST (24 h) of its own SIM swap is ignored, audited ACK_IGNORED_SWAPPED_LINE, escalation continues, and the watcher's next message says so (06 §3)
    subscriptions.py   subscribe(line_id, kinds) / unsubscribe via CarrierClient; sink URL per line with an unguessable token stored on the Watch; expiry watchdog in the poller (06 §8)
    templates.py       imports tower_policy.phrase(form="sms"); nothing else
    internal_api.py    POST /internal/watch {line_id, enable, profile} — called by Tower's watch_line; bearer-protected
  tests/
    test_same_decision.py   event and poll with identical facts → identical decision, at most one alert
    test_windows.py         transplant: 19 min → none; 20 → alert; true at minute 10 resets; care: 4 h inside 08–22 only
    test_revoke_race.py     revoke between evaluate and send → SUPPRESSED_REVOKED row, no send
    test_sim_swap_recipients.py  swapped line excluded; backup phone used; watcher always
    test_rate_limit.py      second identical change in 6 h → audited, not sent
    test_hooks.py           unknown token → 200 no state; bad payload → dropped + counted; duplicate event_id → dropped
    test_escalation.py      no ack in 15 min → second recipient; ack → stop; ack from the swapped line within 24 h → ignored + audited, escalation continues; same ack from the watcher → accepted
    test_failures.py        06 §8 table: 3 poll misses → CARRIER_ERROR audit, no alert; SNS fail → retry → ALERT_FAILED → next recipient
    test_privacy.py         every SMS body produced in the suite: no E.164, no health words
  Dockerfile, README.md, .env.example (ALERTS_MODE=lambda|local, SNS_TOPIC_ARN, SMS_GATEWAY_URL, ALERTS_CLOCK_SCALE, HOOKS_BASE_URL, INTERNAL_BEARER, CARRIER_*, DYNAMO_ENDPOINT)
```

## Steps

1. `evaluate.py` + `windows.py` pure-ish and tested with a fake `CarrierClient` first.
2. Hooks with CloudEvents validation against the vendored schema; dedupe.
3. `send.py` with the recipient rules; SNS behind a Protocol with a log implementation.
4. Subscriptions + internal API; wire Tower's `watch_line` stub to it (update 08's Protocol impl).
5. Local runner with the scaled scheduler; the mock clock and `ALERTS_CLOCK_SCALE` together make "20 minutes" take 20 seconds in the demo.
6. `make showcase-alerts`: §2.6 script; locally the "phone" is the log plus the optional SMS gateway webhook.

## Acceptance

- `testing-and-showcase.md` §2.6 runs locally end to end with the mock: enable watch → admin `sim_swap` on Mom → alert logged within 5 s → repeat within 6 h → audited only → revoke → `SUPPRESSED_REVOKED` → transplant: 20 min dark → first text; +15 min → second contact.
- Audit rows for every branch, with `actor="system:alerts"` and `trigger ∈ {event, poll}`.
- Same `tower_policy` version hash in Alerts' rows as in Tower's (shared package proven).

## Guardrails

- No decision in this service that isn't `tower_policy` + the window/recipient tables in 06. No model.
- A failure to observe is never a change (06 §8). No alert on absence of data.
- The swapped line is never texted after a SIM swap. The test is the guarantee; keep it.

## Report back

The showcase transcript (log lines) for §2.6, the dedupe design you chose, and how `ALERTS_CLOCK_SCALE` interacts with the mock clock (one paragraph for the README).
