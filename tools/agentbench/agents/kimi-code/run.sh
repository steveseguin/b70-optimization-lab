#!/bin/sh
# Kimi Code, headless: `kimi -p` runs one prompt in print mode, which always uses the "auto" permission mode
# (never asks) and has no step cap; --output-format stream-json writes the event stream. The config template
# gets the proxy URL and model name. Sessions go to ~/.kimi-code/sessions (copied out after the run).
set -e
mkdir -p "$HOME/.kimi-code"
sed -e "s|@URL@|$AB_PROXY_URL|g" -e "s|@MODEL@|$AB_MODEL|g" /opt/agentbench/kimi/config.toml > "$HOME/.kimi-code/config.toml"
cp /opt/agentbench/kimi/tui.toml "$HOME/.kimi-code/tui.toml"
exec node /opt/agent/node_modules/@moonshot-ai/kimi-code/dist/main.mjs --model agentbench --output-format stream-json \
  --prompt="$(cat "$1")" < /dev/null > /logs/agent/kimi-events.jsonl
