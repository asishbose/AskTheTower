# 16 — Showcase artefacts + video

> Load `00-conventions.md` first. Depends on: everything through 15. Days 15–16. Evidence, then the recording.

## Goal

Every item in `testing-and-showcase.md` §6 exists, is current, and is linked from the README; the nine-step showcase is rehearsed and recorded under three minutes; the deck's numbers match the artefacts.

## Read first

- `docs/architecture/testing-and-showcase.md` §4 (order and timings), §5 (non-claims), §6 (checklist)
- `docs/architecture/diagrams/06-test-topology.drawio`
- the deck (`docs/Decks/`), slides: demo, architecture, aws, honest, tracks, close
- hackathon submission requirements (video length, what must be shown, repo visibility) — fetch the current rules page and quote the constraints at the top of `docs/submission/checklist.md`

## Deliverables

```
artifacts/
  policy-table.md          regenerated (make policy-table)
  latency.md               local; latency-aws.md if 13 ran — both dated, with p50/p95/p99 per tool
  conformance-report.html  regenerated
  corpus.md                regenerated
  transcripts/*.json       the four local stories + alexa-* if 15 ran
  sms-screenshot.png       the watcher's phone, alert received (number masked)
  audit-screenshot.png     Mom's view, chain verified
  clean-run.txt            `time make up && make demo` on a clean machine
  terraform-plan.txt, billing-zero.png, cost.md
  video/
    script.md              the nine steps with the exact spoken lines, timings, and which pane is on screen; the organisers' five answers placed explicitly: what problem (0:00), who it's for (0:15), the solution working (0:45–2:15), how it uses the track's tool — say "Alexa+ MCP Toolkit" aloud and show it on screen when the simulator calls Tower (0:45), what the working app actually does (2:15). Pitch, not tutorial: no install steps on camera beyond `make up && make demo`.
    ask-the-tower-demo.mp4 ≤ 3:00; 1080p; captions burned in for the spoken utterances
docs/submission/
  checklist.md             the rules' constraints + the §6 list with links, each ticked with the date it was produced
  deck-consistency.md      every number on the deck (p95, cost, day count, API list, table count) ↔ the artefact it comes from; mismatches fixed in the deck
Makefile                   showcase-artifacts: regenerates every generated artefact in one go and fails if any is stale (> 24 h older than the code)
```

## Steps

1. `make showcase-artifacts`; leave the generated files for the human to commit.
2. Walk the deck slide by slide against the artefacts; edit the deck where a number moved (the Slides artifact is the deck; re-export the PPTX to `docs/Decks/` after edits).
3. Write `video/script.md` from §4 with real timings from a dry run; cut until under three minutes with steps 4–6 untouched. Open with the hook from the numbers slide's note (Wei Shen, NBC 6 Miami 2022 — phone went quiet, $68,000 gone in hours, nobody else knew), 15 s, then "same attack, different ending". Never say "SIM swap is growing in the US" (see the numbers slide note).
4. Record: two panes (simulator or reference client; Tower log + mock admin), phone on camera for step 6, binding page on the phone for step 3. One take per step is fine; stitch.
5. Burn captions; export; check it plays without audio and still makes sense (judges skim).
6. Update the `docs/architecture/README.md` status line from "design" to "built — see artifacts/".

## Acceptance

- §6 checklist fully ticked with links; `make showcase-artifacts` passes the staleness check.
- Video ≤ 3:00, shows the three moments, the buzz on camera, revoke → suppressed, audit verified, `make demo` in the terminal.
- The track tool is impossible to miss: "Alexa+ MCP Toolkit" spoken and on screen (a caption) at the moment the simulator invokes a Tower tool; a second caption names AgentCore Runtime when the architecture is shown.
- No key, token, phone number or account id visible in any frame (scrub the terminal and console panes; use a clean AWS console profile).
- `deck-consistency.md` has zero open mismatches.

## Guardrails

- No claim in the video that the tests don't back (§5). "Spec-conformant mock" not "a real carrier"; "measured against the mock" with the number on screen.
- No phone number visible anywhere in the recording; mask the SMS header.
- Don't re-record steps 4–6 to look smoother than they are; a visible latency is fine, a faked one is not.

## Report back

The video link, the checklist, and the list of deck edits made for consistency.
