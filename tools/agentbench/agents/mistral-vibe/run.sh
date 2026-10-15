#!/bin/sh
# Mistral Vibe, programmatic mode: the prompt file as given, every tool call approved, one JSON line per message on
# stdout; export.json and a copy of the session journal go to /logs/agent/vibe-run. The config template gets the
# proxy URL and model name. --max-turns: the default limit is 1000 model calls per run.
set -e
mkdir -p "$HOME/.vibe"
sed -e "s|@URL@|$AB_PROXY_URL|g" -e "s|@MODEL@|$AB_MODEL|g" /opt/agentbench/vibe-config.toml > "$HOME/.vibe/config.toml"
export AGENTBENCH_API_KEY=sk-agentbench-dummy
exec /opt/agent/bin/vibe --prompt-file "$1" --auto-approve --trust --max-turns 100000 --output streaming \
  --output-dir /logs/agent/vibe-run < /dev/null > /logs/agent/vibe-events.jsonl
