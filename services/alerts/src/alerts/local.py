"""Local runner: one FastAPI app (hooks + internal API + health) and an in-process scheduler that calls the
same `poll` the Lambda runs, on the 10 §3 cadences divided by `ALERTS_CLOCK_SCALE`.

    uv run python -m alerts.local          # or: alerts-local

| Job | Simulated cadence | Real interval at scale 60 |
|---|---|---|
| poll `transplant` | 5 min (`ALERTS_TRANSPLANT_POLL_S`) | 5 s |
| poll `care` | 30 min (`ALERTS_CARE_POLL_S`) | 30 s |
| poll `self` | daily (`ALERTS_DAILY_POLL_S`) | 24 min |
| escalation tick | 1 min (`ALERTS_TICK_S`) | 1 s |

The scale only changes how often the jobs wake up. *What time it is* comes from the clock (`ALERTS_CLOCK`):
with `mock`, every evaluation asks the mock carrier, so a 20-minute window closes when the mock clock has
moved 20 minutes — whether a script advanced it in one jump or the showcase stepped it a minute per second.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from alerts import escalation, hooks, internal_api
from alerts.context import AlertsService
from alerts.runner import build_service, poll

log = logging.getLogger("alerts.local")


class Scheduler:
    def __init__(self, svc: AlertsService) -> None:
        self.svc = svc
        s = svc.settings
        self.jobs: list[tuple[str, float, Callable[[], Awaitable[Any]]]] = [
            ("poll:transplant", s.transplant_poll_s, lambda: poll(svc, "transplant")),
            ("poll:care", s.care_poll_s, lambda: poll(svc, "care")),
            ("poll:self", s.daily_poll_s, lambda: poll(svc, "self")),
            ("tick", s.tick_s, self._tick),
        ]
        self._tasks: list[asyncio.Task[None]] = []

    async def _tick(self) -> Any:
        return await escalation.tick(self.svc, await self.svc.clock.now())

    def interval(self, simulated_s: float) -> float:
        return simulated_s / self.svc.settings.clock_scale

    async def _loop(self, name: str, every: float, job: Callable[[], Awaitable[Any]]) -> None:
        while True:
            await asyncio.sleep(every)
            try:
                result = await job()
                log.debug("job %s → %s", name, result)
            except Exception:  # noqa: BLE001 - a failed poll must not stop the scheduler (06 §8)
                log.exception("job %s failed", name)

    def start(self) -> None:
        for name, simulated, job in self.jobs:
            self._tasks.append(
                asyncio.create_task(self._loop(name, self.interval(simulated), job), name=name)
            )
        log.info(
            "scheduler started (scale %.3g): %s",
            self.svc.settings.clock_scale,
            ", ".join(f"{n} every {self.interval(s):.3g}s" for n, s, _ in self.jobs),
        )

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await t
        self._tasks.clear()


def create_app(svc: AlertsService, *, scheduler: bool = False) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        sched = Scheduler(svc) if scheduler else None
        if sched:
            sched.start()
        try:
            yield
        finally:
            if sched:
                await sched.stop()

    app = FastAPI(title="Ask the Tower — Alerts", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.include_router(hooks.router(svc))
    app.include_router(internal_api.router(svc))

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {"ok": True, "mode": svc.settings.mode}

    app.state.alerts = svc
    return app


def main() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    svc = build_service()
    # k8s: the same app without the in-process scheduler — CronJobs run `python -m alerts.job` (10 §1, §3)
    scheduler = svc.settings.mode == "local"
    uvicorn.run(create_app(svc, scheduler=scheduler), host="0.0.0.0", port=svc.settings.port)  # noqa: S104


if __name__ == "__main__":
    main()
