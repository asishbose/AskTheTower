# 09 — Reference Client

**Role:** a voice-shaped client for Tower that isn't Alexa+. It is the demo path if Alexa+ web-simulator access slips, the integration-test harness for tool selection, and the one legitimate place Bedrock sits in this system.
**Runs on:** locally (CLI); optionally on AgentCore Runtime as a Strands agent.
**Owns:** nothing. It calls Tower's MCP tools exactly as Alexa+ would.

---

## 1. Why it exists

Three reasons, all of them boring and all of them real:

1. **Fallback demo surface.** The MCP Toolkit is US-only; the simulator should work from Ottawa, but if it doesn't on the day, this client drives the same three moments from a terminal with speech-to-text in and text-to-speech out.
2. **Tool-selection regression.** Alexa+'s model chooses tools from descriptions. The reference client, with a different model, is a second opinion: if phrasings in the test corpus select the wrong tool here, the descriptions are ambiguous and will be ambiguous for Alexa+ too.
3. **AWS Builder mini.** It is a Strands agent on Bedrock that genuinely does something — not Bedrock in the hot path for show.

## 2. Shape

```
ref-client/
  agent.py           # Strands agent; system prompt from prompts/ref-client/
  mcp_client.py      # connects to Tower over Streamable HTTP with the local bearer
  voice.py           # optional: mic → transcribe → agent → polly → speaker
  corpus/            # phrasings.yaml — utterance → expected tool + args
  prompts/
    ref-client/
      system.md      # one file; the client has one role
```

Model: a small Bedrock model (Nova Micro / Haiku-class) at low temperature. It never sees carrier credentials, never calls carrier APIs directly, never decides policy — it only decides which Tower tool to call, like Alexa+.

**As built (prompt 11):** `services/ref-client/` with `src/ref_client/{agent,mcp_client,demo,transcript,corpus_runner,run,voice}.py`, `prompts/ref-client/system.md`, `corpus/phrasings.yaml`. The agent calls the **Bedrock Converse API with tool use directly** (boto3), not the Strands Agents SDK: `strands-agents` 1.58 requires `mcp<2.2` and Tower's FastMCP 4.0.11 needs `mcp` 2.3 in the same uv workspace lock. The loop is the one Strands' `BedrockModel` would run; swap back when Strands accepts `mcp>=2.3`. Default model `amazon.nova-micro-v1:0` (`BEDROCK_MODEL_ID`), temperature 0. Without AWS credentials the demo runs with a **scripted agent** (tool calls from the demo script, `summary` read verbatim) and says so; it proves Tower's side of the transcript, not tool selection.

## 3. The corpus

```yaml
- say: "my phone just lost signal, is my line ok?"
  expect: { tool: line_is_ok, args: { line: self } }
- say: "is anything forwarding my calls"
  expect: { tool: line_is_ok, args: { line: self } }
- say: "is mom's phone on"
  expect: { tool: is_reachable, args: { line: mom } }
- say: "stop watching mom's line"
  expect: { tool: watch_line, args: { line: mom, enable: false } }
- say: "what's the weather in ottawa"
  expect: { tool: null }
- say: "is the line ok"     # no owner named: ask which line ("is my line ok" means self — demo moment 1)
  expect: { clarify: true }
```

Forty-odd entries. The test asserts selection and arguments; it does not assert the model's wording.

## 4. Transcript capture

Every run writes a transcript (`utterance → tool call → structured result → spoken text`) to `artifacts/transcripts/`. The README embeds one. This is the evidence a judge can read without a device. Golden files (`tests/e2e/golden/`, one set for ENV=local, eks and aws) hold the tool calls and reason codes per utterance; `ref_client.transcript.compare` is the check. Between utterances the demo calls the mock's `/_admin/*` and, for moment 3's revoke, the binding page's local grant admin `POST /_admin/grants {owner_user_id, grantee_user_id, grant, alias, action}` (`BIND_ADMIN=1`).

The demo script fires mock events by the line's opaque `ref`, read from `GET /_admin/state?view=refs`, so it never handles a number, and sends `MOCK_ADMIN_TOKEN` as a bearer when it is set (08 §3). `run_demo(agent_for, control, *, reset=True, on_step=None, replay=())` (G4, doc 11 §10): `on_step` receives a `StepReport` per step (story, step id `<story>#<n>`, kind, narration, expected and actual reason codes, `ok`, `elapsed_ms`, `replay`, fired timeline events, the `Turn`); `reset=False` skips the scenario reload and only looks up the line refs. The CLI's behaviour is unchanged.

**Who may depend on it.** No product component — Tower, Alerts, the binding page, the mock carrier, `packages/` — imports `ref_client` or waits on it, so the product never has a model on its path (design rule 1). The one consumer is the demo UI (11), which is laptop-only demo tooling outside paths A/B/C and drives Tower through this client exactly as `make demo` does; nothing imports the demo UI in turn. `tests/test_fallback.py::test_nothing_depends_on_the_reference_client` checks both.

## 5. Not a second policy path

The client receives Tower's `summary` and may read it verbatim or rephrase; it may not add facts. The system prompt says so, and a test asserts no digits appear in its output that weren't in `summary` (no invented times or numbers). The client also enforces it: a model reply carrying a digit that no `summary` has is replaced by the summary verbatim, and the transcript records the replacement (`guard`).

## 6. Deployed as the web chat page (decision 2026-10-09)

For the AWS demo the reference client is also deployed as a signed-in chat page: the agent on AgentCore Runtime (`POST /invocations`, Cognito JWT), a thin page in front (Lambda + CloudFront). Same prompts, stories and golden transcripts; `next_step` is copied from the tool result verbatim. Flows, rules and open questions: [`../bind-and-alert-flows.md`](../bind-and-alert-flows.md). This is the Alexa+ stand-in if simulator access is unavailable (prompt 15 fallback); the laptop demo UI (11) is unchanged.

## 7. Showcase on its own

`make showcase-ref`: the three demo moments driven from the terminal against local Tower + mock, with TTS if available. Then `make corpus`: the selection table with pass/fail. See `testing-and-showcase.md` §2.9.
