# demo-ui — the demo control room

One browser page for presenting and rehearsing the demo: the conversation, the carrier's state, the live alerts
and audit rows, and the binding QR code, side by side. Design: [`docs/architecture/components/11-demo-ui.md`](../../docs/architecture/components/11-demo-ui.md),
diagram [`11-demo-ui`](../../docs/architecture/diagrams/png/11-demo-ui.png).

**What it is.** FastAPI + HTMX, one static page, no build step (HTMX 2 and its SSE extension are vendored in
`src/demo_ui/static/`). The reference client is used as a library: the macro buttons run
`ref_client.demo.STORIES` through `run_demo(reset=False, on_step=…)`, the same code and steps as `make demo`,
with a pass/fail badge per step.

**What it is not.** Not part of the product and not on any path (e2e §3–§5): it owns no table, decides nothing
(outcome chips are Tower's `reason_codes`), makes no CAMARA or Gateway call, holds no key, never shows or handles a
phone number, and is **never deployed to AWS** (no ECR repository, no Terraform, `values-eks` `enabled: false`).
There is no `prompts/` folder: the UI has no agent role of its own.

| Pane | Does |
|---|---|
| 1 Conversation | macros Moment 1, 2, 3, Transplant (Reset → earlier stories replayed → this one, badges + timings); free text as Asish or Mom with Bedrock; environment pill (`scripted`/`bedrock` · `ENV`) |
| 2 Carrier controls | Reset (= `make seed`), clock +1/+12/+20 min, line events by the mock's opaque `ref`, faults; state by holder |
| 3 Live feed | SMS from Alerts' `GET /internal/sent` (role, template, body) and the last 50 audit rows read as each line's owner |
| 4 Binding | bind link as a QR code (drawn here with `segno`), grants, `resolve`, Mom's revoke / re-grant |

## Run

```bash
make up              # the stack, including this UI in compose at http://127.0.0.1:8090 (scripted agent)
make showcase-ui     # the judge-facing run: the UI on the host, Bedrock when AWS credentials resolve
```

On the host without make: set the variables below (see `.env.example`) and `uv run demo-ui`. On ENV=aws, run
`make showcase-ui ENV=aws`: the conversation (Asish only) and the audit feed work; the carrier pane, Reset and the
macros are local-only and say so; pane 4 shows only the QR code from Tower's `next_step`.

## Config

| Variable | Default | Meaning |
|---|---|---|
| `ENV` | `local` | `local`, `eks`, `aws`; not `local` → pane 2, Reset and macros off (doc 11 decision 2), Asish only |
| `TOWER_URL`, `TOWER_BEARER` | `http://localhost:8080/mcp`, — | Tower's MCP endpoint and bearer (a JWT on AWS) |
| `MOCK_URL`, `MOCK_ADMIN_TOKEN` | `http://localhost:8443`, — | the mock's `/_admin` and its bearer (08 §3, G1); empty URL → pane 2 off |
| `BINDING_URL` | `http://localhost:8081` | the binding page's local admin (`/_admin/*`, 404 off-local) |
| `ALERTS_URL`, `ALERTS_INTERNAL_BEARER` | `http://localhost:8082`, — | `GET /internal/sent` (06 §3.1, G3) |
| `DYNAMO_ENDPOINT` (`TOWER_DYNAMODB_ENDPOINT`), `TOWER_TABLE_PREFIX`, `AWS_REGION` | `http://localhost:8000`, ``, `us-east-1` | audit reads; with an endpoint, DynamoDB Local's placeholder credentials are set in code, never in `AWS_*` |
| `REF_AGENT`, `BEDROCK_MODEL_ID` | `auto`, `amazon.nova-micro-v1:0` | `auto` = Bedrock when credentials resolve |
| `DEMO_UI_HOST`, `DEMO_UI_PORT` | `127.0.0.1`, `8090` | listen address |
| `DEMO_UI_PUBLISHED_LOOPBACK` | `0` | `1` = listens on 0.0.0.0 but is published on 127.0.0.1 only (compose, kind) |
| `DEMO_UI_TOKEN` | — | required for a non-loopback listen; open once with `?token=` (HttpOnly cookie) or send a bearer |
| `FEED_POLL_S` | `2` (`5` off-local) | feed poll interval; the poller runs only while a page is open |
| `DEMO_UI_SEED_PATH` | the checkout's `deploy/compose/seed/seed.py` | the `make seed` module Reset runs (copied into the image) |

Every POST needs the `HX-Request` header that HTMX sends, so another web page cannot drive the UI on 127.0.0.1.
Logs are JSON lines with event names and counts; uvicorn's access log is off; every fragment and SSE frame passes
the number filter (`redact.py`). `/healthz` reports the mode, `ENV` and which panes are live, never a setting.

## How to showcase

`make up && make showcase-ui`, open http://127.0.0.1:8090. Press Moment 1, 2, 3, then Transplant: every badge
is green; the feed shows the watcher's SMS (`watcher`, named "mom"), then the `SUPPRESSED_REVOKED` row, then the
partner's (`escalation[0]`) and the neighbour's (`escalation[1]`) texts. "QR: bind Asish's line" draws a bind link
a phone on the same Wi-Fi can scan (the caption says nothing texts it yet: D1). What it proves: the same
transcripts as `make demo`, live, in one view — nothing the other showcases don't already prove.

## How to test

```bash
uv run pytest services/demo-ui -q          # unit (config, redaction, macro sequencer, feed, views) + integration (app over ASGI, moto)
```

The fuller suite (privacy on the wire, macros vs golden over the in-process stack, import graph, never-on-AWS
static test, Playwright smoke) is doc 11 §11.
