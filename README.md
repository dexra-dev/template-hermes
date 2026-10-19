# Dexra for Hermes Agent

Lets [Hermes Agent](https://hermes-agent.nousresearch.com) trade on Solana, with [Dexra](https://dexra.dev/?utm_source=github&utm_medium=referral&utm_campaign=templates&utm_content=template-hermes) checking every buy first. Before a buy, the agent gets two Dexra verdicts (`ok`, `caution`, `avoid` or `unknown`) with reasons in plain words, and the buy goes ahead only if both pass. The template has two parts. `dexra-trader` is a local stdio MCP server with five tools: `check_token`, `preflight`, `fresh_launches`, `buy` and `sell`. The `solana-trading-with-dexra` skill teaches Hermes the workflow: check, preflight, report, then buy only when the guard allows. Swaps go through Jupiter. Everything is a dry run until you switch live trading on. The MCP server isn't tied to Hermes, so any MCP client can use it.

## Safety

- **Dry run by default.** Trades are sent only when `DRY_RUN=false`, `SOLANA_PRIVATE_KEY` and `JUPITER_API_KEY` are all set. Otherwise every result has `mode: dry_run`, and the message says which setting is missing.
- **Caps.** `MAX_TRADE_SOL` (default 0.05) is a hard cap per buy. A larger buy is refused, not reduced. `SLIPPAGE_BPS` defaults to 100 and can't go above 1000.
- **What blocks a buy:**
  - an `avoid` or `unknown` verdict from either check
  - a `caution` verdict, unless `ALLOW_CAUTION=true`
  - an invalid mint or amount
  - any Dexra failure (402, 429, 5xx or a network error). The guard fails closed.
- **The guard sits in the server, not the prompt.** `buy` runs Dexra's checks itself every time it's called. So no wording, skill or other MCP server can make the agent buy past a block. Dexra's remote MCP server has no trading tools.
- **Sells are never blocked**, so a position can always be exited. The preflight verdict is still reported.
- **Keys come only from the environment.** The wallet secret is never logged or echoed. Hermes passes a stdio server only the variables listed in its `env` block, plus a short safe baseline. Use a dedicated wallet that holds little SOL. The caps limit each trade, not all trades together.

Not financial advice. A Dexra `ok` means launches like it survived more often in our published report, not that the price will go up.

## Quick start

Click **Use this template** on GitHub, or:

```bash
git clone https://github.com/dexra-dev/template-hermes
cd template-hermes
cp .env.example .env          # add DEXRA_API_KEY at least
uv sync
uv run --env-file .env python scripts/smoke.py    # dry run, no LLM: checks BONK and tries a 0.01 SOL buy
```

Then connect it to Hermes:

```bash
./scripts/install.sh
```

The script installs the Python dependencies and copies the skill to `~/.hermes/skills/trading/solana-trading-with-dexra/`. It then prints the `mcp_servers` block with this checkout's path filled in. It never edits your `config.yaml`. Paste the block into `~/.hermes/config.yaml` yourself, and put the keys in `~/.hermes/.env`:

```bash
DEXRA_API_KEY=dxr_...
# live trading only:
JUPITER_API_KEY=...
SOLANA_PRIVATE_KEY=...
```

Check the server and load it:

```bash
hermes mcp test dexra_trader      # should list 5 tools
hermes                            # then, in a session: /reload-mcp
```

Ask: *"Check DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263 and buy 0.01 SOL if it passes."* You can also call the skill directly: `/solana-trading-with-dexra`.

Get a key at [dexra.dev/app/keys](https://dexra.dev/app/keys?utm_source=github&utm_medium=referral&utm_campaign=templates&utm_content=template-hermes). The free tier gives 100 credits a day. Paid tools can also be paid per call over x402.

### The Hermes config

[`hermes/config.example.yaml`](hermes/config.example.yaml) adds two servers:

- `dexra_trader`: the local server, started with `uv run --directory <this checkout> dexra-trader`.
  - Secrets come in as `${DEXRA_API_KEY}`-style references, which Hermes fills from `~/.hermes/.env`.
  - The safety settings are written out literally in the `env` block, so you can see them there.
  - `tools.include` lists the five tools.
- `dexra` (optional): Dexra's remote MCP server at `https://api.dexra.dev/mcp` over Streamable HTTP, with `Authorization: Bearer ${DEXRA_API_KEY}`.
  - It's for research: `wallet_check`, `pool_health`, `market_snapshot` and others.
  - `tools.include` leaves out `token_deep_check`, `swap_preflight` and `new_launches`. `dexra_trader` already covers them, so the model sees one name per check.
  - Hermes won't connect this server while `DEXRA_API_KEY` is unset. Set `enabled: false` until you have a key.

Hermes registers the tools as `mcp__dexra_trader__buy`, `mcp__dexra__wallet_check` and so on. Run `/reload-mcp` after any change. To load the skill from this checkout instead of copying it, add the checkout's `skills/` directory to `skills.external_dirs`.

### Other MCP clients

`dexra-trader` is a standard stdio MCP server. In a client that uses the common `mcpServers` JSON format:

```json
{
  "mcpServers": {
    "dexra-trader": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/template-hermes", "dexra-trader"],
      "env": { "DEXRA_API_KEY": "dxr_...", "DRY_RUN": "true" }
    }
  }
}
```

The server sends short usage instructions in its MCP handshake: check first, never work around a block, say when a result is a dry run. Clients that read those instructions pass them to the model.

## Configuration

The server reads only its environment. Under Hermes, that means the `env` block of `dexra_trader`. A `${VAR}` that Hermes couldn't resolve counts as unset, so a setting you leave out falls back to its safe default.

| Variable | Default | Meaning |
| - | - | - |
| `DEXRA_API_KEY` | unset | `dxr_…` key. Without it, paid checks answer 402 and every buy is blocked. |
| `DEXRA_BASE_URL` | `https://api.dexra.dev` | Dexra API. Point it at a local API for testing. |
| `DRY_RUN` | `true` | Only `false`/`0`/`no`/`off` turn it off. |
| `JUPITER_API_KEY` | unset | Needed for live trading. In a dry run it adds a Jupiter quote. |
| `SOLANA_PRIVATE_KEY` | unset | Base58 64-byte secret key. Only for live trading. |
| `MAX_TRADE_SOL` | `0.05` | Hard cap per buy. |
| `SLIPPAGE_BPS` | `100` | Jupiter slippage, 0 to 1000. |
| `ALLOW_CAUTION` | `false` | Let a `caution` verdict pass. |

## How the guard works

`dexra_core` is the shared Dexra trading core, copied unchanged. Each tool is a thin wrapper around it:

| Tool | Core call | Notes |
| - | - | - |
| `check_token` | `token_deep_check` | Read only. Dexra errors come back as MCP tool errors. |
| `preflight` | `swap_preflight` | `amount` is SOL for a buy, token units for a sell. |
| `fresh_launches` | `new_launches` | Each launch has its own verdict. |
| `buy` | `trade.buy` | `decide_buy` first, then Jupiter, or a dry run. Never raises. |
| `sell` | `trade.sell` | Reports the preflight and never blocks. `amount_atomic` is in the token's smallest units. |

`decide_buy` checks the mint and the amount against `MAX_TRADE_SOL` before any network call. Then it runs `token_deep_check` and `swap_preflight` in parallel. The buy is allowed only if both verdicts pass. `buy` returns plain JSON whose `status` is one of these:

- `blocked`: the guard said no.
- `dry_run`: it would have traded.
- `executed`: the trade was sent and landed.
- `failed`: Jupiter couldn't build the transaction, or it didn't land.
- `error`: a problem with config, keys or the network.

The `decision` field holds both verdicts and the reasons. The full rules are in [`dexra_core/README.md`](dexra_core/README.md).

## Project layout

```
dexra_core/                 shared trading core (copied verbatim, do not edit)
dexra_trader/
  tools.py                  the five tools as plain functions on the core
  server.py                 MCP server (official mcp SDK, MCPServer, stdio)
skills/solana-trading-with-dexra/SKILL.md   Hermes skill: the workflow and its rules
hermes/config.example.yaml  mcp_servers entries for ~/.hermes/config.yaml
scripts/install.sh          copies the skill, prints the config (never edits it)
scripts/smoke.py            starts the server over stdio and runs a dry-run buy, no LLM
tests/                      core tests, tool tests and MCP client tests, HTTP mocked with respx
```

Develop:

```bash
uv sync
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run pyright
```

The `mcp` SDK is pinned to 2.3.0. In SDK 2.x the high-level server class is called `MCPServer`; in 1.x it was `FastMCP`.

## Links

- Dexra docs for templates: https://dexra.dev/docs/templates?utm_source=github&utm_medium=referral&utm_campaign=templates&utm_content=template-hermes
- API keys: https://dexra.dev/app/keys?utm_source=github&utm_medium=referral&utm_campaign=templates&utm_content=template-hermes
- How the verdicts hold up: https://dexra.dev/accuracy?utm_source=github&utm_medium=referral&utm_campaign=templates&utm_content=template-hermes
- Hermes MCP guide: https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp
- Hermes MCP config reference: https://hermes-agent.nousresearch.com/docs/reference/mcp-config-reference
- Hermes skills: https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
- Jupiter Swap API: https://developers.jup.ag/docs/swap/order-and-execute
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk

## License

MIT. See [LICENSE](LICENSE).
