"""Tower over MCP Streamable HTTP, exactly as Alexa+ would reach it: discover the tools, call them, get the
`ToolResult` envelope back as a dict.

Auth: `Authorization: Bearer $TOWER_BEARER`; in local mode also `X-Tower-User: <user_id>` (Tower's local
identity, 01 §4). On AWS the bearer is the JWT and the header is ignored by Tower.

This module knows nothing about policy, consent or carriers. It holds no carrier credentials and no store.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any

DEFAULT_TOWER_URL = "http://localhost:8080/mcp"  # mk/vars.mk TOWER_URL for ENV=local


class TowerError(RuntimeError):
    """Tower refused the request outright (401, unknown tool, internal error) or could not be reached.
    A policy refusal is *not* an error: it is a normal `ToolResult` with a refusal reason code."""


@dataclass(frozen=True)
class ToolSpec:
    """One tool as Tower advertises it: the description is the voice UX (01 §2)."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TowerConfig:
    url: str = DEFAULT_TOWER_URL
    bearer: str | None = None
    user_id: str | None = None
    timeout_s: float = 10.0

    @classmethod
    def from_env(cls, *, user_id: str | None = None) -> TowerConfig:
        return cls(
            url=os.environ.get("TOWER_URL") or DEFAULT_TOWER_URL,
            bearer=os.environ.get("TOWER_BEARER") or None,
            user_id=user_id,
            timeout_s=float(os.environ.get("TOWER_TIMEOUT_S", "10")),
        )

    def headers(self) -> dict[str, str]:
        h: dict[str, str] = {}
        if self.bearer:
            h["Authorization"] = f"Bearer {self.bearer}"
        if self.user_id:
            h["X-Tower-User"] = self.user_id
        return h


def user_id_for(name: str) -> str:
    """`--user asish` → `user-asish` (the demo seed's ids); a full id passes through."""
    return name if name.startswith("user-") or ":" in name else f"user-{name}"


class TowerClient:
    """`async with TowerClient(cfg) as tower: await tower.tools(); await tower.call("line_is_ok", {...})`.

    `httpx_client_factory` is the test seam: tests hand in a factory that talks to Tower's ASGI app in-process.
    """

    def __init__(self, config: TowerConfig, *, httpx_client_factory: Callable[..., Any] | None = None):
        self.config = config
        self._factory = httpx_client_factory
        self._client: Any = None
        self._tools: list[ToolSpec] | None = None

    async def __aenter__(self) -> TowerClient:
        from fastmcp import Client
        from fastmcp.client.transports import StreamableHttpTransport

        transport = StreamableHttpTransport(
            self.config.url, headers=self.config.headers(), httpx_client_factory=self._factory
        )
        self._client = Client(transport, timeout=self.config.timeout_s)
        try:
            await self._client.__aenter__()
        except Exception as e:  # noqa: BLE001 - one clear error for "cannot reach Tower"
            self._client = None
            raise TowerError(f"cannot connect to Tower at {self.config.url}: {type(e).__name__}") from None
        return self

    async def __aexit__(
        self, et: type[BaseException] | None, e: BaseException | None, tb: TracebackType | None
    ) -> None:
        if self._client is not None:
            await self._client.__aexit__(et, e, tb)
            self._client = None

    async def tools(self) -> list[ToolSpec]:
        """Discovered at connect, cached for the session. Nothing is hard-coded here."""
        if self._tools is None:
            try:
                listed = await self._client.list_tools()
            except Exception as e:  # noqa: BLE001
                raise TowerError(f"tools/list failed: {type(e).__name__}") from None
            self._tools = [ToolSpec(t.name, t.description or "", dict(t.inputSchema or {})) for t in listed]
        return self._tools

    async def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call one tool; returns the `ToolResult` wire dict (summary, facts, reason_codes, next_step, ...)."""
        from fastmcp.exceptions import ToolError

        try:
            res = await self._client.call_tool(name, arguments)
        except ToolError as e:
            raise TowerError(f"{name}: {e}") from None
        except Exception as e:  # noqa: BLE001
            raise TowerError(f"{name}: {type(e).__name__}") from None
        data = res.structured_content
        if not isinstance(data, dict):
            text = res.content[0].text if res.content else "{}"
            data = json.loads(text)
        if "summary" not in data or "reason_codes" not in data:
            raise TowerError(f"{name}: result is not a ToolResult envelope")
        return dict(data)
