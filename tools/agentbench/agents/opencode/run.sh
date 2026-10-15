#!/bin/sh
# OpenCode, headless: `opencode run` with every permission granted; the prompt goes in on stdin (a positional prompt
# is re-quoted); JSON events to /logs/agent/opencode-events.jsonl. Config: $HOME/.config/opencode/opencode.json.
set -e
mkdir -p "$HOME/.config/opencode"
sed -e "s|@URL@|$AB_PROXY_URL|g" -e "s|@MODEL@|$AB_MODEL|g" /opt/agentbench/opencode.json > "$HOME/.config/opencode/opencode.json"
exec /opt/agent/opencode run --format json --thinking --dangerously-skip-permissions --model "ctxkeeper/$AB_MODEL" \
  --agent build --title agentbench-run < "$1" > /logs/agent/opencode-events.jsonl
