#!/bin/sh
# Qwen Code, headless: one prompt, every tool call approved (yolo), events as JSON lines. The settings template gets
# the proxy URL and model name; see README.md for what each setting turns off.
set -e
mkdir -p "$HOME/.qwen"
sed -e "s|@URL@|$AB_PROXY_URL|g" -e "s|@MODEL@|$AB_MODEL|g" /opt/agentbench/qwen-settings.json > "$HOME/.qwen/settings.json"
exec node /opt/agent/node_modules/@qwen-code/qwen-code/cli-entry.js --yolo --output-format stream-json \
  --session-id "$(cat /proc/sys/kernel/random/uuid)" "$(cat "$1")" < /dev/null > /logs/agent/qwen-events.jsonl
