# 09 — Binding page (`services/binding-page`)

> Load `00-conventions.md` first. Depends on: 05, 06; mock from 04. Day 7. Small web app; the demo's first screen.

## Goal

The one tap: open a link on the phone over mobile data, Number Verification asserts the number, the line is bound. Then grants, revocation, the resident's own audit view, and a tiny admin view for the showcase. Runs as a container locally and as a Lambda on AWS.

## Read first

- `docs/architecture/components/04-consent-and-binding.md` §1–3, §6–8
- `docs/architecture/e2e-wiring.md` §5 (Path C), §2 (Phone ↔ Binding page edge)
- `docs/architecture/diagrams/04-binding-flow.drawio`
- `docs/architecture/components/08-mock-carrier.md` §3 (`X-Mock-Client-Id` simulation)
- `docs/architecture/components/07-audit-log.md` §4 (what the page shows)

## Deliverables

```
services/binding-page/
  src/binding_page/
    app.py             FastAPI + Jinja; Mangum adapter for Lambda; /healthz
    routes/
      bind.py          GET /bind/{token} → page ("turn Wi-Fi off, tap Verify"); POST /bind/{token}/verify → start carrier auth-code via CarrierClient (DirectClient locally; Gateway on AWS); GET /bind/callback → exchange code → number_verify → bind_line → "Line connected"
      grants.py        GET /me → my lines, my grants given/received, invite code; POST /grants {invite_code, kind, alias}; POST /grants/{id}/revoke
      audit.py         GET /me/lines/{line_id}/audit → list + chain status (owner only)
      admin.py         GET /_admin/tables (local only, MOCK_ADMIN-style flag) — the showcase's "show the tables" view, numbers redacted by construction (they're never in the tables)
    invite.py          invite code: short, 24 h TTL, maps to user_id; stored in BindTokens-style table with a `kind` attribute
    mobile_data.py     local simulation: a `?as=phone-asish` query param on the bind page sets X-Mock-Client-Id on the carrier call; on AWS this module is a no-op and the carrier's network attribution does the work. One place, clearly labelled.
    templates/         bind.html, connected.html, refused.html, me.html, audit.html — plain, phone-width, no JS framework
  tests/
    test_bind_flow.py        token → page → verify with right client id → Line exists; "Wi-Fi on" simulation (no client id) → refused page, nothing stored
    test_tokens.py           reuse / expiry / wrong user → 4xx, nothing stored
    test_grants.py           bind as Mom; invite as Asish; grant watch alias "mom"; resolve flips; revoke; flips back; alias collision → 409
    test_audit_view.py       owner sees rows + chain ok; watcher gets 403 for the watched line
    test_privacy.py          render every page for the seeded state; grep E.164 → only the masked form "•••• 0101" the connected page shows (last four digits allowed by the conventions)
    test_lambda.py           Mangum event round-trip for GET /bind/{token}
  Dockerfile, README.md, .env.example (TOWER_ENV, CARRIER_*, DYNAMO_ENDPOINT, BASE_URL, SESSION_SECRET)
```

## Steps

1. Token page + verify + callback against the mock, with the local simulation param. Prove refusal without the client id.
2. Session: the callback must know which `user_id` started the flow — sign it into the OAuth `state`.
3. `/me`, invites, grants, revoke.
4. Audit view wired to `tower_audit.list_for_line` with the owner check.
5. Admin table view for the showcase; off unless `BIND_ADMIN=1`.
6. `make showcase-binding`: prints a QR code (terminal) for `BASE_URL/bind/<fresh token>?as=phone-asish` and the §2.4 script.

## Acceptance

- `testing-and-showcase.md` §2.4 script runs from a phone on the same Wi-Fi against the local stack (simulation on) and from a laptop browser.
- Nothing is typed by the user at any point in the bind flow — a test asserts the pages have no `<input type="tel">` or free-text inputs on the bind path.
- Revocation is page-only; there is no revoke route callable without a session.

## Guardrails

- The page never displays or accepts a full phone number. Masked last-four on "connected" only.
- The simulation param is rejected unless `TOWER_ENV=local`; on AWS the module is inert and a test proves the param is ignored.
- No revoke by voice, no revoke via API without the page session (04 §3).

## Report back

Screenshots of the five pages on a phone, the OAuth `state` design, and the AWS-vs-local behaviour of `mobile_data.py` in two sentences for the slide note.
