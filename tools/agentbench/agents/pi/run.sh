#!/bin/sh
# pi, headless: one prompt, JSON event stream (pi never asks for approval). Config templates get the proxy URL and
# model name. --no-extensions drops the built-in MCP, llama.cpp, codemode and tool-search extensions (none is used;
# the default tools read, bash, edit, write stay). Sessions go to ~/.pi/agent/sessions (copied out after the run).
set -e
mkdir -p "$HOME/.pi/agent"
for f in models.json settings.json; do
  sed -e "s|@URL@|$AB_PROXY_URL|g" -e "s|@MODEL@|$AB_MODEL|g" "/opt/agentbench/pi/$f" > "$HOME/.pi/agent/$f"
done
exec node /opt/agent/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js --mode json --offline \
  --no-extensions --provider agentbench --model "$AB_MODEL" -- "$(cat "$1")" < /dev/null > /logs/agent/pi-events.jsonl
