# 05 — Consent library + store (`packages/tower-consent`)

> Load `00-conventions.md` first. Depends on: 01. Day 3. The binding *page* is prompt 09; this is the library and tables both Tower and Alerts use.

## Goal

The six DynamoDB tables, the crypto helpers (`line_id` HMAC, `msisdn_enc` KMS/local envelope), and the one hot-path function `resolve(user_id, line)`; plus write helpers the binding page and `watch_line` need.

## Read first

- `docs/architecture/components/04-consent-and-binding.md` §3 (grants), §4 (store), §5 (resolve), §7 (tests)
- `docs/architecture/components/06-alerts-service.md` §7 (`Watches.last_state` shape)
- `docs/architecture/e2e-wiring.md` §2 (what crosses the Tower → DynamoDB edge), §6 (`ConsentView`, `Watch`)
- `docs/architecture/components/10-scheduler-and-infra.md` §2 (table list, TTL on `BindTokens`, PITR on `Audit`)

## Deliverables

```
packages/tower-consent/
  src/tower_consent/
    __init__.py        resolve, ConsentView(+line_id), stores, crypto, errors
    crypto.py          LineIdHasher (HMAC-SHA256 over E.164, key from KMS-backed secret or local env), MsisdnCipher (KMS envelope on AWS; AES-GCM with a local key when TOWER_ENV=local). Both behind a Protocol so tests use the local impl.
    tables.py          table names + key schemas + TTL/PITR flags as data — Terraform (13) and DynamoDB Local setup read this one file
    models.py          User, Line, Grant, Watch (incl. last_state), BindToken — pydantic; `alias` validated: lowercase, ≤ 24 chars, no digits
    store.py           thin DynamoDB wrapper (boto3): get/put/query/update with conditional writes; `ensure_tables()` for Local
    resolve.py         resolve(user_id, line) -> ResolvedConsent {view: ConsentView, line_id: str|None}; exactly one GetItem or one Query
    grants.py          grant(line_id, grantee_user_id, kind, alias), revoke(...), list_grants(line_id), list_granted_to(user_id); alias collision rejected at grant time
    bind.py            create_bind_token(user_id) → token (10-min TTL), consume_bind_token(token, user_id), bind_line(user_id, e164, method, carrier_hint) → Line (idempotent on line_id; refuses if owned by another user)
    watches.py         upsert_watch, get_watch, list_watches_by_profile, update_last_state (conditional on `at`)
  tests/
    conftest.py        DynamoDB Local via testcontainers (or moto if Local is unavailable in CI — document which)
    test_resolve.py    self → owner; alias → grant kind; revoked → none; unknown alias → bound False; exactly one call (count via a boto3 event hook)
    test_grants.py     grant/revoke/flip; alias collision; grant to self rejected; "owner" not grantable
    test_bind.py       token reuse / expiry / other user → refused; rebind same number same user idempotent; other user → refused
    test_crypto.py     HMAC stable across processes with same key; cipher round-trips; ciphertext differs per call; decrypt never logs
    test_privacy.py    dump every table after the suite; grep `\+?\d{10,15}` → nothing except inside `msisdn_enc` ciphertext (which must not match either)
  README.md
```

## Steps

1. `tables.py` first — it is the contract with Terraform. Six tables, keys as 04 §4, GSI `Grants.by_grantee` (`grantee_user_id` → `line_id#grant`) for `list_granted_to` and the alias lookup.
2. Crypto with the local implementation; the KMS implementation is a thin class that prompt 13 wires in.
3. `resolve`: `"self"` → `Query Lines.by_owner` (GSI) limit 1; alias → `Query Grants.by_grantee` with filter `alias == line and revoked_at absent`. One call either way. Return `grant="none"` rather than raising.
4. Writes with conditional expressions: bind refuses if `owner_user_id` differs; grant refuses if `(grantee, alias)` exists unrevoked.
5. `ensure_tables()` for Local, driven by `tables.py`, used by compose and tests.

## Acceptance

- Tests green against DynamoDB Local; `resolve` proven to be a single request in both branches.
- `uv run python -m tower_consent.tables --terraform` prints the table definitions as HCL-ready JSON (prompt 13 consumes it).
- A grant then revoke makes `resolve` flip to `none` on the next call with no cache.

## Guardrails

- No phone number as a key, in a GSI, or in a log. `Line.msisdn_enc` only.
- No caching layer. The hot path is one read; caching would make revocation lie.
- `revoke` by voice does not exist here or anywhere (04 §3).

## Report back

Table definitions as printed, the request-count proof for `resolve`, and the moto-vs-Local decision for CI.
