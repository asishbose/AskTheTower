# 21 — Demo UI: a visual control room

> Redesign the **presentation** of `services/demo-ui` so it looks like a product a judge wants to watch, not a form. Dark, cinematic, picture-led, with one animated scene that shows the story happening. **Behaviour, endpoints, data flow, security and tests stay exactly as they are** (`components/11-demo-ui.md`); this prompt changes templates, static assets and CSS, and adds a visual-regression test. **No git operations**: leave everything in the working tree and list it in the final message.

## Read first

- `prompts/00-conventions.md`, `prompts/RUN-ALL.md` (Operating mode)
- `docs/architecture/components/11-demo-ui.md` — every decision in §13 stands; §1 "it is not" is the boundary
- `services/demo-ui/README.md`, `src/demo_ui/{app,views,redact,macros,feed}.py`, `src/demo_ui/templates/**`, `src/demo_ui/static/**`
- `docs/img/hero.svg` — the project's illustration; reuse its shapes, palette and mood (navy sky `#070b1f→#1d2b63`, cyan `#4fe3ff`, warm amber `#ffd27a`, mint `#7CF2B4`, coral beacon `#ff6b6b`)
- `docs/architecture/explainer/README.md` — the ten pages and the talk track; the UI should feel like those pages came alive
- `.claude/rules/*.md`; `frontend-design` skill if present

## Design brief

**Mood.** Night-time operations room watching over a town. Depth (layered gradients, soft glows, subtle grain), not flat cards. Typography: Inter or system-ui for UI, a condensed display face (`Sora`/`Space Grotesk` from Google Fonts, vendored as woff2 — no runtime CDN) for the title and pane names. One accent colour per meaning, used consistently: cyan = request path, amber = proactive/SMS, mint = consent/ok, coral = refusal/alert. Motion: short (150–300 ms), purposeful, `prefers-reduced-motion` respected.

**Layout (1440 × 900 and up; degrades to 1024).**

1. **Top bar** — wordmark "Ask the Tower" with the small tower glyph from `hero.svg`, the mode pill (`bedrock`/`scripted` · `ENV`), a stack-health strip: five dots (mock, Tower, binding, alerts, DynamoDB) green/grey with the service name on hover. `/healthz` already knows this; expose it in the fragment.
2. **The Stage (new, full-width, ~260 px tall)** — an inline SVG scene derived from `hero.svg`: your house on the left, the tower in the middle, Mom's house on the right, a phone near Mom's house, the audit ledger at the tower's foot. It is **driven by the SSE feed and macro steps the page already receives**: a request lights the cyan beam house→tower for 600 ms; a carrier call makes the tower's rings pulse; a refusal flashes the beacon coral; an SMS sends an amber pulse tower→phone and the phone buzzes; a `SUPPRESSED_REVOKED` row shows the shield turning grey with a slash; a revoke/re-grant toggles the shield. Outcome chips (Tower's `reason_codes`, unchanged text) float up from the tower and fade. Nothing in the scene is clickable except the two houses (scroll to Binding pane) — it is a picture of what the panes already say.
3. **Four panes, 2 × 2 under the Stage**, each a glass card with an icon in the header (SVG, inline, from one `icons.svg` sprite):
   - **Conversation** — the four macros become story tiles with a tiny illustration each (Moment 1: SIM glyph; Moment 2: forwarding arrow; Moment 3: Mom's house; Transplant: a phone with a dashed outline), running state (spinner → step badges as a horizontal stepper with ticks/crosses and timings), and the transcript rendered as chat bubbles (Asish/Mom avatar initials, Tower replies with the reason-code chips coloured by meaning). The free-text row stays, restyled.
   - **Carrier controls** — line holders as two rows with a mini "line card" (holder name, status chips for `sim`, `cf`, `reach` reflecting the mock's state), event buttons as icon-buttons with tooltips; faults as a segmented control; the clock as a small analogue/digital widget that advances when +1/+12/+20 is pressed.
   - **Live feed** — a single vertical timeline (newest on top) merging SMS and audit rows, each row with a left icon (SMS amber envelope, audit mint link), the role/template, and relative time; filter chips `all · sms · audit`. Paused state is a banner, not italic text.
   - **Binding** — the QR code centred on a phone-shaped frame with a caption; grants shown as a small consent graph (Mom —watch→ Asish) that updates on revoke/re-grant; `resolve` output as a chip row.
4. **Footer** — the one-line disclaimer, unchanged text.

**Pictures.** All vector, all inline or vendored (`src/demo_ui/static/img/*.svg`, `icons.svg` sprite). No raster photos, no external URLs, no tracking, no fonts from CDNs at runtime. Reuse the `hero.svg` house/tower/phone/shield/ledger groups by copying them into `scene.svg` with ids (`#house-you`, `#tower`, `#rings`, `#beacon`, `#beam-req`, `#beam-sms`, `#house-mom`, `#phone`, `#shield`, `#ledger`) so JS toggles classes, never redraws.

**States to design, not just the happy path:** stack down (every pane shows the same calm "waiting for `make up`" illustration, with the exact command); ENV≠local (pane 2 and macros greyed with the doc-11 reason); Bedrock unavailable (pill shows `scripted` with a tooltip); feed paused; a failed macro step (coral cross, the step name, "see transcript").

## Hard constraints (from doc 11 and the rules)

- No new backend behaviour, no new endpoint except a `GET /fragments/health` if the top-bar strip needs one; no change to `redact.py`, the HX-Request check, the token cookie, the poller or the macro sequencer.
- Every fragment and SSE frame still passes the number filter; the Stage receives only what the feed already carries (role names, template ids, reason codes, timings). No phone number, no holder's number, no key, ever.
- No build step: plain CSS (one `app.css`, CSS variables, nesting is fine), vanilla JS modules for the Stage (`stage.js`), HTMX as-is. No npm, no bundler, no Tailwind CDN, no framework.
- Page weight ≤ 600 KB total; first paint < 1 s on the laptop; Lighthouse accessibility ≥ 95 (contrast on dark, focus rings, aria-live for the feed and step badges, reduced-motion).
- The UI remains laptop-only and never deployed to AWS; `values-eks` stays `enabled: false`.

## Deliverables

```
services/demo-ui/src/demo_ui/
  templates/base.html, index.html, fragments/*.html     restructured per the layout; same fragment names/ids HTMX targets
  static/app.css                                         the design system: tokens, cards, chips, stepper, timeline, phone frame, states
  static/stage.js                                        drives scene.svg from the existing SSE/macro events (class toggles only)
  static/img/scene.svg, icons.svg, empty-state.svg       vector art derived from docs/img/hero.svg
  static/fonts/*.woff2                                   vendored (OFL), with LICENSE alongside
services/demo-ui/tests/
  test_visual.py          Playwright (skip if no browser): screenshots of the five states at 1440×900 into artifacts/screenshots/demo-ui/, compared to
                          tests/visual/baseline/*.png with a 0.5 % pixel tolerance; first run writes baselines and is marked
  test_assets.py          unit: no external URL in templates/static; total static weight ≤ 600 KB; every reason code in codes.py has a colour class
services/demo-ui/README.md     "Look" section with the five screenshots; config unchanged
docs/architecture/components/11-demo-ui.md   §2 gains "Presentation" (Stage, states, asset rules); §13 unchanged
artifacts/screenshots/demo-ui/*.png          generated
docs/submission/build-log/21.md
```

## Steps

1. **architect** — write the Presentation subsection of doc 11 §2 and the asset rules; confirm every Stage trigger maps to an event the page already receives (list them with the fragment/SSE field); stop if any trigger would need new data.
2. **developer** — tokens and base layout → the four panes → the Stage → the five states → fonts/icons. Run `uv run demo-ui` against `make up` continuously; check each pane against the mock events (Asish `sim_swap` → Moment 1 shows `SIM_SWAPPED_RECENT` chip, Stage beacon coral).
3. **tester** — `uv run pytest services/demo-ui -q` (all existing tests green, unchanged), the new `test_assets.py`, `test_visual.py` with baselines; the privacy suite over the new fragments; `make showcase-ui` end to end pressing Moment 1, 2, 3, Transplant with every badge green.
4. **reflect-and-learn** — the HTMX + SVG-scene pattern into the `python` skill (or a new `web-ui` skill) if it proved reusable.

## Acceptance

- Opening http://127.0.0.1:8090 with the stack up shows the Stage and four panes; pressing Moment 1–3 and Transplant animates the Stage in step with the badges, and the feed timeline shows the watcher SMS, `SUPPRESSED_REVOKED`, and the escalation texts with the right icons and colours.
- Stack down shows the waiting illustration with `make up` in every pane, no stack traces, no italic error strings.
- All existing demo-ui tests pass unchanged; `test_assets.py` and `test_visual.py` pass; privacy sweep clean.
- Lighthouse (or axe) accessibility ≥ 95; reduced-motion disables the Stage animations but not the state changes.
- No external request from the page (checked in `test_assets.py` and by the Playwright network log in `test_visual.py`).
- Five screenshots in `artifacts/screenshots/demo-ui/` and in the README.

## Guardrails

- Pretty is not a reason to change meaning: chip text is Tower's reason code verbatim; the transcript is the reference client's, unedited.
- Don't draw a phone number, a fake number, or a redacted-looking number anywhere, including in illustrations ("•••• 0101" is also out).
- Don't add Alexa, Amazon or carrier logos or trade dress; the speaker is a plain cylinder with a light ring.
- If a design element needs data the page doesn't have, drop the element — never add a backend call for decoration.
- No git operations. Final message: files changed, test counts, the five screenshots' paths, anything deferred.
