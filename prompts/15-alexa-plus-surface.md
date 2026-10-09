# 15 — Alexa+ surface (toolkit registration, simulator run)

> Load `00-conventions.md` first. Depends on: 13 (Tower on Runtime) or 12 + a tunnel; spike 02A. Days 13–14. The primary track's literal ask: Alexa+ connects to Tower.

## Goal

Tower registered with the Alexa+ MCP Toolkit, the three tools invoked from the web simulator with the three demo moments, the clarifying-question case shown, and a record of what Alexa+ does with `summary`. If access is not available, the documented fallback is executed instead and the friction log says why.

## Read first

- `docs/architecture/components/01-alexa-surface.md` — all of it
- `docs/architecture/spikes/A-alexa-plus-toolkit.md`
- `docs/architecture/testing-and-showcase.md` §2.1, §4 steps 4–6, §5 (what we don't claim)
- `docs/review-response.md` A1–A4, A13, P7
- the deck's demo and close slides (`docs/Decks/`) for the exact utterances

## Deliverables

```
docs/architecture/alexa/
  registration.md        every step taken, with screenshots; account-linking configuration; the identity Tower receives (ties to tower_mcp auth middleware — update it if the shape differs from spike A)
  simulator-run.md       transcript of: 5 phrasings × 3 tools, 2 off-topic, 1 ambiguous; what Alexa+ said; whether `summary` was read verbatim; the clarifying question
  friction-log.md        the running log of friction (dated, reproducible) that feeds the Alexa+ MCP Toolkit section of docs/submission/product-feedback.md — product feedback is a *required* part of the submission, not a bonus; finalise that section (☑) in this prompt
services/tower-mcp/
  src/tower_mcp/auth.py  final inbound auth for Alexa+ (replacing the spike assumption); tests updated
  README.md              "Connecting from Alexa+" section
artifacts/
  alexa-simulator.mp4    screen recording of steps 4–6 of the showcase order, with the mock admin calls visible in a second pane
  transcripts/alexa-*.json  captured from Tower's side (tool call + result) for each utterance
Makefile                 showcase-alexa: prints the §2.1 script, starts a request log tail on Tower, and the admin curl lines
```

## Steps

1. Register Tower (Runtime URL from 13; or local Tower via a tunnel if 13 was cut — say which in `registration.md`).
2. Account linking per the toolkit's requirement; map to `user_id`; seed the demo users accordingly (the Alexa identity for "asish" and "mom" must be two accounts or one account with two lines — decide from what the simulator allows and document it).
3. Run the §2.1 script; capture Tower-side transcripts for each utterance; note tool selection misses and fix descriptions (with 08's drift test and 11's corpus).
4. Run the three moments exactly as the deck phrases them, with the mock admin calls between; record.
5. Write the friction log while it's fresh.

## Acceptance

- The recording shows all three moments from the simulator with the correct reason codes visible in Tower's log pane.
- `simulator-run.md` answers 01 §7's two open questions, and `components/01` is updated to match.
- The Alexa+ MCP Toolkit feedback section is final: used for, worked, needs work (named pages/errors), onboarding minutes, build again + why.
- Tool-selection on Alexa+ ≥ the corpus pass rate from prompt 11, or the misses are listed with the description change made.

**If access is unavailable from Canada:** `registration.md` records the exact point of failure; the showcase order's steps 4–6 use the reference client (already recorded in 12); the close slide's ask stays; the friction log leads with it. This is a documented outcome, not a gap.

## Guardrails

- Don't change tool shapes to suit the simulator without updating 01 §2, `descriptions.py`, and the corpus together.
- Nothing proactive via Alexa+. If the toolkit offers a notification path, note it in the friction log; don't build on it this week.

## Report back

The verdict (simulator works / fallback), the identity shape as finally implemented, the verbatim-vs-paraphrase observation, and the friction log's top three items.
