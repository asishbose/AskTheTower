# 11 — Reference client + corpus (`services/ref-client`)

> Load `00-conventions.md` first. Depends on: 08 (Tower running). Day 9. The fallback demo surface, the tool-selection regression harness, and the only place Bedrock sits.

## Goal

A Strands agent on Bedrock that connects to Tower over MCP exactly as Alexa+ would, drives the three demo moments from a terminal (voice optional), captures transcripts, and runs the phrasing corpus as a test.

## Read first

- `docs/architecture/components/09-reference-client.md` — all of it
- `docs/architecture/components/01-alexa-surface.md` §2 (descriptions are the UX), §3
- `docs/architecture/testing-and-showcase.md` §2.9, §3 (end-to-end layer: transcripts vs golden)
- `docs/review-response.md` A5 (why Bedrock is here and nowhere else)

## Deliverables

```
services/ref-client/
  src/ref_client/
    agent.py           Strands agent; model id from env (default a Nova Micro / Haiku-class id); temperature 0; tools = Tower's MCP tools, discovered at connect
    mcp_client.py      Streamable HTTP client with bearer; TOWER_URL; local header X-Tower-User
    run.py             CLI: `ref-client say "<utterance>" [--user asish]`, `ref-client demo` (three moments + transplant story, with the mock admin calls between them), `ref-client corpus`
    voice.py           optional: mic → Transcribe (or local whisper) → agent → Polly → speaker; behind REF_VOICE=1; never required by tests
    transcript.py      {utterance, tool_calls[{name,args}], result (ToolResult), spoken} → artifacts/transcripts/<name>.json; redaction pass (E.164 regex) before write
    corpus_runner.py   loads corpus/phrasings.yaml; for each: expected tool+args or null or clarify; prints a markdown table; exit non-zero below CORPUS_MIN_PASS (default 0.9)
  prompts/ref-client/system.md   one role, one file: "you are a voice assistant; call Tower's tools when the user asks about a phone line; read `summary` verbatim or rephrase without adding facts; ask which line when ambiguous; otherwise answer normally without tools"
  corpus/phrasings.yaml          ≥ 40 entries per 09 §3: ~10 per tool incl. slang ("did my sim get jacked"), 5 off-topic, 3 ambiguous, 2 wrong-language edge
  tests/
    test_no_invented_digits.py   09 §5: for each golden ToolResult, the agent's spoken text contains no digits absent from `summary`
    test_corpus.py               runs the corpus against Tower + mock; asserts ≥ CORPUS_MIN_PASS; writes artifacts/corpus.md
    test_transcripts.py          `demo` run vs golden transcripts in tests/golden/*.json (tool calls + reason codes must match; wording not asserted)
    test_fallback.py             Bedrock unreachable → clear error, nothing else affected (the system has no dependency on this service)
  Dockerfile, README.md, .env.example (TOWER_URL, TOWER_BEARER, BEDROCK_MODEL_ID, AWS_REGION, REF_VOICE, CORPUS_MIN_PASS)
```

## Steps

1. MCP client + agent with the system prompt; `say "is my line ok"` round-trips against the local stack.
2. `demo` command: the §4 showcase order steps 4–7 scripted, with the mock admin calls and clock advances between utterances; prints each spoken line; writes transcripts.
3. Corpus and the runner; write entries from the user's actual phrasings, not the tool names.
4. Golden transcripts written after one green run (the human commits them); redacted by construction.
5. `make demo` → `ref-client demo`; `make corpus` → `ref-client corpus`; `make showcase-ref` → both, with TTS if `REF_VOICE=1`.

## Acceptance

- `make demo` on the local stack prints the three moments and the transplant story with the expected reason codes and exits 0.
- `make corpus` ≥ 90 % with the verbatim descriptions from 01 §2. Failures are listed with the tool chosen — these are description bugs; fix the description in `docs/architecture/components/01` §2 and `tower_mcp/descriptions.py` together (08's drift test enforces it).
- `artifacts/transcripts/*.json` for the four stories; no digits/numbers beyond those in `summary`.

## Guardrails

- The agent has no carrier credentials, no DynamoDB access, no policy code. It only calls Tower.
- It may rephrase `summary`; it may not add facts (09 §5 test).
- The Bedrock call must be the only LLM call in the whole repo (a repo-wide grep test for LLM SDK imports lives here).

## Report back

`artifacts/corpus.md`, the four transcripts, the model id used and its cost per demo run, and every description you changed to fix a corpus miss.
