import json
import os
import sys

import httpx
import pytest
from mcp import Client, StdioServerParameters

from conftest import BONK, DEXRA, dexra_result
from dexra_trader.server import server

TOOLS = {"check_token", "preflight", "fresh_launches", "buy", "sell"}
SETTINGS = (
    "DEXRA_API_KEY",
    "JUPITER_API_KEY",
    "SOLANA_PRIVATE_KEY",
    "DRY_RUN",
    "MAX_TRADE_SOL",
    "SLIPPAGE_BPS",
    "ALLOW_CAUTION",
)


@pytest.fixture(autouse=True)
def env(monkeypatch):
    for name in SETTINGS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DEXRA_BASE_URL", DEXRA)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_lists_the_five_tools():
    async with Client(server) as client:
        listed = {t.name: t for t in (await client.list_tools()).tools}
    assert set(listed) == TOOLS
    assert listed["buy"].annotations.destructive_hint and listed["check_token"].annotations.read_only_hint
    assert listed["preflight"].input_schema["required"] == ["mint", "side", "amount"]


@pytest.mark.anyio
async def test_check_token_over_mcp(mock):
    mock.get(f"{DEXRA}/token_deep_check").mock(
        return_value=httpx.Response(200, json=dexra_result("ok", ["no linked holders"]))
    )
    async with Client(server) as client:
        result = await client.call_tool("check_token", {"mint": BONK})
    assert not result.is_error
    assert result.structured_content["verdict"] == "ok"


@pytest.mark.anyio
async def test_dexra_failure_is_a_tool_error(mock):
    mock.get(f"{DEXRA}/token_deep_check").mock(
        return_value=httpx.Response(402, json={"error": "payment_required", "context": "add an API key"})
    )
    async with Client(server) as client:
        result = await client.call_tool("check_token", {"mint": BONK})
    assert result.is_error and "payment_required (HTTP 402)" in result.content[0].text


@pytest.mark.anyio
async def test_buy_over_cap_is_blocked_before_any_request(mock):
    async with Client(server) as client:
        result = await client.call_tool("buy", {"mint": BONK, "amount_sol": 1})
    body = result.structured_content
    assert (body["status"], body["mode"]) == ("blocked", "dry_run")
    assert "MAX_TRADE_SOL" in body["message"]
    assert len(mock.calls) == 0


@pytest.mark.anyio
async def test_buy_dry_run_over_mcp(mock):
    mock.get(f"{DEXRA}/token_deep_check").mock(return_value=httpx.Response(200, json=dexra_result("ok")))
    mock.get(f"{DEXRA}/swap_preflight").mock(return_value=httpx.Response(200, json=dexra_result("ok")))
    async with Client(server) as client:
        result = await client.call_tool("buy", {"mint": BONK, "amount_sol": 0.01})
    body = json.loads(result.content[0].text)
    assert (body["status"], body["signature"]) == ("dry_run", None)


@pytest.mark.anyio
async def test_stdio_server_starts_and_lists_tools():
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "dexra_trader"],
        env={"PATH": os.environ.get("PATH", ""), "DRY_RUN": "${DRY_RUN}"},
    )
    async with Client(params) as client:
        names = {t.name for t in (await client.list_tools()).tools}
        result = await client.call_tool("buy", {"mint": "not-a-mint", "amount_sol": 0.01})
    assert names == TOOLS
    assert result.structured_content["status"] == "blocked"
