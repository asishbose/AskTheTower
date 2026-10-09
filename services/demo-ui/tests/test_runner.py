"""Doc 11 §5: macros = `STORIES` through `run_demo(reset=False, on_step=…)`: Reset first, earlier stories
replayed, one run at a time, mismatches shown, failures stop the run with the reason. Fakes only."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from demo_ui.runner import MACROS, Busy, Runner, plan
from ref_client.demo import STORIES, Control

from .fakes import MOM_REF, Recorder, StoryAgent, dump

pytestmark = pytest.mark.unit


class Noop:
    async def set_mom_grant(self, action: Any) -> None:
        return None

    async def save_transplant(self) -> None:
        return None

    async def reset(self) -> None:
        return None


def make_runner(
    rec: Recorder, agent: StoryAgent | None = None, reset_error: Exception | None = None
) -> tuple[Runner, list[tuple[str, str]], list[str]]:
    published: list[tuple[str, str]] = []
    resets: list[str] = []
    mock = httpx.AsyncClient(transport=rec.mock(), base_url="http://mock.test")
    control = Control(mock=mock, grants=Noop(), settings=Noop())

    async def reset() -> None:
        resets.append("seed")
        if reset_error:
            raise reset_error

    @asynccontextmanager
    async def agents() -> AsyncIterator[Callable[[str], Any]]:
        async def agent_for(user_id: str) -> StoryAgent:
            return agent or StoryAgent()

        yield agent_for

    runner = Runner(
        reset=reset,
        control=lambda: control,
        agents=agents,
        publish=lambda e, h: published.append((e, h)),
        agent_label="scripted",
    )
    return runner, published, resets


def test_plan_replays_everything_before() -> None:
    assert plan("moment-1") == (("moment-1",), ())
    assert plan("moment-3") == (("moment-1", "moment-2", "moment-3"), ("moment-1", "moment-2"))
    assert [m for m, _ in MACROS] == [s.name for s in STORIES]
    with pytest.raises(KeyError):
        plan("moment-4")


async def test_moment_2_resets_replays_moment_1_and_passes() -> None:
    rec = Recorder()
    runner, published, resets = make_runner(rec)
    result = await runner.run("moment-2")
    assert resets == ["seed"]
    assert result.error is None and result.failed == 0
    assert result.steps == len(STORIES[0].steps) + len(STORIES[1].steps)
    turns = [h for e, h in published if e == "turn"]
    assert len(turns) == result.steps
    assert all("replay" in h for h in turns[: len(STORIES[0].steps)])
    assert not any("replay" in h for h in turns[len(STORIES[0].steps) :])
    assert "/_admin/scenarios/load" not in dump(rec.requests)  # Reset is the seed, not run_demo's reload
    assert "2 steps" not in published[-1][1] and "0 mismatched" in published[-1][1]


async def test_moment_3_fires_by_ref_only() -> None:
    rec = Recorder()
    runner, _, _ = make_runner(rec)
    await runner.run("moment-3")
    fires = [r for r in rec.requests if r.url.path.endswith("/events")]
    assert fires and all(r.url.path == f"/_admin/lines/{MOM_REF}/events" for r in fires)
    assert "+1" not in dump(rec.requests)


async def test_mismatch_is_a_red_badge_and_the_run_goes_on() -> None:
    rec = Recorder()
    runner, published, _ = make_runner(rec, StoryAgent(wrong="Is my line OK?"))
    result = await runner.run("moment-1")
    assert result.failed == 1 and result.steps == len(STORIES[0].steps)
    bad = [h for e, h in published if e == "turn" and "FAIL" in h]
    assert len(bad) == 1 and "CARRIER_ERROR" in bad[0] and "expected" in bad[0]
    assert "1 mismatched" in published[-1][1]


async def test_reset_failure_stops_with_the_reason() -> None:
    from demo_ui.clients import Unavailable

    rec = Recorder()
    runner, published, _ = make_runner(rec, reset_error=Unavailable("Reset failed: SeedError: x"))
    result = await runner.run("moment-1")
    assert result.error and "Reset failed" in result.error
    assert "stopped" in published[-1][1] and not [e for e, _ in published if e == "turn"]


async def test_mock_down_stops_the_run() -> None:
    rec = Recorder(status=401)
    runner, published, _ = make_runner(rec)
    result = await runner.run("moment-1")
    assert result.error is not None and "stopped" in published[-1][1]


async def test_one_run_at_a_time() -> None:
    rec = Recorder()
    gate = asyncio.Event()
    runner, _, _ = make_runner(rec)
    original = runner.reset

    async def slow_reset() -> None:
        await gate.wait()
        await original()

    runner.reset = slow_reset
    task = runner.start("moment-1")
    with pytest.raises(Busy):
        runner.start("moment-2")
    gate.set()
    await task
    assert not runner.busy
    with pytest.raises(KeyError):
        runner.start("nope")


async def test_bind_line_next_step_becomes_a_qr_frame() -> None:
    rec = Recorder()
    agent = StoryAgent(next_step={"kind": "bind_line", "url": "http://localhost:8081/bind/abc"})
    runner, published, _ = make_runner(rec, agent)
    await runner.run("moment-1")
    qrs = [h for e, h in published if e == "qr"]
    assert qrs and "<svg" in qrs[0] and "as=phone-asish" in qrs[0] and "D1" in qrs[0]
