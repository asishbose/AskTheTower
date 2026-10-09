# 11 — Demo UI (control room)

**Role:** one browser page for presenting and rehearsing the demo. It shows the conversation, the carrier's state, the live alerts and audit rows, and the binding QR code side by side. It only drives what `make demo` and the showcase scripts already drive.
**Runs on:** the presenter's laptop only: a container in compose on `:8090`, or `uv run` on the host. Demo tooling, not a system component. It is never deployed to AWS.
**Owns:** nothing. No table, no consent, no policy, no carrier credentials. It reads, and it calls admin endpoints that already exist.
**Status:** designed, not built (diagram [`11-demo-ui`](../diagrams/11-demo-ui.drawio), dashed). Step 2 adds the service `services/demo-ui`, its compose entry, the kind-only Helm chart and a `showcase-ui` make target (doc 10 §5 is updated with it).

---

## 1. What it is and is not

| It is | It is not |
|---|---|
| A view over the reference client (09), the mock's `/_admin` (08 §3), the binding page's local admin (04) and the audit table (07) | A second client of the carrier: it makes no CAMARA call and holds no carrier token |
| A runner for the four showcase stories in `ref_client.demo.STORIES`, step for step, with their narration | A new demo script: the stories, expected reason codes and golden files stay in the reference client |
| Text in, text out (Alexa+'s part is played by the reference client's agent) | A voice surface, or a replacement for the Alexa+ simulator in the video |
| Laptop-only, with ENV=local as the default | Anything that runs in the AWS account (no image in ECR, no Terraform, `values-eks` `enabled=false`) |

## 2. Shape

FastAPI + HTMX, one static page with no build step, mobile-friendly (the four panes stack on a phone). One server process holds one feed poller and one demo runner. The browser gets HTML fragments and one Server-Sent Events stream, `GET /events`.

```
services/demo-ui/
  src/demo_ui/app.py        # routes: /, /events (SSE), /say, /macro/{name}, /carrier/*, /binding/*
  src/demo_ui/feed.py       # the poller (§4): audit rows, sent SMS, carrier state, grants → SSE frames
  src/demo_ui/runner.py     # macros over ref_client.demo.STORIES (§5); one run at a time
  src/demo_ui/clients.py    # thin httpx wrappers for /_admin on the mock and the binding page
  src/demo_ui/redact.py     # the output filter (§8): every frame and fragment passes through it
  src/demo_ui/static/index.html
```

| Pane | Does | Consumes |
|---|---|---|
| **1 Conversation** | Type an utterance as Asish or Mom. See the tool call, `reason_codes`, `summary` / spoken text and `next_step`. Macro buttons: Moment 1, Moment 2, Moment 3, Transplant. | `ref_client` as a library: `TowerClient` → Tower `/mcp`, `BedrockAgent` or `ScriptedAgent` |
| **2 Carrier controls** | Load the demo scenario. Show and advance the mock clock. Fire `sim_swap`, `cf_set`, `cf_clear`, `unreachable`, `reachable` on Asish's or Mom's line. Inject or clear faults. Show line state and subscriptions. | mock `/_admin/*` |
| **3 Live feed** | The last 50 audit rows, from the line-holders' own views, and the SMS that Alerts sent, live over SSE. | DynamoDB (`tower_audit` reader), Alerts (gap G3) |
| **4 Binding** | QR code of a bind link, current grants and what `resolve` returns, and Mom's revoke and re-grant of Asish's `watch`. | binding page `/_admin/*`; Tower's `next_step.url` |

## 3. Interfaces it consumes (exact, as built)

| Pane | Call | Where it is defined | Notes |
|---|---|---|---|
| 1 | MCP `tools/list`, `tools/call` over Streamable HTTP at `TOWER_URL` | `ref_client/mcp_client.py:296` `TowerClient`; headers `:282` | `Authorization: Bearer $TOWER_BEARER`; locally also `X-Tower-User: user-asish \| user-mom` (ignored on AWS) |
| 1 | Bedrock Converse (tool use) | `ref_client/agent.py:120` `BedrockAgent` | the only model call in the repo; `ScriptedAgent` (`:211`) when there is no Bedrock |
| 1 | `next_step.kind == "bind_line"`, `next_step.url` | `tower_mcp/next_step.py:30-42` | a fresh 10-min bind link; pane 4 renders it as a QR code |
| 2 | `GET /_admin/state` | `mock_carrier/routers/admin.py:98` | lines keyed by E.164: the UI keeps holder → line and drops the keys at once (§8) |
| 2 | `POST /_admin/scenarios/load {name:"demo"}` · `GET /_admin/scenarios` | `admin.py:53` · `:49` | |
| 2 | `GET /_admin/clock` · `POST /_admin/clock {advance_s}` | `admin.py:72` · `:61` | the response lists the timeline events that fired |
| 2 | `POST /_admin/lines/{msisdn}/events {event}` | `admin.py:76` | the path takes the raw number (gap G2) |
| 2 | `POST /_admin/faults {kind, n}` · `DELETE /_admin/faults` | `admin.py:85` · `:93` | `timeout`, `500`, `429` |
| 2 | `GET /healthz` | `mock_carrier/app.py:122` | |
| 3 | `tower_consent.list_lines(store, owner)` → `tower_audit.list_for_line(store, line_id, owner)` | `tower_consent/bind.py:124`; `tower_audit/reader.py:63` (owner check `:57`) | read as each demo line-holder, so 07 §4 holds: the feed is Asish's log plus Mom's log, never a watcher's view |
| 3 | sent SMS: **no endpoint today** | bodies exist only as log lines, `alerts/send_backends.py:48` | gap G3 |
| 3 | `GET /healthz` | `alerts/local.py:99` | |
| 4 | `POST /_admin/bind-tokens {user_id}` → `{url}` | `binding_page/routes/admin.py:75` | the UI adds `?as=phone-<who>` locally (the mobile-data simulation, e2e §5) and draws the QR code itself (`segno`); the page has no QR endpoint |
| 4 | `GET /_admin/tables?format=json` | `admin.py:58` | Grants rows only, already redacted by the page |
| 4 | `GET /_admin/resolve?user=..&line=..` | `admin.py:68` | shows `resolve` flipping after a revoke |
| 4 | `POST /_admin/grants {owner_user_id, grantee_user_id, grant, alias, action}` | `admin.py:95` | idempotent; the same `tower_consent.grant` / `revoke` the resident's `/me` page calls |
| 4 | all `/_admin/*` answer 404 unless `TOWER_ENV=local` and `BIND_ADMIN=1` | `binding_page/config.py:57` | so on AWS pane 4 has only the QR code from `next_step` |

The mock's admin API has **no token**. It is mounted only when `MOCK_ADMIN=1` (`mock_carrier/settings.py:64`, `app.py:119`), and the network keeps it private: the compose network locally, and inside the Fargate task on AWS. `MOCK_ADMIN_TOKEN` is therefore a proposal (gap G1), not a current interface.

## 4. The live feed (SSE, no DynamoDB Streams)

One poller per UI process, every `FEED_POLL_S` (2 s locally, 5 s on AWS). It diffs each source against the last tick and pushes only new items as SSE events to every open page.

| SSE event | Source per tick | Shown |
|---|---|---|
| `audit` | `list_lines` for `user-asish` and `user-mom` (cached for 30 s), then `list_for_line` for each line as its owner; merged, newest 50 | time, whose log, actor, tool, trigger, `outcome`, `reason_codes`, `message_ref`. `line_id` shortened to 8 characters |
| `sms` | `GET {ALERTS_URL}/internal/sent?after=<n>` (G3) | time, recipient label (`chain:user-asish`), template body |
| `carrier` | `GET {MOCK_URL}/_admin/state` | clock, per holder: SIM change time, forwarding, reachable, connectivity; subscriptions with status and events sent (by `ref`); pending faults |
| `grants` | `GET {BINDING_URL}/_admin/tables?format=json` (Grants only) | grantee, kind, alias, `revoked_at` |
| `turn`, `control`, `note` | the macro runner (§5) | the narration |

The chain-verified badge stays on the binding page (`/me/lines/{line_id}/audit`, `binding_page/routes/audit.py:20`). Verifying the chain needs the marker signer key (`tower_audit/chain.py:129`), and the UI holds no keys.

## 5. Macros

The four buttons run `ref_client.demo.STORIES` (`demo.py:76`): `moment-1`, `moment-2`, `moment-3`, `transplant`. They use the same `Say`, `Advance`, `Fire`, `Grant` and `Note` steps in the same order as `make demo`. The `why` and `text` of each step are the narration. Each `Say` shows a pass or fail badge: the reason codes it got against the codes the story expects (the golden-file check, 09 §4).

- **One timeline.** The stories share one mock timeline: Moment 2's +8 min only means something after Moment 1's +12. A button runs Reset, replays the earlier stories collapsed, then its own story in full. Reset (ENV=local only) runs the same code as `make seed` (`deploy/compose/seed/seed.py`): it reloads the scenario and clears Watches and `AlertsState`, because a stale `last_state` would otherwise answer.
- **One run at a time.** A second click while a run is going is refused.
- **Honest captions.** Each macro shows a fixed caption naming what the code does not do yet (`code-vs-docs.md`):

| Macro | What it can show | What it cannot show yet |
|---|---|---|
| Moment 1 | `OK`, clock +12, `SIM_SWAPPED_RECENT` | — |
| Moment 2 | `SIM_SWAPPED_RECENT` + `CALL_FORWARDING_SET` | — |
| Moment 3 | `watch_line(mom)`, the swap, the watcher's SMS in the feed, the revoke, the `SUPPRESSED_REVOKED` audit row, `NO_CONSENT` | **D7:** after the revoke, Mom's subscriptions stay `ACTIVE` in pane 2, so the caption must not say "watching stopped". **D15:** the SMS body has no name in it. |
| Transplant | `UNREACHABLE` then `OK` from `is_reachable`, and the audit rows | **D9/D8:** `watch_line(self)` writes profile `self`, so no 20-minute text and no escalation appear. The caption points to the `showcase-alerts` run, which shows them. |
| any `NOT_BOUND` | the bind link as a QR code in pane 4 | **D1:** nothing texts the link. The QR code stands in for the SMS, and the caption says so. **D18:** an unknown alias (`bob`) also gets a link. |

## 6. Configuration

| Variable | Local (compose) | ENV=aws (laptop) | |
|---|---|---|---|
| `TOWER_URL` | `http://tower-mcp:8000/mcp` | `deploy/.env.aws` (Runtime URL) | |
| `TOWER_BEARER` | from `deploy/compose/.env` | a JWT (one per persona, G6) | **also needed**, not in the brief's list: Tower answers 401 without it |
| `MOCK_URL` | `http://mock-carrier:8443` | empty, or `http://localhost:18443` through the tunnel (G5) | empty → pane 2 shows "not reachable from this laptop" |
| `MOCK_ADMIN_TOKEN` | optional | optional | sent as `Authorization: Bearer` once G1 exists; ignored until then |
| `BINDING_URL` | `http://binding-page:8081` | `deploy/.env.aws` (API Gateway) | |
| `ALERTS_URL` | `http://alerts:8082` | `deploy/.env.aws` (hooks base; nothing to read there) | |
| `ALERTS_INTERNAL_BEARER` | `INTERNAL_BEARER` from `deploy/compose/.env` | — | **also needed** for G3 |
| `DYNAMO_ENDPOINT` | `http://dynamodb-local:8000` | empty (real DynamoDB, `AWS_PROFILE`) | mapped to `TOWER_DYNAMODB_ENDPOINT`: `Store.from_env` reads only that name |
| `TOWER_TABLE_PREFIX`, `AWS_REGION` | as compose | `deploy/.env.aws` | |
| `BEDROCK_MODEL_ID` | `amazon.nova-micro-v1:0` | same | with `REF_AGENT=auto\|bedrock\|scripted` |
| `FEED_POLL_S`, `DEMO_UI_PORT` (8090), `DEMO_UI_HOST` (127.0.0.1) | | | |

The UI holds no HMAC or KMS key and no carrier secret. It never prints `.env` values. `/healthz` reports which panes are live, not the settings.

## 7. Wiring

**ENV=local (default).** One compose service `demo-ui` on the `tower` network, published on `127.0.0.1:8090`. Every pane works. The phone that scans the QR code reaches the binding page at `BINDING_PUBLIC_URL`, as in `showcase-binding`; it never reaches the UI.

**ENV=aws.** The same container, or `uv run`, on the laptop, with `deploy/.env.aws` loaded. Nothing is created in the account. What a laptop can reach:

| Pane | Reachable from the laptop? | Result |
|---|---|---|
| 1 Conversation | Tower on AgentCore Runtime: yes, with a valid JWT (D21: with an empty discovery URL every call is 401). Bedrock: yes, with the `att` profile. | works as Asish. Mom needs her own JWT (G6). |
| 2 Carrier | No. `MOCK_URL` is empty (`scripts/render_env.py:29`), the ALB is internal and never forwards `/_admin` (`modules/mock_carrier/main.tf:7`). `make seed-aws` uses ECS Exec, one command per call. | disabled, unless an SSM port-forward to the task is open (G5). Without it no macro can run on AWS. `make demo ENV=aws` has the same problem today. |
| 3 Feed: audit | DynamoDB with the `att` profile: yes | works (about 3 reads/s at 5 s polling) |
| 3 Feed: SMS | No (Lambda, SNS) | not shown. The SMS arrives on the real phone. The audit row with `message_ref` is the evidence. |
| 4 Binding | API Gateway: `/bind/*` and `/me` yes; `/_admin/*` 404 | QR code from `next_step.url` only. Grants and revoke happen on the resident's own phone at `/me` (`grants.py:78`, `:141`), never from the UI. |

## 8. What it must never do

1. **Decide anything.** It imports nothing from `tower_policy` or `camara_client` and calls no CAMARA path. Outcomes come only from Tower's `ToolResult` and the audit.
2. **Call the carrier.** Its only routes to the mock are under `/_admin`, which is a simulation aid and not CAMARA.
3. **Show a phone number.** Lines are shown by holder ("Asish", "Mom") and by the mock's opaque `ref`. Numbers read from `/_admin/state` live only in server memory, keyed by `mobile_data_client_ids` as in `demo.py:184`. Every HTML fragment and SSE frame goes through the E.164 filter (`ref_client.transcript.redact`, `E164` at `transcript.py:21`) before it leaves the process. Uvicorn runs with `access_log=False`.
4. **Write consent.** Grants and revokes go through the binding page (`/_admin/grants`, then `tower_consent`), which records them. The one direct store write is Reset, which reuses the `make seed` code (open decision 5).
5. **Read another person's audit.** Only `list_for_line` as the line's owner.
6. **Speak first.** It has no way to make Alexa+ say anything. Proactive messages stay SMS from Alerts.
7. **Be deployed to AWS.** No ECR repository (`SERVICES` stays five for `push`), no Terraform resource, `values-eks.yaml` `enabled: false`.
8. **Touch the hot path.** It is a client like the reference client. Tower's path still makes one consent read plus the carrier calls (and D2).

## 9. Failure behaviour

| Failure | Pane shows | Never |
|---|---|---|
| Tower 401 / unreachable | the `TowerError` text in pane 1; macros stop | a made-up answer |
| No Bedrock | "scripted agent: tool calls from the script" (as `ref-client demo` says); free text is turned off | a hand-written answer standing in for the model |
| Mock `/_admin` 404 / unreachable | pane 2 greyed out with the reason; macros turned off | a fallback to CAMARA calls |
| Binding admin 404 (AWS, or `BIND_ADMIN` off) | pane 4: QR code from `next_step` only | a session forged to call `/me` |
| DynamoDB unreachable | a "feed paused" banner; the poller retries | — |
| Story codes ≠ expected | a red badge on that utterance; the run goes on (as `run_demo` records mismatches) | hiding the mismatch |

## 10. Gaps the build needs from other services

| # | Service | Gap | Proposal |
|---|---|---|---|
| G1 | mock-carrier | No admin token. `MOCK_ADMIN_TOKEN` does not exist. Compose publishes `:8443` on every laptop interface, so anyone on the venue Wi-Fi can call `/_admin`. | Optional `MOCK_ADMIN_TOKEN`: when set, the mutating `/_admin` routes need `Authorization: Bearer`. `GET /_admin/clock` and `GET /_admin/state` stay open, because Tower (`TOWER_CLOCK_URL`) and Alerts (`alerts/clock.py:44`) read the clock. `seed.py`, `ref_client.demo.Control` and `aws_seed.py` send it. |
| G2 | mock-carrier | `POST /_admin/lines/{msisdn}/events` takes the raw number in the path (`admin.py:76`) | Also accept the opaque `ref` there. `state.line_by_ref` already exists (`state.py:184`). The UI then never holds an E.164 past one parse. |
| G3 | alerts | No way to read sent SMS. Bodies are only log lines (`send_backends.py:48`). | `GET /internal/sent?after=<n>`, behind the existing internal bearer (`internal_api.py:80`), local mode only. Returns `{n, at, label, body}` from `LogSender.sent`, never `to_e164`. Without it the feed shows audit rows (`message_ref`) only. |
| G4 | ref-client | `run_demo` always resets (`demo.py:240`) and reports only through text `echo` (`:260`) | `run_demo(..., reset=True, on_step=None)`: a structured callback with the step and the `Turn`. Alternative: the UI walks `STORIES` itself (the step classes are public) and duplicates about 25 lines of `_step`. |
| G5 | deploy (aws) | No laptop path to the mock admin | An SSM port-forward to the mock task (ECS Exec is already on), giving `MOCK_URL=http://localhost:18443`. Laptop-only, nothing public. It would also make `make demo ENV=aws` work. |
| G6 | tower-mcp (aws) | Identity comes from the JWT `sub`; `X-Tower-User` is ignored | A JWT per persona (`TOWER_BEARER_MOM`), or an Asish-only pane 1 on AWS |

## 11. Tests (for `tester`)

- **Privacy:** drive every pane against a mock state whose keys are the demo numbers. Grep every HTML response and SSE frame with `E164_STRICT`: zero hits. The uvicorn log, too.
- **No second policy path:** an import-graph test (no `tower_policy`, no `camara_client` under `services/demo-ui`), and a grep for CAMARA path prefixes. The existing `services/ref-client/tests/test_only_llm_call.py` still passes with the new service in the tree.
- **Macros = `make demo`:** with `ScriptedAgent` against in-process Tower and the mock (the ref-client test seams), each macro's reason codes equal `STORIES` and `tests/e2e/golden/*.json`. Moment 2 run alone replays Moment 1 first.
- **Owner-only audit:** the feed reads only through `list_for_line` with the owner id. A test passes a watcher id and expects `AuditAccessDenied`, which the feed never triggers.
- **ENV=aws degradation:** with `MOCK_URL=""` and binding `/_admin` answering 404, pane 2 and the macros are off, pane 4 shows only the `next_step` QR code, and the UI makes no request to an empty URL.
- **Never on AWS:** a static test in `tests/aws/`: no `demo-ui` in Terraform, in `SERVICES` for `push`, or enabled in `values-eks.yaml`.
- **One feed:** two browser tabs, one poller (count the DynamoDB calls per tick).

## 12. Showcase on its own

`showcase-ui` (added with the code): `make up`, then open `http://localhost:8090`. Press Moment 1, 2 and 3, then Transplant. Each turn's badge is green. The feed shows the watcher's SMS and then the `SUPPRESSED_REVOKED` row. Scan the QR code with a phone on the same Wi-Fi. What it proves: the same transcripts as `make demo`, live, in one view. It proves nothing the other showcases don't already prove.

## 13. Open decisions (for the user)

1. G1: add `MOCK_ADMIN_TOKEN` (mutations only), or drop it from the UI's settings and rely on the network.
2. G5: an SSM tunnel for ENV=aws, or pane 2 and the macros stay local-only.
3. G6: a second JWT for Mom on AWS, or Asish only.
4. G3: add the Alerts sent-SMS endpoint, or a feed with audit rows only.
5. Reset reuses the `make seed` code, which deletes Watches and `AlertsState` directly. Accept that one store write in demo tooling, or make Reset print "run `make seed`".
6. Bedrock inside the container: mount `~/.aws` read-only with `AWS_PROFILE`, or run scripted in compose (host `uv run` for Bedrock). Compose keeps the DynamoDB Local placeholder credentials away from the reference client on purpose (Bedrock detection).
7. Viewing from a phone: listen on `127.0.0.1` by default. LAN access needs a `DEMO_UI_TOKEN`, since the UI can revoke grants.
8. Transplant macro: ship it with the D9 caption, or wait for D9 (a `watch_line` profile).
9. G4: a hook in `run_demo`, or a loop owned by the UI.
10. Add row 11 to the README's components table (only the diagram table has it now).
