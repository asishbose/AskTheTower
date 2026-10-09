"""The demo's HTTP controls (mock admin + binding-page grant admin) and the CLI's failure paths, without a stack."""

from __future__ import annotations

import json

import httpx
import pytest
from ref_client import run
from ref_client.demo import BindingAdminGrants, DemoError

pytestmark = pytest.mark.unit


async def test_grant_admin_contract() -> None:
    seen: list[dict[str, object]] = []

    def ok(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/_admin/grants"
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True})

    g = BindingAdminGrants("http://bind.test/", transport=httpx.MockTransport(ok))
    await g.set_mom_grant("revoke")
    await g.aclose()
    assert seen == [
        {
            "owner_user_id": "user-mom",
            "grantee_user_id": "user-asish",
            "grant": "watch",
            "alias": "mom",
            "action": "revoke",
        }
    ]


async def test_missing_grant_admin_is_a_clear_error() -> None:
    g = BindingAdminGrants("http://bind.test", transport=httpx.MockTransport(lambda _r: httpx.Response(404)))
    with pytest.raises(DemoError, match="BIND_ADMIN=1"):
        await g.set_mom_grant("grant")
    await g.aclose()


def test_demo_with_no_stack_exits_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("MOCK_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("TOWER_URL", "http://127.0.0.1:9/mcp")
    assert run.main(["demo", "--agent", "scripted", "--no-write"]) == run.EXIT_TOWER
    assert "demo control call failed: ConnectError" in capsys.readouterr().err
