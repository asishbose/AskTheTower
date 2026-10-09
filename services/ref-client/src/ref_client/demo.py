"""`ref-client demo`: the showcase order steps 4–7 (testing-and-showcase §4) from the terminal — the three moments
and the transplant story — with the mock admin calls and clock advances between utterances issued by this
script, not by hand.

The script talks to the mock carrier's `/_admin/*` (a simulation aid, 08 §3) and, for the revoke in moment 3,
to the binding page's local admin. It never talks to the store or the carrier APIs; the agent only calls Tower.
Lines are addressed by who holds them; the numbers are read from the mock's own state (the line whose
simulated client id is `phone-asish` / `phone-mom` in `scenarios/demo.yaml`) and never printed or written.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

import httpx

from ref_client.agent import Agent
from ref_client.transcript import ToolCall, Transcript, Turn, write

Who = Literal["asish", "mom"]
DEFAULT_MOCK_URL = "http://localhost:8443"  # mk/vars.mk MOCK_URL
DEFAULT_BINDING_URL = "http://localhost:8081"  # mk/vars.mk BINDING_URL


# --- the script -------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Say:
    text: str
    expect: ToolCall
    codes: tuple[str, ...]  # what the story expects Tower to answer (the golden files say the same)


@dataclass(frozen=True)
class Advance:
    minutes: int
    why: str


@dataclass(frozen=True)
class Fire:
    who: Who
    event: str
    why: str


@dataclass(frozen=True)
class Grant:
    action: Literal["revoke", "grant"]
    why: str


@dataclass(frozen=True)
class Note:
    text: str


Step = Say | Advance | Fire | Grant | Note


@dataclass(frozen=True)
class Story:
    name: str
    title: str
    steps: tuple[Step, ...]
    user: str = "user-asish"


def _c(name: str, **args: Any) -> ToolCall:
    return ToolCall(name, args)


STORIES: tuple[Story, ...] = (
    Story(
        "moment-1",
        "Moment 1 — my phone just lost signal",
        (
            Say("Is my line OK?", _c("line_is_ok", line="self"), ("OK",)),
            Advance(12, "mock clock +12 min; the demo timeline moves Asish's SIM to another device"),
            Say(
                "My phone just lost signal. Is my line OK?",
                _c("line_is_ok", line="self"),
                ("SIM_SWAPPED_RECENT",),
            ),
        ),
    ),
    Story(
        "moment-2",
        "Moment 2 — is anything forwarding my calls?",
        (
            Advance(8, "mock clock +8 min; the demo timeline sets call forwarding on Asish's line (cf_set)"),
            Say(
                "Is anything forwarding my calls?",
                _c("line_is_ok", line="self"),
                ("SIM_SWAPPED_RECENT", "CALL_FORWARDING_SET"),
            ),
        ),
    ),
    Story(
        "moment-3",
        "Moment 3 — Mom's line, a watch, a revoke",
        (
            Say("Is Mom's line OK?", _c("line_is_ok", line="mom"), ("OK",)),
            Say("Watch Mom's line for me.", _c("watch_line", line="mom", enable=True), ("OK",)),
            Fire("mom", "sim_swap", "mock: SIM swap on Mom's line"),
            Note("Alerts texts the watcher now — the phone buzzes (SMS log locally; make showcase-alerts)."),
            Grant("revoke", "Mom revokes Asish's watch grant (binding page)"),
            Fire("mom", "sim_swap", "mock: SIM swap on Mom's line again"),
            Note("No text this time: Alerts re-reads the grant and audits SUPPRESSED_REVOKED."),
            Say("Is Mom's line OK?", _c("line_is_ok", line="mom"), ("NO_CONSENT",)),
            Grant("grant", "demo reset: Mom grants the watch again"),
        ),
    ),
    Story(
        "transplant",
        "Transplant closing story — the line must stay reachable",
        (
            Say("Turn on alerts for my line.", _c("watch_line", line="self", enable=True), ("OK",)),
            Fire("asish", "unreachable", "mock: Asish's phone drops off the network"),
            Advance(20, "mock clock +20 min dark"),
            Note("Alerts' transplant rule: 20 min dark → the partner's text (make showcase-alerts)."),
            Say("Is my phone on?", _c("is_reachable", line="self"), ("UNREACHABLE",)),
            Advance(15, "mock clock +15 min, no acknowledgement"),
            Note("15 more minutes with no reply → the second contact's text."),
            Fire("asish", "reachable", "mock: Asish's phone is back on the network"),
            Say("Is my phone reachable now?", _c("is_reachable", line="self"), ("OK",)),
        ),
    ),
)
STORY_NAMES = tuple(s.name for s in STORIES)


# --- the controls between utterances ---------------------------------------------------------------------
class GrantControl(Protocol):
    async def set_mom_grant(self, action: Literal["revoke", "grant"]) -> None: ...


class BindingAdminGrants:
    """Compose/AWS: `POST {BINDING_URL}/_admin/grants` on the binding page (local admin, `BIND_ADMIN=1`).
    Body: `{owner_user_id, grantee_user_id, grant, alias, action}`. The endpoint is wired by prompt 12."""

    def __init__(self, base_url: str, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.url = base_url.rstrip("/") + "/_admin/grants"
        self._http = httpx.AsyncClient(transport=transport, timeout=10.0)

    async def set_mom_grant(self, action: Literal["revoke", "grant"]) -> None:
        body = {
            "owner_user_id": "user-mom",
            "grantee_user_id": "user-asish",
            "grant": "watch",
            "alias": "mom",
            "action": action,
        }
        r = await self._http.post(self.url, json=body)
        if r.status_code == 404:
            raise DemoError(
                f"{self.url} answered 404: the binding page's local grant admin is needed for moment 3 "
                "(TOWER_ENV=local, BIND_ADMIN=1)."
            )
        r.raise_for_status()

    async def aclose(self) -> None:
        await self._http.aclose()


class DemoError(RuntimeError):
    pass


@dataclass
class Control:
    """Mock admin + grant control. `on_reset` / `on_advance` let an in-process run move Tower's clock with the
    mock's (in compose Tower reads the mock clock itself via `TOWER_CLOCK_URL`)."""

    mock: httpx.AsyncClient
    grants: GrantControl
    on_reset: Callable[[], Awaitable[None]] | None = None
    on_advance: Callable[[float], Awaitable[None]] | None = None
    _lines: dict[str, str] = field(default_factory=dict)

    async def reset(self) -> None:
        r = await self.mock.post("/_admin/scenarios/load", json={"name": "demo"})
        r.raise_for_status()
        r = await self.mock.get("/_admin/state")
        r.raise_for_status()
        lines: dict[str, Any] = r.json()["lines"]
        for who in ("asish", "mom"):  # demo.yaml: the simulated client id on each line names its holder
            found = [
                m for m, line in lines.items() if f"phone-{who}" in line.get("mobile_data_client_ids", [])
            ]
            if len(found) != 1:
                raise DemoError(f"the mock's demo scenario has no single line for phone-{who}")
            self._lines[who] = found[0]
        if self.on_reset:
            await self.on_reset()

    async def advance(self, minutes: int) -> list[str]:
        r = await self.mock.post("/_admin/clock", json={"advance_s": minutes * 60})
        r.raise_for_status()
        if self.on_advance:
            await self.on_advance(minutes * 60)
        return [str(f.get("event", "")) for f in r.json().get("fired", [])]

    async def fire(self, who: Who, event: str) -> None:
        r = await self.mock.post(f"/_admin/lines/{self._lines[who]}/events", json={"event": event})
        r.raise_for_status()


def http_control(mock_url: str | None = None, binding_url: str | None = None) -> Control:
    mock = httpx.AsyncClient(
        base_url=mock_url or os.environ.get("MOCK_URL") or DEFAULT_MOCK_URL, timeout=10.0
    )
    grants = BindingAdminGrants(binding_url or os.environ.get("BINDING_URL") or DEFAULT_BINDING_URL)
    return Control(mock=mock, grants=grants)


# --- running it -------------------------------------------------------------------------------------------
@dataclass
class DemoRun:
    transcripts: list[Transcript] = field(default_factory=list)
    mismatches: list[str] = field(default_factory=list)


async def run_demo(
    agent_for: Callable[[str], Awaitable[Agent]],
    control: Control,
    *,
    env: str = "local",
    stories: tuple[str, ...] = STORY_NAMES,
    out_dir: Path | None = None,
    echo: Callable[[str], None] = print,
    pause: Callable[[Story], None] | None = None,
) -> DemoRun:
    """Run the stories in order on one mock timeline. `agent_for(user_id)` gives an agent connected to Tower
    as that user. Prints each spoken line; writes `<out_dir>/<story>.json` when `out_dir` is set."""
    run = DemoRun()
    await control.reset()
    selected = [s for s in STORIES if s.name in stories]
    if any(isinstance(step, Grant) for s in selected for step in s.steps):
        await control.grants.set_mom_grant("grant")  # a re-run starts from the seeded grant
    for story in STORIES:
        if story.name not in stories:
            continue
        if pause is not None:
            pause(story)  # `make showcase`: "press enter for step 4: moment 1"
        agent = await agent_for(story.user)
        t = Transcript(story.name, story.title, story.user, agent.name, agent.model_id, env)
        echo(f"\n=== {story.title} ===")
        for step in story.steps:
            await _step(step, agent, control, t, run, echo)
        run.transcripts.append(t)
        if out_dir is not None:
            echo(f"    transcript → {write(t, out_dir)}")
    return run


async def _step(step: Step, agent: Agent, control: Control, t: Transcript, run: DemoRun, echo: Any) -> None:
    if isinstance(step, Advance):
        fired = await control.advance(step.minutes)
        text = step.why + (f" (fired: {', '.join(fired)})" if fired else "")
        t.control(text)
        echo(f"  [mock] {text}")
    elif isinstance(step, Fire):
        await control.fire(step.who, step.event)
        t.control(step.why)
        echo(f"  [mock] {step.why}")
    elif isinstance(step, Grant):
        await control.grants.set_mom_grant(step.action)
        t.control(step.why)
        echo(f"  [consent] {step.why}")
    elif isinstance(step, Note):
        t.note(step.text)
        echo(f"  ({step.text})")
    else:
        turn: Turn = await agent.ask(step.text, expect=step.expect)
        t.turn(turn)
        calls = ", ".join(f"{c.name}({_args(c.args)})" for c in turn.tool_calls) or "no tool"
        echo(f"  you> {step.text}")
        echo(f"       → {calls}  {turn.reason_codes}")
        echo(f"  ref> {turn.spoken}")
        if tuple(turn.reason_codes) != step.codes:
            run.mismatches.append(
                f"{t.story}: {step.text!r} → {turn.reason_codes}, expected {list(step.codes)}"
            )


def _args(args: dict[str, Any]) -> str:
    return ", ".join(f"{k}={v}" for k, v in args.items())
