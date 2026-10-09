# ref-client

The reference client: a voice-shaped client for Tower that isn't Alexa+
(design: [`docs/architecture/components/09-reference-client.md`](../../docs/architecture/components/09-reference-client.md)).
It connects to Tower over MCP Streamable HTTP exactly as Alexa+ would, lets a Bedrock model choose Tower's tools
from their descriptions, and writes transcripts. Three jobs:

1. **Fallback demo surface** — `ref-client demo` drives the three demo moments and the transplant story from a
   terminal, with the mock carrier's admin calls and clock advances between utterances. The transplant story
   starts with a Settings step: `POST {BINDING_URL}/_admin/watch-settings` saves Asish's `transplant` profile
   with contacts `[user-partner, user-neighbour]` (06 §11.4); `Control.reset` deletes that Watch first.
2. **Tool-selection regression** — `ref-client corpus` runs ~40 real phrasings (`corpus/phrasings.yaml`) and
   checks the model picked the expected tool and arguments. A miss is a description bug.
3. **The one place a model sits** — `src/ref_client/agent.py` is the only language-model call in the repository
   (`tests/test_only_llm_call.py` greps for any other).

What it doesn't do: hold carrier credentials, touch DynamoDB, or decide policy. Nothing in the system depends on
it (`tests/test_fallback.py`).

## Layout

| Path | |
|---|---|
| `src/ref_client/mcp_client.py` | `TowerClient`: Streamable HTTP, `Authorization: Bearer $TOWER_BEARER`, local `X-Tower-User`; tools discovered at connect |
| `src/ref_client/agent.py` | `BedrockAgent` (Converse API + tool use, temperature 0, digit guard) and `ScriptedAgent` (no model) |
| `src/ref_client/demo.py` | the four stories (showcase order §4 steps 4–7) and the mock / grant controls |
| `src/ref_client/transcript.py` | transcript shape, E.164 redaction before write, `invented_digits`, `compare(golden, transcript)` |
| `src/ref_client/corpus_runner.py` | load the corpus, score, markdown table, `CORPUS_MIN_PASS` gate |
| `src/ref_client/run.py` | the CLI |
| `src/ref_client/voice.py` | optional mic → whisper → agent → Polly → speaker, behind `REF_VOICE=1` |
| `prompts/ref-client/system.md` | the system prompt (one role, one file) |
| `corpus/phrasings.yaml` | the phrasing corpus |
| `../../tests/e2e/golden/*.json` | golden transcripts: tool calls + reason codes, hand-written from `artifacts/policy-table.md` |

## Run

```bash
make demo                      # = ref-client demo --env $(ENV): transcripts → artifacts/transcripts/<story>.json
make corpus                    # = ref-client corpus: table → artifacts/corpus.md (needs Bedrock)
make showcase-ref              # both; REF_VOICE=1 speaks the answers
uv run ref-client say "is my line ok" --user asish
uv run pytest services/ref-client -q
```

**Agents.** `--agent auto` (default) uses Bedrock when AWS credentials are configured; otherwise the demo runs
with the **scripted** agent — tool calls come from the demo script and `summary` is read verbatim — and says so on
its first line. The scripted run proves Tower's side of each transcript (tool call → reason codes), not tool
selection; `corpus` and `say` need the model (without credentials `corpus` prints SKIPPED and exits 0; `say`
exits 3). `--agent bedrock` never falls back.

**Exit codes.** 0 ok · 1 demo reason codes differ from the script / corpus below the gate · 2 Tower or a demo
control unreachable · 3 Bedrock unavailable (the message names the model, region and what to check).

**The demo's controls.** The script calls the mock's `/_admin/scenarios/load`, `/_admin/clock` and
`/_admin/lines/{msisdn}/events` (numbers are read from the mock's state by simulated client id and never printed),
and for moment 3 the binding page's local grant admin: `POST {BINDING_URL}/_admin/grants`
`{owner_user_id, grantee_user_id, grant, alias, action: "revoke"|"grant"}` (idempotent; `TOWER_ENV=local`,
`BIND_ADMIN=1`). Locally Tower follows the mock's clock (`TOWER_CLOCK_URL`).

**Re-running.** On compose, run the demo through `make demo`. It runs `make seed` first, which clears the
previous run's Watches and Alerts state. A Watch's `last_state` from the old timeline would otherwise outlive
the mock's scenario reset, and Tower's stored-state path would answer from it.

`--pause` waits for enter before each story ("press enter for step 4: …"). `make showcase` uses it for steps 4–6.

## Config

| Variable | Default | |
|---|---|---|
| `TOWER_URL` | `http://localhost:8080/mcp` | Tower's MCP endpoint (`mk/vars.mk`) |
| `TOWER_BEARER` | — | local static bearer, or the JWT on AWS |
| `MOCK_URL` / `BINDING_URL` | `http://localhost:8443` / `http://localhost:8081` | demo controls (local) |
| `MOCK_ADMIN_TOKEN` | — | bearer for the mock's mutating `/_admin` routes (08 §3); `make demo` reads it from `deploy/compose/.env`. The demo fires events by the line's `ref` (`/_admin/state?view=refs`), never by number |
| `BEDROCK_MODEL_ID` | `amazon.nova-micro-v1:0` | any Converse model with tool use |
| `AWS_REGION` | `us-east-1` | Bedrock (and Polly) region |
| `BEDROCK_ENDPOINT_URL` | — | override the Bedrock endpoint (tests point it at a closed port) |
| `REF_AGENT` | `auto` | `auto` · `bedrock` · `scripted` |
| `REF_VOICE` | `0` | `1` = speak with Polly; `say -` listens on the mic |
| `CORPUS_MIN_PASS` | `0.9` | corpus gate |
| `REF_ARTIFACTS_DIR` | `artifacts` | where transcripts / corpus.md go |
| `REF_SYSTEM_PROMPT`, `REF_CORPUS` | packaged files | override the prompt / corpus path |

**Cost.** Nova Micro on demand lists at $0.035 per million input tokens and $0.14 per million output tokens (us-east-1; not re-verified in the autonomous build). One model
demo run is about nine utterances × two Converse calls × ~1.2 k input tokens ≈ 22 k input + ~1 k output tokens,
**≈ $0.001 per demo run**; a 42-entry corpus run ≈ $0.004. These are estimates; the CLI prints the token counts
of a corpus run (`tokens in/out`) so the real figure can replace them.

## Showcase on its own

`make showcase-ref` against the local stack: the three moments and the transplant story printed line by line
(`you>`, the tool call and reason codes, `ref>`), then the corpus table. Transcripts in `artifacts/transcripts/`
are the evidence a judge can read without a device.

## Tests

| Test | Layer | |
|---|---|---|
| `test_transcripts.py` | integration (+ e2e Bedrock, skipped without credentials) | scripted demo against in-process Tower + mock + DynamoDB vs `tests/e2e/golden/*.json` |
| `test_no_invented_digits.py` | unit + integration (+ e2e Bedrock) | 09 §5 on every ToolResult of the golden run; the agent's guard |
| `test_corpus.py` | unit + integration (+ e2e Bedrock) | corpus shape, scoring, descriptions verbatim, live run gated at 90 % |
| `test_fallback.py` | unit + integration | Bedrock unreachable → clear error; Tower unaffected; nothing imports `ref_client` |
| `test_only_llm_call.py` | unit | no other model call in the repo |
| `test_demo_control.py` | unit | grant admin contract; CLI exit codes |

`REF_TRANSCRIPTS_WRITE=1 uv run pytest services/ref-client/tests/test_transcripts.py` rewrites
`artifacts/transcripts/*.json`. `REF_DDB_BACKEND=moto|local` picks the DynamoDB (default: DynamoDB Local when
`docker info` works, else moto).

## As a library (the demo UI)

`run_demo(agent_for, control, *, reset=True, on_step=None, replay=())` is what `services/demo-ui` calls (doc 11, G4):
`on_step` receives a `StepReport` per step (story, `<story>#<n>`, kind, narration, expected vs actual reason
codes, `ok`, `elapsed_ms`, `replay`, the `Turn`); `reset=False` skips the scenario reload. No product component
imports `ref_client` (09 §4 "Who may depend on it").
