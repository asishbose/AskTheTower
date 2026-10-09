#!/usr/bin/env python3
"""Generate 11-demo-ui.drawio (two pages): the demo control room — never hand-edit the XML.

Page 1: ENV=local — the four panes and every endpoint each consumes on the compose stack.
Page 2: ENV=aws — the same UI on the laptop, and what a laptop can and cannot reach in the account.

Same palette and Page helpers as gen_deploy.py (08) and gen_flows.py (09, 10). The demo UI is not built yet, so every
box of it is dashed; the services it calls are built and solid; an endpoint that does not exist yet is a dashed edge
with its gap number (G1–G6 in components/11-demo-ui.md §10). Every file:line was read on 2026-10-09.

    uv run python docs/architecture/diagrams/gen/gen_demo_ui.py            # write + check
    uv run python docs/architecture/diagrams/gen/gen_demo_ui.py --check    # fail if the file is stale
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check as checker  # noqa: E402
from gen_deploy import ROOT, Page, esc  # noqa: E402
from gen_flows import header, titles  # noqa: E402

OUT = HERE.parent / "11-demo-ui.drawio"


def lbl(*lines: str) -> str:
    return "<br>".join(esc(x) for x in lines)


# =====================================================================================================================
# Page 1 — ENV=local
# =====================================================================================================================

PANE_X, PANE_W = 90, 500
TGT_X, TGT_W = 910, 470
LBL_X = 750


def page_local() -> Page:
    p = Page("11_local", "1 ENV=local", 1960, 1360)
    titles(
        p,
        "11 · Demo UI (control room): four panes, ENV=local",
        "Demo tooling, laptop only, not built yet (dashed). It drives only what make demo and the showcase "
        "scripts already drive; it owns nothing.",
        "Teal = the conversation (request path) · amber = the live feed (proactive evidence) · grey = demo "
        "controls and binding · dashed edge = endpoint missing today (gap Gn, doc 11 §10).",
    )

    p.zone("z_laptop", 30, 100, 1410, 1010, "Presenter's laptop (ENV=local)", kind="grey")
    p.box("browser", 60, 140, 560, 70, "Browser: desktop or phone (mobile layout)", [
        "one static page, HTMX, no build step · served on 127.0.0.1:8090 (LAN only with a token, open decision 7)",
    ], kind="white")  # fmt: skip
    p.zone("z_ui", 60, 250, 560, 840, "services/demo-ui: not built yet", kind="white", dashed=True)

    p.box("p1", PANE_X, 300, PANE_W, 160, "1 · Conversation", [
        "type as Asish or Mom · macros: Moment 1 · Moment 2 · Moment 3 · Transplant",
        "ref_client as a library: TowerClient (mcp_client.py:296), BedrockAgent (agent.py:120),",
        "ScriptedAgent (agent.py:211) without Bedrock, and the page says so",
        "shows tool call · reason_codes · summary / spoken · next_step; badge = codes vs STORIES",
        "next_step bind_line → url → QR code in pane 4 (D1: nothing texts the link)",
        "macros replay ref_client.demo.STORIES (demo.py:76) on one timeline, one run at a time",
    ], kind="teal", dashed=True)  # fmt: skip
    p.box("p2", PANE_X, 490, PANE_W, 160, "2 · Carrier controls (mock /_admin)", [
        "load demo · clock +1 / +12 / +20 min · fire sim_swap cf_set cf_clear unreachable reachable",
        "by holder (Asish, Mom), never by number: the E.164 keys of /_admin/state stay in server memory",
        "faults timeout / 500 / 429 · line state and subscriptions shown by the mock's opaque ref",
        "no admin token exists today (G1): the gate is MOCK_ADMIN=1 plus the network",
        "events take the raw number in the path (admin.py:76); accept the ref instead (G2)",
    ], kind="grey", dashed=True)  # fmt: skip
    p.box("p3", PANE_X, 680, PANE_W, 160, "3 · Live feed (SSE, one poller, every 2 s)", [
        "audit: list_lines(owner) → list_for_line(line, owner): Asish's log + Mom's log, newest 50",
        "sms: GET /internal/sent does not exist (G3); until then audit message_ref only",
        "also per tick: mock /_admin/state (pane 2) and binding /_admin/tables (pane 4)",
        "no DynamoDB Streams · the chain check stays on the binding page /me (the UI holds no keys)",
    ], kind="amber", dashed=True)  # fmt: skip
    p.box("p4", PANE_X, 870, PANE_W, 150, "4 · Binding (QR code · grants · revoke)", [
        "QR code of POST /_admin/bind-tokens {user_id} → url + ?as=phone-<who>, drawn by the UI",
        "grants: GET /_admin/tables?format=json · resolve: GET /_admin/resolve?user=..&line=..",
        "revoke / re-grant: POST /_admin/grants {owner, grantee, grant, alias, action}",
        "D7: a revoke leaves Mom's subscriptions ACTIVE; the captions say so",
    ], kind="grey", dashed=True)  # fmt: skip
    p.box("redact", PANE_X, 1035, PANE_W, 40, "", [
        "every HTML fragment and SSE frame → E.164 filter (transcript.py:21) · uvicorn access_log off",
    ], kind="white", dashed=True)  # fmt: skip

    p.zone("z_compose", 880, 250, 530, 840, "compose stack (built)", kind="slate")
    p.box("tower", TGT_X, 350, TGT_W, 110, "tower-mcp :8080 /mcp", [
        "MCP tools/list · tools/call · Bearer TOWER_BEARER + X-Tower-User",
        "each turn is an ordinary check: consent read, carrier calls, audit row",
        "the UI adds nothing to this path",
    ], kind="teal")  # fmt: skip
    p.box("mock", TGT_X, 490, TGT_W, 160, "mock-carrier :8443 /_admin/* (MOCK_ADMIN=1)", [
        "GET /state :98 · POST /scenarios/load :53 · GET /scenarios :49",
        "GET /clock :72 · POST /clock {advance_s} :61",
        "POST /lines/{msisdn}/events {event} :76",
        "POST /faults {kind, n} :85 · DELETE /faults :93 · GET /healthz (app.py:122)",
        "(routers/admin.py; mounted at app.py:119)",
    ], kind="grey")  # fmt: skip
    p.box("alerts", TGT_X, 680, TGT_W, 70, "alerts :8082", [
        "GET /healthz (local.py:99) · SMS bodies only in log lines (send_backends.py:48)",
    ], kind="amber")  # fmt: skip
    p.box("ddb", TGT_X, 770, TGT_W, 70, "DynamoDB Local :8000 (read only)", [
        "Lines by_owner (bind.py:124) · Audit via reader.py:63, owner check :57",
    ], kind="grey")  # fmt: skip
    p.box("binding", TGT_X, 870, TGT_W, 150, "binding-page :8081 /_admin/*", [
        "POST /bind-tokens {user_id} :75 · GET /tables?format=json :58",
        "GET /resolve?user=..&line=.. :68 · POST /grants {...} :95",
        "404 unless TOWER_ENV=local and BIND_ADMIN=1 (config.py:57)",
        "(routes/admin.py) · GET /bind/{token} (bind.py:157) for the phone",
    ], kind="grey")  # fmt: skip

    p.zone("z_aws", 1470, 250, 460, 200, "AWS: Bedrock only (optional)", kind="amber")
    p.box("bedrock", 1500, 300, 400, 110, "Bedrock Converse (tool use)", [
        "BEDROCK_MODEL_ID (amazon.nova-micro-v1:0) · AWS_PROFILE",
        "the repo's only model call stays in ref_client/agent.py",
        "absent → ScriptedAgent; free text turned off",
    ], kind="white")  # fmt: skip

    header(p, "phone", TGT_X, 1150, TGT_W, 56, "Phone on the same Wi-Fi (scans the QR code)", amber=True)

    p.edge("e_br", "browser", "z_ui", [(560, 210), (560, 250)], lbl("HTMX + SSE GET /events"), at=(500, 230))
    p.edge("e_bed", "p1", "bedrock", [(590, 330), (1500, 330)], lbl("Converse"), kind="teal", at=(LBL_X, 330))
    p.edge("e_tow", "p1", "tower", [(590, 405), (910, 405)], lbl("MCP Streamable HTTP"), kind="teal",
           at=(LBL_X, 405))  # fmt: skip
    p.edge("e_mock", "p2", "mock", [(590, 570), (910, 570)], lbl("/_admin/* (no token: G1)"), at=(LBL_X, 570))
    p.edge("e_al", "p3", "alerts", [(590, 715), (910, 715)], lbl("GET /internal/sent: G3"), kind="amber",
           dashed=True, at=(LBL_X, 715))  # fmt: skip
    p.edge("e_ddb", "p3", "ddb", [(590, 805), (910, 805)], lbl("Query, read as owner"), kind="amber",
           at=(LBL_X, 805))  # fmt: skip
    p.edge("e_bind", "p4", "binding", [(590, 945), (910, 945)], lbl("/_admin bind-tokens · grants"),
           at=(LBL_X, 945))  # fmt: skip
    p.edge("e_phone", "phone", "binding", [(1145, 1150), (1145, 1020)],
           lbl("GET /bind/{token}?as=phone-asish"), at=(1145, 1125))  # fmt: skip

    p.box("never", 30, 1240, 1900, 96, "Never (doc 11 §8)", [
        "1 decides nothing: no tower_policy, no camara_client, no CAMARA path · 2 calls the carrier only "
        "under /_admin (a simulation aid) · 3 renders no phone number",
        "4 writes no consent: grants and revokes go through the binding page; Reset reuses the make seed "
        "code (open decision 5) · 5 reads an audit only as its line's owner",
        "6 cannot make Alexa+ speak first · 7 is never deployed to AWS: no ECR repository, no Terraform, "
        "values-eks enabled=false · 8 adds nothing to the hot path",
        "Divergences shown as captions, not hidden: D1 (link not texted → QR code), D7 (revoke leaves "
        "subscriptions), D9/D8 (transplant text and escalation not reachable by voice), D15 (SMS without a name)",
    ], kind="white", body_size=10)  # fmt: skip
    return p


# =====================================================================================================================
# Page 2 — ENV=aws: the same UI on the laptop, pointed at the account
# =====================================================================================================================

P2_PX, P2_PW = 90, 580
A_X, A_W = 1040, 420
A_LBL = 835


def page_aws() -> Page:
    p = Page("11_aws", "2 ENV=aws (laptop)", 1960, 1300)
    titles(
        p,
        "11 · Demo UI, ENV=aws: on the laptop, pointed at the account, never deployed into it",
        "The same container (or uv run) with deploy/.env.aws loaded. Nothing is created in AWS. Each pane "
        "works only as far as a laptop can reach.",
        "Solid edge = reachable today · dashed = only with a gap closed (G5 tunnel, G6 second JWT) · "
        "no edge = no laptop path at all.",
    )

    p.zone("z_laptop", 30, 100, 700, 900, "Presenter's laptop", kind="grey")
    p.zone("z_ui", 60, 140, 640, 820, "services/demo-ui: not built yet", kind="white", dashed=True)
    p.box("p1", P2_PX, 190, P2_PW, 180, "1 · Conversation: works", [
        "TOWER_URL = the Runtime URL from deploy/.env.aws",
        "TOWER_BEARER must be a JWT; D21: an empty discovery URL means every call gets 401",
        "X-Tower-User is ignored on AWS: Asish only, unless Mom has her own JWT (G6)",
        "Bedrock with the att profile, or ScriptedAgent",
        "macros off: they need pane 2",
    ], kind="teal", dashed=True)  # fmt: skip
    p.box("p2", P2_PX, 400, P2_PW, 180, "2 · Carrier controls: off", [
        "MOCK_URL is empty (render_env.py:29)",
        "the ALB is internal and never forwards /_admin (modules/mock_carrier/main.tf:7)",
        "make seed-aws uses ECS Exec, one command per call: too slow for buttons",
        "G5: an SSM port-forward to the task → MOCK_URL=http://localhost:18443",
        "the same gap stops make demo ENV=aws today",
    ], kind="ghost", dashed=True)  # fmt: skip
    p.box("p3", P2_PX, 610, P2_PW, 180, "3 · Live feed: audit only", [
        "DynamoDB with the att profile; DYNAMO_ENDPOINT empty; TOWER_TABLE_PREFIX from .env.aws",
        "polled every 5 s: about 3 reads/s while the page is open, cents per day",
        "SMS: no laptop read path (Lambda + SNS); the text lands on the real phone",
        "the audit row with message_ref is the evidence on screen",
    ], kind="amber", dashed=True)  # fmt: skip
    p.box("p4", P2_PX, 820, P2_PW, 120, "4 · Binding: QR code from next_step only", [
        "/_admin/* answers 404 on AWS (config.py:57): no grants list, no revoke from the UI",
        "the bind link comes from Tower's NOT_BOUND next_step.url (next_step.py:41)",
        "grants and revokes happen on the resident's own phone at /me (grants.py:78, :141)",
    ], kind="grey", dashed=True)  # fmt: skip

    p.zone("z_aws", 1000, 100, 930, 900, "AWS account (built; the demo UI is not in it)", kind="slate")
    p.box("bedrock", A_X, 190, A_W, 70, "Bedrock Converse", ["us-east-1 · BEDROCK_MODEL_ID"], kind="white")
    p.box("runtime", A_X, 280, A_W, 90, "Tower on AgentCore Runtime", [
        "MCP over HTTPS · JWT sub → user_id",
        "Gateway + Identity → mock (unchanged)",
    ], kind="teal")  # fmt: skip
    p.box("mock", A_X, 400, A_W, 180, "Mock carrier on Fargate", [
        "internal ALB: CAMARA prefixes and /oauth2 only",
        "/_admin/* reachable only inside the task",
        "ECS Exec enabled (aws_seed.py uses it)",
        "SSM port-forward to :8443 would serve /_admin",
        "to the laptop alone, nothing public (G5)",
    ], kind="grey")  # fmt: skip
    p.box("ddb", A_X, 610, A_W, 80, "DynamoDB (Lines, Audit)", [
        "Query Lines by_owner · Query Audit, read as owner",
    ], kind="grey")  # fmt: skip
    p.box("alerts", A_X, 710, A_W, 80, "Alerts Lambda + SNS", [
        "API Gateway exposes /hooks/* only: nothing to read",
    ], kind="amber")  # fmt: skip
    p.box("apigw", A_X, 820, A_W, 120, "Binding page: API Gateway + Lambda", [
        "/bind/{token} · /bind/callback · /me (session)",
        "/_admin/* → 404 (TOWER_ENV=aws)",
    ], kind="grey")  # fmt: skip
    p.box("absent", 1500, 190, 400, 180, "Not in the account, by design", [
        "no demo-ui ECR repository (SERVICES stays five)",
        "no Terraform resource",
        "Helm values-eks.yaml: enabled=false",
        "nothing listening publicly for the UI",
        "a static test in tests/aws/ checks all four",
    ], kind="white")  # fmt: skip

    header(p, "phone", A_X, 1060, A_W, 56, "Real phone (Wi-Fi off for binding)", amber=True)

    p.edge("e_bed", "p1", "bedrock", [(670, 225), (1040, 225)], lbl("Converse (att profile)"), kind="teal",
           at=(A_LBL, 225))  # fmt: skip
    p.edge("e_rt", "p1", "runtime", [(670, 325), (1040, 325)], lbl("MCP + JWT (one per persona: G6)"),
           kind="teal", at=(A_LBL, 325))  # fmt: skip
    p.edge("e_mock", "p2", "mock", [(670, 490), (1040, 490)], lbl("only via SSM port-forward (G5)"),
           kind="ghost", dashed=True, at=(A_LBL, 490))  # fmt: skip
    p.edge("e_ddb", "p3", "ddb", [(670, 650), (1040, 650)], lbl("Query as owner"), kind="amber",
           at=(A_LBL, 650))  # fmt: skip
    p.edge("e_bind", "p4", "apigw", [(670, 880), (1040, 880)], lbl("QR code of next_step.url only"),
           at=(A_LBL, 880))  # fmt: skip
    p.edge("e_sms", "alerts", "phone", [(1460, 750), (1640, 750), (1640, 1088), (1460, 1088)],
           lbl("SNS SMS: the real buzz"), kind="amber", at=(1640, 900))  # fmt: skip
    p.edge("e_phone", "phone", "apigw", [(1250, 1060), (1250, 940)], lbl("bind link over mobile data"),
           at=(1250, 1030))  # fmt: skip

    p.box("note", 30, 1150, 960, 110, "What ENV=aws can demonstrate from the laptop", [
        "the conversation as Asish against the real Runtime, the audit feed, and the bind link as a QR code",
        "not the macros: Moment 1–3 and Transplant need the mock's clock and events (G5)",
        "the video's Alexa+ simulator path does not depend on the UI at all",
    ], kind="white", body_size=10)  # fmt: skip
    return p


def build() -> str:
    mx = ET.Element("mxfile", host="app.diagrams.net", agent="Ask the Tower design generator", type="device")
    for page in (page_local(), page_aws()):
        mx.append(page.element())
    ET.indent(mx, space="  ")
    return ET.tostring(mx, encoding="unicode") + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="fail if the file on disk differs from the generator")
    args = ap.parse_args()
    text = build()
    if args.check:
        if not OUT.exists() or OUT.read_text("utf-8") != text:
            print(f"{OUT.name} is stale: run gen_demo_ui.py")
            return 1
    else:
        OUT.write_text(text, "utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}")
    issues = checker.check(OUT)
    for i in issues:
        print("  " + i)
    print(f"{OUT.name}: check {len(issues)} issue(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
