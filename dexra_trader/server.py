"""dexra-trader: a stdio MCP server with Dexra checks and guarded Solana trades. Works with any MCP client."""

from __future__ import annotations

import logging
from typing import Annotated, Any, Literal

import anyio.to_thread
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import Field

from . import tools

Mint = Annotated[str, Field(description="Solana token mint address (base58)")]

INSTRUCTIONS = """\
Dexra checks Solana tokens and guards every buy.
Before buying, call check_token and preflight and tell the user the verdicts and reasons in plain words.
buy runs the same checks again and refuses unless both verdicts pass. A blocked buy is final:
do not retry with a smaller amount, a different tool or split orders to get around it.
Every result has a mode; when it is dry_run, say that nothing was sent.
A Dexra ok means launches like it survived more often in Dexra's published report, not that the price will go up.
"""

server = MCPServer(name="dexra-trader", instructions=INSTRUCTIONS, version="0.1.0")

READ_ONLY = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=True)
TRADE = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=True)


async def _read(fn: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        return await anyio.to_thread.run_sync(lambda: fn(*args, **kwargs))
    except Exception as error:  # the message is what the model needs
        raise ToolError(str(error)) from error


@server.tool(title="Check a token", annotations=READ_ONLY)
async def check_token(mint: Mint) -> dict[str, Any]:
    """Dexra token_deep_check: who really holds the token, linked wallets, authorities and
    Token-2022 extensions. Returns a verdict (ok, caution, avoid, unknown) with reasons."""
    return await _read(tools.check_token, mint)


@server.tool(title="Preflight a swap", annotations=READ_ONLY)
async def preflight(
    mint: Mint,
    side: Annotated[Literal["buy", "sell"], Field(description="buy spends SOL, sell sells the token")],
    amount: Annotated[float, Field(gt=0, description="SOL for a buy, token units for a sell")],
) -> dict[str, Any]:
    """Dexra swap_preflight for this exact swap: price impact, sandwich risk, transfer fees,
    hooks, mint and freeze authority. Returns a verdict with reasons."""
    return await _read(tools.preflight, mint, side, amount)


@server.tool(title="Fresh launches", annotations=READ_ONLY)
async def fresh_launches(
    minutes: Annotated[int, Field(ge=1, le=1440, description="Look-back window")] = 15,
    limit: Annotated[int, Field(ge=1, le=20)] = 10,
    min_liquidity_usd: Annotated[float | None, Field(ge=0)] = None,
    platforms: Annotated[
        str | None,
        Field(description="Comma separated, e.g. pump_fun,letsbonk,raydium_launchlab,meteora_dbc,pump_swap"),
    ] = None,
) -> dict[str, Any]:
    """Dexra new_launches: tokens launched on Solana in the last N minutes, each with its own
    verdict and reasons. Windows over 60 minutes cost more."""
    return await _read(
        tools.fresh_launches,
        minutes=minutes,
        limit=limit,
        min_liquidity_usd=min_liquidity_usd,
        platforms=platforms,
    )


@server.tool(title="Buy (guarded)", annotations=TRADE)
async def buy(
    mint: Mint,
    amount_sol: Annotated[float, Field(gt=0, description="SOL to spend, at most MAX_TRADE_SOL")],
) -> dict[str, Any]:
    """Buys the token with SOL through Jupiter, only if Dexra's token check and preflight both
    pass. Dry run unless the operator enabled live trading. status is blocked, dry_run,
    executed, failed or error; decision.reasons says why."""
    return await anyio.to_thread.run_sync(tools.buy, mint, amount_sol)


@server.tool(title="Sell", annotations=TRADE)
async def sell(
    mint: Mint,
    amount_atomic: Annotated[
        int | str, Field(description="Token amount in smallest units; a string keeps large values exact")
    ],
) -> dict[str, Any]:
    """Sells the token for SOL through Jupiter. Never blocked by a verdict, so a position can
    always be exited; the preflight verdict is reported. Dry run unless live trading is on."""
    return await anyio.to_thread.run_sync(tools.sell, mint, amount_atomic)


def main() -> None:
    """Runs the server over stdio."""
    # Request lines would flood the host's MCP log on every check.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    server.run("stdio")


if __name__ == "__main__":
    main()
