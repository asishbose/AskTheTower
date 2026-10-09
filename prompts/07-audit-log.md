# 07 — Audit log (`packages/tower-audit`)

> Load `00-conventions.md` first. Depends on: 05 (store, `line_id`). Day 4, half a day.

## Goal

Append-before-release audit rows, hash-chained per line, readable by the line-holder, verifiable, trimmable — and containing nothing a judge could call a leak.

## Read first

- `docs/architecture/components/07-audit-log.md` — all of it
- `docs/architecture/components/02-tower-mcp-server.md` §2 step 5, §6 last row (no audit → no answer)
- `docs/architecture/components/03-policy-engine.md` §4 (`SUPPRESSED_REVOKED`, `ALERT_FAILED` are audit-only)
- `docs/architecture/components/10-scheduler-and-infra.md` §2–3 (reconciliation Lambda, nightly)

## Deliverables

```
packages/tower-audit/
  src/tower_audit/
    __init__.py       append, verify, trim, recent_checks, AuditRecord
    record.py         AuditRecord — exactly 07 §2; canonical JSON (sorted keys, RFC 3339 Z, no floats) for hashing
    chain.py          prev_hash lookup (last row per line, cached per process per line *only within one append*), hash computation, trimmed_at marker (signed with the HMAC key)
    writer.py         append(record) -> AuditRecord: conditional PutItem on `ts#seq` uniqueness; retries seq collision once; raises AuditWriteFailed — callers must treat that as "do not respond"
    reader.py         recent_checks(line_id, since) -> {by_actor: {actor: n}, outcomes: {ok: n, changed: n, refused: n, suppressed: n}, last_at}; list_for_line(line_id, viewer_user_id) — viewer must own the line (07 §4 "never")
    verify.py         verify(line_id) -> VerifyResult{ok, rows, trimmed, first_bad_ts|None}
    trim.py           trim(line_id, before) — re-anchors per 07 §5; TTL does the deletion, trim only writes the marker
    reconcile.py      nightly: for each trace id in the last 24 h with a tool call, assert an audit row exists → raise and emit a metric on any miss (traces source is pluggable; local = a JSONL file)
  tests/
    test_append_release.py   simulate crash between decision and response (a callback hook); on restart the row exists and no response object was produced
    test_chain.py            append 5; tamper row 3 in the table; verify names ts of row 3
    test_trim.py             append 10; trim before row 6; verify ok with trimmed=True
    test_content.py          every stored field scanned: no `\+?\d{10,15}`; message_ref ∈ known template ids; no free text fields
    test_reader_scope.py     watcher cannot list the watched line's audit; owner can; recent_checks aggregates match
    test_reconcile.py        delete a row behind a trace → reconcile raises
  README.md
```

## Steps

1. `AuditRecord` with a `canonical()` method; property test that `canonical()` is stable under field reordering.
2. Writer with the conditional put and seq handling; the "append then callback then return" shape so the crash test is honest.
3. Chain + verify + trim.
4. Reader with the ownership check — the function signature takes `viewer_user_id` and refuses rather than relying on callers.
5. Reconcile with a file-backed trace source for local; the Observability-backed one is a stub prompt 13 fills.

## Acceptance

- Crash test passes: no row ⇒ no response; row ⇒ response.
- Tamper test names the exact row.
- `recent_checks` output for the seeded demo after prompt 08's showcase matches the sentence in 07 §4 (counts by actor and outcome; no second-precision timestamps in the voice form — that's phrasing's job, but the reader returns only `last_at` rounded to the minute).

## Guardrails

- No facts in the row beyond reason codes (07 §3). No message bodies. No numbers.
- The writer never swallows `AuditWriteFailed`. Callers decide, and the rule is: refuse.

## Report back

The canonical JSON of one row, the verify output after tampering, and the trace-source interface you left for 13.
