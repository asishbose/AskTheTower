#!/usr/bin/env python3
"""Append the as-built branches to 03-proactive-path and 04-binding-flow without touching their existing cells.

01-07 were generated outside this repo (finding F13 in deployment-agentcore.md), so their XML is the source. This
script leaves every existing cell byte-for-byte as it is. It inserts one block of new cells (ids `x_*`) between
`<!-- gen_extend:begin -->` / `<!-- gen_extend:end -->` just before `</root>`, and raises `pageHeight` to fit.
Re-running replaces the block, so the output is idempotent. The cells come from gen_deploy's helpers and palette.

- 03 gets the ack and revoke branches (06 §3-§4): reply accepted, ACK_IGNORED_SWAPPED_LINE, tick to escalation[1],
  revoke then SUPPRESSED_REVOKED.
- 04 gets the invite code, grant, watch-settings (04 §9: the page → Alerts edge), watch and revoke steps (04 §3).

    uv run python docs/architecture/diagrams/gen/gen_extend.py            # write both + check
    uv run python docs/architecture/diagrams/gen/gen_extend.py --check    # fail if a file is stale
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check as checker  # noqa: E402
from gen_deploy import BOX, EDGE, ROOT, Page  # noqa: E402

BOX.setdefault("exit", ("#FBEAEA", "#C57B7B"))
EDGE.setdefault("refuse", ("#C57B7B", 2))
BEGIN, END = "<!-- gen_extend:begin -->", "<!-- gen_extend:end -->"
F03 = HERE.parent / "03-proactive-path.drawio"
F04 = HERE.parent / "04-binding-flow.drawio"

COL_W, COL_GAP, X0 = 342, 50, 40
XS = [X0 + i * (COL_W + COL_GAP) for i in range(4)]


def right(p: Page, a: str, b: str, cid: str, label: str = "", kind: str = "grey") -> None:
    """A straight edge from a's right side to b's left side, at a's vertical middle."""
    ax, ay, aw, ah = p.geo[a]
    bx = p.geo[b][0]
    y = ay + ah / 2
    p.edge(cid, a, b, [(ax + aw, y), (bx, y)], label, kind, at=((ax + aw + bx) / 2, y - 9) if label else None)


def ext03() -> tuple[Page, int]:
    p = Page("x03", "x", 1600, 0)
    top = 940
    p.zone("x_zone", 28, top, 1544, 372, "Ack and revoke branches, as built (06 §3–§4) — added by gen_extend.py", "amber", size=13)  # fmt: skip
    r1, r2, r3, r4 = top + 40, top + 128, top + 216, top + 316
    h = 70
    p.box("x_reply", XS[0], r1, COL_W, h, "Watcher replies OK / CANCEL", [
        "SMS reply → SNS inbound topic → Alerts handler → handle_reply (escalation.py:175)",
        "the number is hashed to a line_id at once",
    ], "amber", size=10)  # fmt: skip
    p.box("x_swapq", XS[1], r1, COL_W, h, "Replying line SIM-swapped < 24 h?", [
        "ACK_DISTRUST: its Watch state, else a SIM Swap check; a carrier error counts as swapped (escalation.py:161)",
    ], "white", size=10)  # fmt: skip
    p.box("x_ok", XS[2], r1, COL_W, h, "no → accepted", [
        "audit ok · OK; the parked escalation is cleared; escalation[1] is never texted",
    ], "teal", size=10)  # fmt: skip
    p.box("x_ign", XS[2], r2, COL_W, h, "yes → ACK_IGNORED_SWAPPED_LINE", [
        "audited; the chain keeps waiting as if unacknowledged (escalation.py:207)",
    ], "exit", size=10)  # fmt: skip
    p.box("x_tick", XS[3], r2, COL_W, h, "15 min without a valid ack → escalation[1]", [
        "tick (every poll + rate(5 min)): re-read grant → audit changed → SMS; adds “A reply from the affected line was ignored.”",
    ], "amber", size=10)  # fmt: skip
    right(p, "x_reply", "x_swapq", "x_e1", "", "amber")
    right(p, "x_swapq", "x_ok", "x_e2", "no", "grey")
    sx, sy, sw, sh = p.geo["x_swapq"]
    mx = sx + sw / 2
    p.edge("x_e3", "x_swapq", "x_ign", [(mx, sy + sh), (mx, r2 + h / 2), (XS[2], r2 + h / 2)], "yes", "refuse", at=(mx + 70, r2 + h / 2 - 9))  # fmt: skip
    right(p, "x_ign", "x_tick", "x_e4", "", "amber")

    p.box("x_rev", XS[0], r3, COL_W, h, "Line-holder revokes the grant", [
        "binding page POST /grants/{id}/revoke → Grants.revoked_at (grants.py:142, tower_consent grants.py:89)",
    ], "grey", size=10)  # fmt: skip
    p.box("x_reread", XS[1], r3, COL_W, h, "Re-read just before any send", [
        "deliver() (send.py:173) and the tick (escalation.py:118) resolve the watcher's grant again",
    ], "white", size=10)  # fmt: skip
    p.box("x_supp", XS[2], r3, COL_W, h, "SUPPRESSED_REVOKED", [
        "audit suppressed; nothing sent; no rate claim; a parked escalation is cleared",
    ], "exit", size=10)  # fmt: skip
    p.box("x_poll", XS[3], r3, COL_W, h, "Already revoked at evaluation", [
        "no carrier call; on an event one SUPPRESSED_REVOKED row, on a poll no row (runner.py:45)",
    ], "white", size=10)  # fmt: skip
    right(p, "x_rev", "x_reread", "x_e5")
    right(p, "x_reread", "x_supp", "x_e6", "revoked", "refuse")
    p.box("x_note", 60, r4, 1480, 36, "", [
        "As built the order is re-resolve → rate limit → audit → SMS (send.py:173–216): the audit row exists before any "
        "text. The arrow “Watches.last_state ← facts · audit.append” above is drawn after the send (code-vs-docs.md D10)."
    ], "ghost", dashed=True, size=10, body_size=10)  # fmt: skip
    return p, top + 372 + 30


def ext04() -> tuple[Page, int]:
    p = Page("x04", "x", 1600, 0)
    top = 920
    p.zone("x_zone", 28, top, 1544, 430, "Invite, grant, watch settings, watch and revoke, as built (04 §3, §9) — added by gen_extend.py", "grey", size=13)  # fmt: skip
    r1, r2, r3, r4 = top + 40, top + 140, top + 240, top + 340
    h = 82
    p.box("x_inv", XS[0], r1, COL_W, h, "Asish (grantee) on his own page", [
        "/me → “Create invite code” → POST /me/invite (grants.py:87): 8 letters shown ABCD-EFGH, 24 h, single use (invite.py:40)",
    ], "grey", size=10)  # fmt: skip
    p.box("x_pass", XS[1], r1, COL_W, h, "The code reaches Mom out of band", [
        "said aloud or texted by Asish; letters only, so it can never look like a phone number",
    ], "white", size=10)  # fmt: skip
    p.box("x_grant", XS[2], r1, COL_W, h, "Mom grants on her page", [
        "session from her own bind; POST /grants {invite_code, watch | reachability, alias \"mom\"} → grant() (grants.py:111; tower_consent grants.py:38); invite consumed",
    ], "grey", size=10)  # fmt: skip
    p.box("x_watch", XS[3], r1, COL_W, h, "Asish: “Alexa, watch mom's line”", [
        "watch_line(\"mom\", enable=true) → his own Watch (care) + Alerts /internal/watch → subscribe. The page creates no Watch (D7, grant half open)",
    ], "teal", size=10)  # fmt: skip
    right(p, "x_inv", "x_pass", "x_e1")
    right(p, "x_pass", "x_grant", "x_e2")
    right(p, "x_grant", "x_watch", "x_e3")
    p.box("x_set", XS[0], r2, COL_W, h, "Mom: Watching card on /me (6b)", [
        "profile by behaviour (fraud only / must stay reachable / daytime check-in) + up to 3 contacts in order, from her line's active watch grantees",
    ], "grey", size=10)  # fmt: skip
    p.box("x_save", XS[1], r2, COL_W, h, "POST /me/lines/{line_id}/watch-settings", [
        "set_watch_settings (watch_settings.py:26): owner only (403); contacts need an active watch grant (422); one UpdateItem on her own Watch, requires_ack derived; enabled untouched",
    ], "white", size=10)  # fmt: skip
    p.box("x_saud", XS[2], r2, COL_W, h, "Audit, then Alerts if alerts are on", [
        "one row watch_line · binding · ok, no contact ids; enabled Watch → POST /internal/watch {profile} (watching.py; a failure is swallowed, the polls cover it)",
    ], "white", size=10)  # fmt: skip
    p.box("x_mine", XS[3], r2, COL_W, h, "Mom: “Alexa, watch my line”", [
        "watch_line(self, true) keeps the stored profile and chain (watch_line.py:121); facts.profile reports it, contacts never (06 §11.1)",
    ], "teal", size=10)  # fmt: skip
    right(p, "x_set", "x_save", "x_e6")
    right(p, "x_save", "x_saud", "x_e7")
    right(p, "x_saud", "x_mine", "x_e8")
    p.box("x_rev", XS[0], r3, COL_W, h, "Mom revokes — on the page only", [
        "POST /grants/{id}/revoke (grants.py:144) → revoked_at (tower_consent grants.py); never by voice (04 §3)",
    ], "grey", size=10)  # fmt: skip
    p.box("x_after", XS[1], r3, COL_W, h, "Next read sees it", [
        "Asish's line_is_ok(\"mom\") → NO_CONSENT (resolve.py:89); Alerts drops any alert as SUPPRESSED_REVOKED",
    ], "white", size=10)  # fmt: skip
    p.box("x_left", XS[2], r3, COL_W * 2 + COL_GAP, h, "Also on revoke (D7, D8)", [
        "the grantee's Watch is disabled (watches.py disable_watch) and they leave Mom's contact chain (watches.py:83 remove_contact);",
        "the Alerts watchdog drops subscriptions no enabled, consented Watch needs on its next poll. The page never calls Alerts on revoke.",
    ], "teal", size=10)  # fmt: skip
    right(p, "x_rev", "x_after", "x_e4")
    right(p, "x_after", "x_left", "x_e5")
    p.box("x_note", 60, r4, 1480, 70, "", [
        "Also as built: no code sends the link SMS (step “SMS with link”, D1); Alexa+ gets the URL in next_step only.",
        "The bind calls Number Verification phoneNumberShare — the carrier returns devicePhoneNumber (core.py:240) — not verify(number) as drawn above (D12).",
        "The step label “grant watch to <invite code> as mom” renders without its placeholder: the tag is read as HTML (D13).",
    ], "ghost", dashed=True, size=10, body_size=10)  # fmt: skip
    return p, top + 430 + 30


def apply(path: Path, make: object) -> str:
    text = path.read_text("utf-8")
    text = re.sub(re.escape(BEGIN) + ".*?" + re.escape(END), "", text, flags=re.S)
    page, height = make()  # type: ignore[operator]
    cells = "".join(ET.tostring(c, encoding="unicode") for c in page.cells)
    assert text.count("</root>") == 1, path
    text = text.replace("</root>", f"{BEGIN}{cells}{END}</root>")
    text, n = re.subn(r'pageHeight="\d+"', f'pageHeight="{height}"', text, count=1)
    assert n == 1, path
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="fail if a file on disk differs from the generator")
    args = ap.parse_args()
    bad = 0
    for path, make in ((F03, ext03), (F04, ext04)):
        text = apply(path, make)
        if args.check:
            if path.read_text("utf-8") != text:
                print(f"{path.name} is stale: run gen_extend.py")
                bad += 1
        else:
            path.write_text(text, "utf-8")
            print(f"wrote {path.relative_to(ROOT)}")
        issues = [i for i in checker.check(path) if "x_" in i]
        for i in issues:
            print("  " + i)
        print(f"{path.name}: {len(issues)} issue(s) in the added cells")
        bad += len(issues)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
