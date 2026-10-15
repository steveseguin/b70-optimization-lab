#!/bin/sh
# Open Interpreter, headless: `interpreter exec` runs one task and exits when the model ends its turn; every command
# runs without asking and outside its own sandbox (--dangerously-bypass-approvals-and-sandbox: the container is the
# sandbox); events as JSON lines. The prompt is read from stdin (`-`), so it reaches the model byte for byte. The
# config template and the model catalog get the proxy URL and model name (see config.toml).
set -e
H="$HOME/.openinterpreter"
mkdir -p "$H"
sed -e "s|@URL@|$AB_PROXY_URL|g" -e "s|@MODEL@|$AB_MODEL|g" /opt/agentbench/oi-config.toml > "$H/config.toml"
sed -e "s|@MODEL@|$AB_MODEL|g" /opt/agentbench/oi-model-catalog.json > "$H/model-catalog.json"
exec env AGENTBENCH_API_KEY=sk-agentbench-dummy /opt/agent/bin/interpreter exec \
  --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check --json -C /app - \
  < "$1" > /logs/agent/interpreter-events.jsonl
