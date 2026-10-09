# 17 — Submission README + prior art

> Load `00-conventions.md` first. Depends on: 16, 18, 19. Day 17. The README is the submission's front door: it pitches the idea in a minute, proves it in the next three, and runs with two `make` commands. Day 18 is buffer.

## Goal

A root `README.md` that a judge can read in four minutes and run in five; `docs/prior-art.md` naming everything the deck keeps generic; the friction log, test report and cost sheet linked; the submission form fields drafted in one file.

## Read first

- `docs/review-response.md` — P3 (what prior-art.md must name), P5, §4 ("net effect on the pitch")
- the deck (`docs/Decks/`): cover, problem, shift, idea, demo, honest, architecture, aws, consent, tracks, close — the README's pitch is the deck in prose, same claims, same numbers
- `docs/architecture/README.md`, `testing-and-showcase.md` §4–6
- `artifacts/test-report.md`, `latency*.md`, `cost.md`, `docs/architecture/alexa/friction-log.md`
- `make help` output (prompt 19) — the "Run it" block is generated from it
- the hackathon's submission form fields (fetch; list verbatim in `docs/submission/form.md`)

## README structure (in this order; headings are fixed)

```
# Ask the Tower
one line: Your own agent on Alexa+ asking the carrier about your line — from the one device that still works after your phone goes dead.

## The problem, in three moments            (problem slide, as three lines of dialogue — the user's words, then Alexa's; then the three figures from the numbers slide with their sources, one line each)
## What it does                              (idea slide: three tools, consent first, verification not retrieval; one paragraph, no adjectives)
## Why an Echo                               (shift slide: a SIM swap feels like bad signal; the Echo is on Wi-Fi; Alexa+ can't speak first so alerts go by SMS — the hero insight and its honest limit in one paragraph)
## See it                                    (video link; three GIFs ≤ 10 s each: moment 1 in the simulator or ref client; the phone buzzing; revoke → suppressed in the audit)
## Run it                                    (generated block: prerequisites → `make up` → `make demo` → expected output excerpt → `make showcase` → `make test`; "in N min on a clean machine" from artifacts/clean-run.txt; Windows: WSL2/Git Bash)
## How it's built                            (architecture: component-map PNG; ten one-liners linking docs/architecture/components/; the three paths in three sentences; the seven rules)
## Where it runs                             (three environments, one code base: local compose · AWS AgentCore Runtime + Gateway + Identity + Lambda + Fargate · EKS from Helm — the transcript match across all three as the proof; a 6-row table of what's hosted where)
## What's measured                           (p95 per tool local and AWS; conformance report; corpus pass rate; test counts per layer; links into artifacts/)
## What's real and what's mock               (§5 non-claims verbatim; the mock is spec-conformant; the X-Mock-Client-Id simulation; what needs a real carrier)
## Consent and privacy                       ("what never happens" list; how to verify it yourself: `make privacy-grep`, audit `verify`, the policy table)
## Built with                                (a flat list the form's Built With field is copied from: Alexa+ MCP Toolkit first, then Amazon Bedrock AgentCore Runtime / Gateway / Identity, Amazon Bedrock + Strands, DynamoDB, SNS, EventBridge Scheduler, Lambda, API Gateway, Fargate, EKS, KMS, CAMARA OpenAPI, FastMCP, Terraform, Helm, Python 3.12; and the AI tools used to build it)
## Tracks                                    (Alexa+ primary: MCP server on AgentCore Runtime; AWS Builder: the services used and the one place Bedrock sits; Open Source: the consent-and-binding kit with install + 20-line example; product feedback: link to the friction log)
## Prior art                                 (two lines + link to docs/prior-art.md; the honest slide's three-bullet "what is new" unchanged)
## Status and limits                         (what was cut per the cut line, if anything; the two things that need a real carrier; Canada caveat; EKS torn down after the showcase and why)
## Cost                                      (the sheet: AgentCore month estimate; EKS showcase window; `make down` → zero)
## Repo map · Licence · Team                (Asish Bose and Badhrinath Padmanabhan, Canada)
```

Length target: under 1,800 words excluding the generated block and tables. Every number links to the artefact it comes from.

## Other deliverables

```
docs/research/            Badhrinath's notes if supplied (proactive-alexa, silent-alexa-facts, silent-alexa-prior-art, sim-swap-stats) — fold stats into the numbers slide check and prior art into docs/prior-art.md
docs/prior-art.md         every platform/product the review named with link + "does / doesn't": carrier network-API platforms and their MCP servers (named here, per P3), the community CAMARA MCP server, Vonage MCP servers, the CAMARA MCP position paper, Twilio Verify / Prove SIM-swap checks, AT&T Wireless Lock / T-Mobile SIM Protection / Verizon Number Lock, Canadian carrier PINs, Find My / Verizon Family / T-Mobile FamilyMode, carrier Alexa skills; dated; links verified on the day
docs/submission/form.md   each form field with drafted text: tagline ≤ 10 words; description within the limit and naming "Alexa+ MCP Toolkit" in its first two sentences; Built With list (same as the README section); the product-feedback field(s) pasted from docs/submission/product-feedback.md; links (repo, video, deck PDF); team: Asish Bose and Badhrinath Padmanabhan, Canada
docs/submission/product-feedback.md   every section ☑ final — this is a required part of the submission; a section still at ☐ for a tool that appears in Built With fails acceptance
docs/architecture/diagrams/png/   exported from the .drawio files (`make diagrams-png`); README embeds 01 and 02; render checked on GitHub dark mode
README gifs               artifacts/gifs/*.gif (≤ 2 MB each) cut from the video
packages/tower-consent/README.md, services/binding-page/README.md   "reuse with your own CAMARA client" section (Open Source mini)
LICENSE (Apache-2.0 or MIT — pick), CONTRIBUTING.md (short), SECURITY.md (what the system stores: HMACs, ciphertext, audit rows; how to report)
```

## Steps

1. Draft the README from the structure; paste the deck's sentences where they already say it best — the README and the deck must not disagree (`make deck-check`).
2. Generate the "Run it" block (`make help`), the PNGs, the GIFs.
3. `docs/prior-art.md`; verify links.
4. Open Source mini: `pip install -e packages/tower-consent` + example against DynamoDB Local works from the README section alone.
5. Form text; cold-read test: someone who hasn't seen the project says back what it does in one sentence after §1–3; rewrite until they can.
6. `make secrets-check` (gitleaks over the full history) and a manual look at `.env*`, `deploy/`, screenshots and the video for keys, tokens, phone numbers or account ids. Then `make test && make docs-check && make deck-check` on main; tag `v0.1.0-hackathon`; confirm repo visibility matches the rules.

## Acceptance

- Cold reader states the idea after three sections and runs the demo from "Run it" without opening another file.
- Every claim links to an artefact or a doc; `deck-check` and `docs-check` pass after README edits.
- `docs/prior-art.md` names what P3 promised; the deck stays generic.
- Tagged; form text ready; video and deck PDF links live; both team members named on the cover slide, the close slide, the README and the form.
- "Alexa+ MCP Toolkit" appears in the description's opening, in Built With, in the README's first screen, and in the video with a caption.
- `docs/submission/product-feedback.md` has no ☐ sections for any tool in Built With; `make secrets-check` clean.

## Guardrails

- No "revolutionary", "first ever", "AI-powered", "seamless". Plain claims, sourced. The honest slide's tone is the README's tone.
- The employer-platform naming stays out of the deck and README body; it lives in `docs/prior-art.md` only (P3).
- Don't add features on day 17. If something's broken, cut it from the README and say so under Status.

## Report back

The README rendered, the prior-art list, the form text, and the tag. Then stop: day 18 is for the buffer, not for work.
