---
name: solana-trading-with-dexra
description: "Guarded Solana trades: Dexra checks, then buy or sell."
version: 0.1.0
author: Dexra
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Solana, Trading, Crypto, Risk, Dexra, Jupiter, MCP]
    homepage: https://dexra.dev/docs/templates?utm_source=github&utm_medium=referral&utm_campaign=templates&utm_content=template-hermes
---

# Solana trading with Dexra

Check a Solana token with Dexra, then buy or sell it through the `dexra_trader` MCP server. Every buy
is checked again inside the server and refused unless Dexra allows it. It is a dry run unless the
operator turned live trading on.

## When to use

- The user asks whether a Solana token is safe, risky or worth a look.
- The user asks to buy or sell a Solana token, or to find fresh launches.
- The user pastes a mint address and asks what you think.

## Tools

These come from the `dexra_trader` MCP server. In Hermes they are registered as
`mcp__dexra_trader__<tool>` (for example `mcp__dexra_trader__buy`).

| Tool | Use it for |
| - | - |
| `check_token(mint)` | Holder graph, linked wallets, authorities, Token-2022 extensions. Verdict and reasons. |
| `preflight(mint, side, amount)` | This exact swap: price impact, sandwich risk, transfer fees. `amount` is SOL for a buy, token units for a sell. |
| `fresh_launches(minutes, limit, min_liquidity_usd, platforms)` | Tokens launched in the last N minutes, each with its own verdict. |
| `buy(mint, amount_sol)` | Guarded buy. Runs both checks again and refuses unless both pass. |
| `sell(mint, amount_atomic)` | Sell in the token's smallest units. Never blocked by a verdict, so a position can always be exited. |

If the remote `dexra` server is connected too, its tools (`mcp__dexra__wallet_check`,
`mcp__dexra__pool_health` and others) answer research questions. They never trade.

## Procedure

1. **Check.** Call `check_token` for the mint.
2. **Preflight.** Call `preflight` with `side: buy` and the amount in SOL the user wants.
3. **Report.** Tell the user both verdicts and the reasons in plain words, before any buy. Quote the
   `summary` lines. Say what the verdict means: `ok` means launches like it survived more often in
   Dexra's published report, not that the price will go up. `caution` and `avoid` explain the risk.
   `unknown` means data is missing.
4. **Buy only when the guard allows.** Call `buy` only if the user asked for it and both verdicts
   passed. `buy` decides for itself; your own read of the verdicts never overrides it.
5. **Read the result.** Look at `status`:
   - `blocked`: the guard said no. Give the first reasons from `decision.reasons`. Stop.
   - `dry_run`: say clearly that nothing was sent and the trade only would have happened. Mention the
     quote if there is one.
   - `executed`: give the `signature` and `explorerUrl`.
   - `failed` or `error`: give the `message`. Do not retry on your own.
6. **Sell** with `sell`. Ask for the amount in the token's smallest units if the user gives a
   human amount and you don't know the decimals (`check_token` or `preflight` results include them).

## Rules

- Check before every buy. Never call `buy` first to "see what happens".
- A blocked buy is final. Never retry it with a smaller amount, split it into several buys, switch to
  another tool or server, or ask the user to change settings to get it through. You may explain which
  setting exists (`ALLOW_CAUTION`, `MAX_TRADE_SOL`) if the user asks, and leave the choice to them.
- Never ask for, print or store a private key. Keys live in the environment of the MCP server only.
- When `mode` is `dry_run`, remind the user it is a dry run.
- Don't promise returns. This is not financial advice.

## Pitfalls

- `402` or `payment_required` in a result means no Dexra API key is set. Every buy is blocked until
  one is. Keys: https://dexra.dev/app/keys?utm_source=github&utm_medium=referral&utm_campaign=templates&utm_content=template-hermes
- `amount ... is above MAX_TRADE_SOL` means the buy is over the per-trade cap. The cap is not a hint
  to split the order.
- `fresh_launches` can be empty. Say so; don't invent launches.

## Verification

`/reload-mcp`, then ask "check DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263 and buy 0.01 SOL". You
should see both verdicts reported first, then a `blocked` or `dry_run` result, never a signature
while `DRY_RUN` is on.
