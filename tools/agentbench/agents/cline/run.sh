#!/bin/sh
# Cline CLI, headless: --yolo (tools read_files, run_commands, editor, submit_and_exit; every call approved),
# --compaction off, provider openai-compatible (Chat Completions), NDJSON events. Settings live in $CLINE_DATA_DIR.
set -e
mkdir -p "$CLINE_DATA_DIR/settings"
sed -e "s|@URL@|$AB_PROXY_URL|g" -e "s|@MODEL@|$AB_MODEL|g" /opt/agentbench/providers.json > "$CLINE_DATA_DIR/settings/providers.json"
cp /opt/agentbench/global-settings.json "$CLINE_DATA_DIR/settings/global-settings.json"
exec /opt/agent/cline --yolo --json --compaction off -P openai-compatible -m "$AB_MODEL" --data-dir "$CLINE_DATA_DIR" \
  -c /app "$(cat "$1")" < /dev/null > /logs/agent/cline-events.ndjson
