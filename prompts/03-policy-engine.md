# 03 — Policy engine (`packages/tower-policy`)

> Load `00-conventions.md` first. Depends on: 01. Day 1, ~half a day. Pure code; no I/O.

## Goal

The one package both Tower and Alerts import to decide. Same inputs → same outcome, always. Its test prints the decision table that goes in the README.

## Read first

- `docs/architecture/components/03-policy-engine.md` — all of it; §3 is the code, §4 is the template table, §6 is the test
- `docs/architecture/e2e-wiring.md` §6 (`Facts`, `ConsentView`, `Outcome` contracts)
- `docs/architecture/components/06-alerts-service.md` §2 (what the engine does *not* decide: windows live in Alerts)

## Deliverables

```
packages/tower-policy/
  src/tower_policy/
    __init__.py          exports: Facts, ConsentView, Outcome, ReasonCode, evaluate_line, evaluate_reachability, load_thresholds, phrase
    types.py             Facts, ConsentView (pydantic, frozen); Outcome(kind: ok|changed|refuse, reason_codes: list[ReasonCode])
    codes.py             ReasonCode enum — exactly the twelve in 03 §4 (nine returned + audit-only SUPPRESSED_REVOKED, ALERT_FAILED, ACK_IGNORED_SWAPPED_LINE)
    thresholds.py        Thresholds model; load_thresholds(path) with the validation in 03 §3 (SWAP_WINDOW ≤ 2400 h, STALE ≤ 1 h; raise on violation)
    thresholds.yaml      SWAP_WINDOW: 72h, STALE: 10m, FRESH: 10m, UNREACHABLE_ALERT: {transplant: 20m, care: 4h}, ESCALATE_NEXT: 15m, RATE_LIMIT: 6h, ACK_DISTRUST: 24h
    engine.py            evaluate_line, evaluate_reachability — exactly 03 §3, in that order
    phrasing.py          phrase(outcome, facts, *, alias: str|None, tz: str, form: "voice"|"sms") -> str; templates from 03 §4; times rendered "2:14 today" / "yesterday at 9:30" in the line-holder's tz
    version.py           policy_version(): sha256 of thresholds.yaml + templates — written into every audit row
  tests/
    test_table.py        cross-product from 03 §6; also writes artifacts/policy-table.md when POLICY_TABLE_OUT is set
    test_order.py        consent before facts; carrier error before staleness (named cases)
    test_thresholds.py   file exceeding API max rejected; missing file rejected; valid file loads
    test_phrasing.py     every code × both forms renders; no `\+?\d{10,15}`; no health words; alias substituted; SMS form ≤ 160 chars
    test_determinism.py  1,000 random valid inputs, evaluated twice, identical
  README.md
```

## Steps

1. Types first, frozen. `Facts.fetched_at` is required; everything else nullable exactly as 03 §2.
2. Engine: transcribe 03 §3 literally. Do not add rules. `within(latest_sim_change, now, SWAP_WINDOW)` must treat `latest_sim_change=None` with `sim_swapped=True` as swapped (the API may say swapped without a date).
3. Thresholds as data; the engine takes a `Thresholds` object, with the YAML loaded once by the caller. Default export loads the packaged YAML.
4. Phrasing: templates are a dict keyed by `ReasonCode` with `voice` and `sms` forms. `changed` with two codes joins the two sentences; `OK` is the single sentence. Never interpolate anything but `{time}` and `{Name}`.
5. The table test: build the cross-product from 03 §6, assert every row returns, assert the properties, and render markdown grouped by outcome.
6. `make policy-table` → runs the table test with `POLICY_TABLE_OUT=artifacts/policy-table.md`.

## Acceptance

- `uv run pytest packages/tower-policy` green in < 2 s; `mypy --strict` clean.
- `make policy-table` writes `artifacts/policy-table.md`; the file has a row for `bound=False, sim_swapped=True(inside)` → `NOT_BOUND` (the leak-prevention case), visibly.
- `phrase()` for `SIM_SWAPPED_RECENT` with `latest_sim_change=14:14Z`, tz `America/Toronto` → contains "10:14" and "today" when `now` is the same day.
- No `import datetime.now`, `time`, `random`, `os.environ`, or network in `src/` (a test greps for it).

## Guardrails

- No I/O, no clock, no logging in this package.
- Don't put the 20-min / 4-h window logic here. The engine reports the instant fact; Alerts applies windows (06 §2).
- Don't add reason codes. If one seems missing, report back with the case.

## Report back

The rendered `policy-table.md` (first 20 rows) and the test count. Any rule you found ambiguous while transcribing 03 §3, with how you resolved it and the doc line you changed.
