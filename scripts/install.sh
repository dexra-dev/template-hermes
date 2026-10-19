#!/usr/bin/env bash
# Installs the skill into Hermes and prints the MCP config to add. It never edits config.yaml.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SKILL="solana-trading-with-dexra"
DEST="$HERMES_HOME/skills/trading/$SKILL"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

echo "Installing Python dependencies in $ROOT"
uv sync --project "$ROOT" --quiet

if [ -e "$DEST" ] && ! diff -rq "$ROOT/skills/$SKILL" "$DEST" >/dev/null 2>&1; then
  # A backup inside skills/ would load as a second copy of the skill, so it goes next to it.
  BACKUP="$HERMES_HOME/skill-backups/$SKILL.$(date +%Y%m%d%H%M%S)"
  mkdir -p "$(dirname "$BACKUP")"
  mv "$DEST" "$BACKUP"
  echo "Your changed copy of the skill was moved to $BACKUP"
fi
mkdir -p "$DEST"
cp -R "$ROOT/skills/$SKILL/." "$DEST/"
echo "Skill installed: $DEST"

CONFIG="$HERMES_HOME/config.yaml"
echo
echo "Next, add this under mcp_servers in $CONFIG (merge with any servers already there):"
echo "--------------------------------------------------------------------------------"
sed "s#/path/to/template-hermes#$ROOT#g" "$ROOT/hermes/config.example.yaml"
echo "--------------------------------------------------------------------------------"
if [ -f "$CONFIG" ] && grep -q "dexra_trader:" "$CONFIG"; then
  echo "Note: $CONFIG already has a dexra_trader entry. Compare it with the one above."
fi
echo
echo "Put DEXRA_API_KEY (and, for live trading only, JUPITER_API_KEY and SOLANA_PRIVATE_KEY)"
echo "in $HERMES_HOME/.env. Then check the server and reload it in a running session:"
echo "  hermes mcp test dexra_trader"
echo "  /reload-mcp"
