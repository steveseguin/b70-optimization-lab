#!/bin/sh
# Goose, headless: `goose run` with only the built-in developer extension (shell, write, edit, tree, read_image), no
# profile extensions, events as JSON lines. Provider: a declarative custom provider (engine openai = Chat Completions,
# streaming off). Everything else is set by environment (see the Dockerfile and README.md).
set -e
mkdir -p "$GOOSE_PATH_ROOT/config/custom_providers"
sed -e "s|@URL@|$AB_PROXY_URL|g" -e "s|@MODEL@|$AB_MODEL|g" /opt/agentbench/custom_provider.json \
  > "$GOOSE_PATH_ROOT/config/custom_providers/custom_ctxkeeper.json"
export GOOSE_MODEL="$AB_MODEL"
exec /opt/agent/goose run --name agentbench-run --no-profile --with-builtin developer --max-turns 100000 \
  --output-format stream-json -i "$1" < /dev/null > /logs/agent/goose-events.jsonl
