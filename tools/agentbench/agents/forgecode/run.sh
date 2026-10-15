#!/bin/sh
# ForgeCode, headless: `forge -p PROMPT` runs one turn of the default `forge` agent and exits when the model stops
# calling tools. Every tool runs without asking (restricted = false is the default). The config template gets the
# proxy URL and model name (see forge.toml); forge-agent.md is the built-in `forge` agent minus the `fetch` (web)
# tool, installed as a global agent, which overrides the built-in one of the same id.
set -e
F="$HOME/.forge"
mkdir -p "$F/agents"
sed -e "s|@URL@|$AB_PROXY_URL|g" -e "s|@MODEL@|$AB_MODEL|g" /opt/agentbench/forge.toml > "$F/.forge.toml"
cp /opt/agentbench/forge-agent.md "$F/agents/forge.md"
exec env AGENTBENCH_API_KEY=sk-agentbench-dummy /opt/agent/forge --agent forge -p "$(cat "$1")" \
  < /dev/null > /logs/agent/forge-stdout.txt
