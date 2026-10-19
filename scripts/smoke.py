"""Starts dexra-trader over stdio like an MCP host would and calls each read tool, then a dry-run buy.

DRY_RUN is forced to true whatever the environment says. Usage: uv run python scripts/smoke.py [mint] [sol]
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

from mcp import Client, StdioServerParameters

BONK = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"


def show(name: str, result, full: bool = False) -> None:
    text = result.content[0].text if result.content else ""
    if result.is_error:
        print(f"== {name}: error\n{text}\n")
        return
    body = json.loads(text)
    if not full:
        body = {k: body.get(k) for k in ("verdict", "summary", "reasons", "count") if k in body}
    print(f"== {name}\n{json.dumps(body, indent=2)}\n")


async def main() -> None:
    mint = sys.argv[1] if len(sys.argv) > 1 else BONK
    sol = float(sys.argv[2]) if len(sys.argv) > 2 else 0.01
    env = {**os.environ, "DRY_RUN": "true"}
    params = StdioServerParameters(command=sys.executable, args=["-m", "dexra_trader"], env=env)
    print(f"Dexra: {env.get('DEXRA_BASE_URL', 'https://api.dexra.dev')}")
    async with Client(params) as client:
        print("tools:", ", ".join(t.name for t in (await client.list_tools()).tools), "\n")
        show("check_token", await client.call_tool("check_token", {"mint": mint}))
        show("preflight", await client.call_tool("preflight", {"mint": mint, "side": "buy", "amount": sol}))
        show("fresh_launches", await client.call_tool("fresh_launches", {"minutes": 15, "limit": 3}))
        result = await client.call_tool("buy", {"mint": mint, "amount_sol": sol})
        show("buy", result, full=True)
        body = result.structured_content or {}
        if body.get("mode") != "dry_run" or body.get("signature") is not None:
            sys.exit("smoke: expected a dry run with no signature")


if __name__ == "__main__":
    asyncio.run(main())
