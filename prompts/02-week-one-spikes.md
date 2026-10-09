# 02 — Week-one spikes

> Load `00-conventions.md` first. Depends on: 01. Days 1–2, run in parallel with 03–04. Timebox: half a day each. These produce *evidence*, not code that ships.

## Goal

Answer the three unknowns the architecture names, with screenshots, captured requests, or a failing/passing script — so prompts 13 and 15 are built on facts. Each spike ends in a short note under `docs/architecture/spikes/`.

## Read first

- `docs/architecture/components/01-alexa-surface.md` §5, §7 (open questions)
- `docs/architecture/components/05-carrier-gateway.md` §3 (week-one check)
- `docs/architecture/components/02-tower-mcp-server.md` §4 (budget)
- `docs/review-response.md` P6 (the 500 ms figure and where it came from)

## Spike A — Alexa+ MCP Toolkit: access, registration, identity shape

**Question.** From Ottawa, can we register a self-hosted MCP server with the Alexa+ MCP Toolkit and drive it from the web simulator? Specifically: is the toolkit gated by region (US-only, as the deck says) or by partner status ("select partners only", as Badhrinath's v3 note says)? The answer changes the friction log and the close slide's ask. What identity does Alexa+ pass to the server on each tool call (account-linking token, opaque user id, nothing)?

**Do.**
1. Follow the toolkit's current onboarding docs (search; they change). Record every step that is region-gated and whether the simulator is usable from a Canadian developer account.
2. Stand up the smallest possible MCP server (one tool, `echo`) with Streamable HTTP, public via a tunnel or a throwaway API Gateway, with request logging of headers and body.
3. Register it; invoke the tool from the simulator; capture the inbound request verbatim (redact secrets).
4. Note whether Alexa+ reads a `summary` field verbatim or paraphrases — try a tool that returns `{"summary": "...", "facts": {...}}`.

**Write.** Fill the Alexa+ MCP Toolkit section of `docs/submission/product-feedback.md` first — onboarding time, every stall, exact errors — this spike *is* the zero-to-hello-world the organisers ask about. Then `docs/architecture/spikes/A-alexa-plus-toolkit.md`: steps that worked, the captured request shape, the identity field(s), paraphrase-vs-verbatim observation, and the gating findings for the friction log (prompt 17). Then update `components/01` §4 and §7 with the answer.

**If blocked** (no access from Canada): write that down with the exact error, and prompt 15 becomes "reference client is the demo surface". That is the plan, not a failure.

## Spike B — AgentCore Gateway against a CAMARA-shaped OAuth target

**Question.** Does AgentCore Gateway ingest the vendored CAMARA OpenAPI (SIM Swap `check` is enough) and call a target that uses OAuth 2 client-credentials, with Identity holding the client secret? Does the generated MCP tool take the request body as structured args?

**Do.**
1. Vendor the SIM Swap spec only (`specs/camara/sim-swap.yaml`, pinned version in the README).
2. Stand up a 40-line FastAPI stub with `/oauth2/token` (client credentials) and `POST /sim-swap/v*/check` returning `{"swapped": false}`, on a public URL (throwaway).
3. Create a Gateway from the spec; configure outbound auth via Identity (client credentials); list the tools it generated; call `check` from a minimal MCP client.
4. Record: tool names/arg schema generated; whether the OAuth call happened (stub logs); any spec feature it rejected (e.g. `oneOf` on `device`); round-trip latency, 20 calls.

**Write.** The AgentCore Gateway and Identity sections of `docs/submission/product-feedback.md` (onboarding, rejected spec constructs, the OAuth experience), then `docs/architecture/spikes/B-agentcore-gateway.md` with the generated tool list, the verdict (Gateway is the path / `DirectClient` is the path), and the latency numbers. Update `components/05` §3 accordingly.

## Spike C — Hot-path latency harness

**Question.** What does a 3-hop request cost before any real code exists, so the p95 < 400 ms gate is grounded?

**Do.**
1. A throwaway FastMCP server with one tool that: does one DynamoDB Local `GetItem`, two parallel HTTP calls to the stub from spike B (local), one `PutItem`, returns JSON.
2. `scripts/latency.py`: 200 calls over Streamable HTTP, prints p50/p95/p99 as a markdown table. This script is kept — prompt 08 reuses it.
3. Run it locally and, if spike B is up, with the two HTTP calls going through Gateway.

**Write.** `artifacts/latency.md` (first version, labelled "harness only") and the script. If local p95 is already > 250 ms, say why (the usual suspect is DynamoDB Local's JVM warm-up — document the warm-up call).

## Acceptance

- Three spike notes exist, each under one page, each ending with a one-line verdict and the doc it updated.
- `scripts/latency.py` exists and runs.
- Nothing from the spikes is imported by any package or service.

## Report back

The three verdicts in three lines, plus anything that changes the plan in `prompts/README.md` (e.g. "Gateway rejected the spec → prompt 13 is `DirectClient`-first").
