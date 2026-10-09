"""`/_admin/*` — the mock's control surface (08 §3). Not CAMARA; a simulation aid, mounted only when
`MOCK_ADMIN=1`. Every change goes through `Runtime`, so the same calls give the same state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import AliasChoices, BaseModel, Field

from mock_carrier.clock import iso, parse_iso
from mock_carrier.runtime import AdminError
from mock_carrier.scenarios import ScenarioError, list_scenarios

if TYPE_CHECKING:
    from mock_carrier.runtime import Runtime


class LoadScenario(BaseModel):
    name: str = Field(examples=["demo"])
    variant: str | None = Field(default=None, examples=["recovered"])


class ClockChange(BaseModel):
    now: str | None = Field(
        default=None, description="RFC 3339 time to set", examples=["2026-10-05T14:12:00Z"]
    )
    advance_s: float | None = Field(default=None, ge=0, description="seconds to move forward", examples=[720])


class LineEvent(BaseModel):
    event: Literal["sim_swap", "cf_set", "cf_clear", "reachable", "unreachable"] = Field(
        validation_alias=AliasChoices("event", "type"), description="`type` is accepted as an alias (06 §8)"
    )
    connectivity: list[Literal["DATA", "SMS"]] | None = None


class Fault(BaseModel):
    kind: Literal["timeout", "500", "429"]
    n: int = Field(default=1, ge=1, le=1000)


def router(rt: Runtime) -> APIRouter:
    r = APIRouter(prefix="/_admin", tags=["mock: admin (simulation aid)"])

    def bad(exc: Exception) -> HTTPException:
        return HTTPException(status_code=400, detail=str(exc))

    @r.get("/scenarios", summary="List scenario files")
    async def scenarios() -> dict[str, Any]:
        return {"scenarios": list_scenarios(rt.settings.scenarios_dir), "loaded": rt.state.scenario}

    @r.post("/scenarios/load", summary="Reset all state to a scenario")
    async def load(body: LoadScenario) -> dict[str, Any]:
        try:
            rt.load(body.name, body.variant)
        except ScenarioError as exc:
            raise bad(exc) from exc
        return {"scenario": rt.state.scenario, "variant": rt.state.variant, "clock": iso(rt.now())}

    @r.post("/clock", summary="Set or advance the clock; due timeline events fire")
    async def clock(body: ClockChange) -> dict[str, Any]:
        if body.now is None and body.advance_s is None:
            raise bad(ValueError("give `now` or `advance_s`"))
        try:
            when = parse_iso(body.now) if body.now else None
            fired = await rt.set_clock(now=when, advance_s=body.advance_s)
        except (ValueError, AdminError) as exc:
            raise bad(exc) from exc
        return {"clock": iso(rt.now()), "fired": [f.dump() for f in fired]}

    @r.get("/clock", summary="Current mock time")
    async def get_clock() -> dict[str, Any]:
        return {"clock": iso(rt.now())}

    @r.post("/lines/{msisdn}/events", summary="Fire a line event; subscriptions are notified")
    async def line_event(msisdn: str, body: LineEvent) -> dict[str, Any]:
        try:
            fired = await rt.fire(msisdn, body.event, connectivity=list(body.connectivity or []) or None)
        except AdminError as exc:
            raise HTTPException(status_code=404 if "line" in str(exc) else 400, detail=str(exc)) from exc
        line = rt.state.lines[msisdn]
        return {"fired": fired.dump(), "line": line.dump()}

    @r.post("/faults", summary="Inject timeout / 500 / 429 for the next n CAMARA calls")
    async def faults(body: Fault) -> dict[str, Any]:
        try:
            rt.add_fault(body.kind, body.n)
        except AdminError as exc:
            raise bad(exc) from exc
        return {"faults": list(rt.state.faults)}

    @r.delete("/faults", summary="Clear pending faults")
    async def clear_faults() -> dict[str, Any]:
        rt.state.faults.clear()
        return {"faults": []}

    @r.get("/state", summary="Dump all state (lines, subscriptions, deliveries, faults, loopback sink)")
    async def state() -> dict[str, Any]:
        return rt.state.dump(rt.now())

    @r.get("/sink", summary="CloudEvents delivered to the loopback sink (https://sink.mock.local/...)")
    async def sink() -> dict[str, Any]:
        return {"events": list(rt.state.sink_inbox)}

    return r
