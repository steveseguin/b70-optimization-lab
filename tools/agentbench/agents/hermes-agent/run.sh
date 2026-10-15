#!/bin/sh
# Hermes Agent, headless one-shot: `hermes chat --oneshot` (the product's own finite-run path: it starts the
# profile's local gateway inside this container and runs the turn there), every approval granted (--yolo +
# approvals.mode off), events as JSON lines. The config template gets the proxy URL and model name; see config.yaml
# for what each setting turns off. Toolsets: shell, files, todo, execute_code, read-only skills (no web, browser,
# memory, session search, delegation, cron, kanban, clarify, vision/image/tts, computer use, connectors).
set -e
H="$HOME/.hermes"
mkdir -p "$H"
sed -e "s|@URL@|$AB_PROXY_URL|g" -e "s|@MODEL@|$AB_MODEL|g" /opt/agentbench/hermes-config.yaml > "$H/config.yaml"
exec /opt/agent/bin/python -P -m hermes_cli.main chat --oneshot --yolo --query-file "$1" --format stream-json \
  --toolsets terminal,file,todo,code_execution,skills < /dev/null > /logs/agent/hermes-events.jsonl
