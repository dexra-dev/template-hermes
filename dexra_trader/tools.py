"""The five trading tools as plain functions on top of dexra_core. The MCP server only wraps them."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Any, Literal

from dexra_core.config import SOL_MINT, Config, load_config
from dexra_core.guard import dexra_for
from dexra_core.trade import _result
from dexra_core.trade import buy as core_buy
from dexra_core.trade import sell as core_sell

# MCP hosts such as Hermes leave "${VAR}" in place when VAR is unset; read that as unset,
# so a missing DRY_RUN falls back to the safe default instead of failing to parse.
_PLACEHOLDER = re.compile(r"^\$\{[^}]*\}$")


def settings(env: Mapping[str, str] | None = None) -> Config:
    """Loads the core config from the environment, ignoring unresolved ${VAR} placeholders."""
    env = os.environ if env is None else env
    return load_config({k: v for k, v in env.items() if not _PLACEHOLDER.match(v.strip())})


def _call(fn_name: str, *args: Any, config: Config | None = None, **kwargs: Any) -> dict[str, Any]:
    config = config or settings()
    client = dexra_for(config)
    try:
        return getattr(client, fn_name)(*args, **kwargs) or {}
    finally:
        client.close()


def check_token(mint: str, config: Config | None = None) -> dict[str, Any]:
    """Dexra token_deep_check: holder graph, authorities, Token-2022 extensions, verdict and reasons."""
    return _call("token_deep_check", mint, config=config)


def preflight(mint: str, side: Literal["buy", "sell"], amount: float, config: Config | None = None) -> dict[str, Any]:
    """Dexra swap_preflight: price impact, sandwich risk and token risks for this exact swap."""
    return _call("swap_preflight", mint, side, amount, config=config)


def fresh_launches(
    minutes: int | None = None,
    limit: int | None = None,
    min_liquidity_usd: float | None = None,
    platforms: str | None = None,
    config: Config | None = None,
) -> dict[str, Any]:
    """Dexra new_launches: recent launches, each with its own verdict."""
    return _call(
        "new_launches",
        minutes=minutes,
        limit=limit,
        min_liquidity_usd=min_liquidity_usd,
        platforms=platforms,
        config=config,
    )


def _config_error(side: Literal["buy", "sell"], mint: str, error: Exception) -> dict[str, Any]:
    # Same shape the core returns for its own errors.
    input_mint, output_mint = (SOL_MINT, mint) if side == "buy" else (mint, SOL_MINT)
    out = _result(side, mint, input_mint, output_mint, 0, None, None, "dry_run")
    out["message"] = f"{side} not sent: {error}"
    return out


def buy(mint: str, amount_sol: float, config: Config | None = None) -> dict[str, Any]:
    """Guarded buy through the core. Never raises; blocked or dry-run results come back as data."""
    try:
        config = config or settings()
    except Exception as error:  # agents get a result, never a traceback
        return _config_error("buy", mint, error)
    return core_buy(mint, amount_sol, config)


def sell(mint: str, amount_atomic: int | str, config: Config | None = None) -> dict[str, Any]:
    """Sell through the core. A verdict never blocks an exit; the preflight is reported."""
    try:
        config = config or settings()
    except Exception as error:
        return _config_error("sell", mint, error)
    return core_sell(mint, amount_atomic, config)
