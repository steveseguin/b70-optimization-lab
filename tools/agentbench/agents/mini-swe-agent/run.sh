#!/bin/sh
# mini-swe-agent, headless: stock mini.yaml + overrides.yaml, no confirmations, exits when the model runs
# `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`. Trajectory: /logs/agent/mini.traj.json; console log on stdout.
set -e
mkdir -p "$HOME/.config/mini-swe-agent"
sed -e "s|@URL@|$AB_PROXY_URL|g" -e "s|@MODEL@|$AB_MODEL|g" /opt/agentbench/overrides.yaml > "$HOME/.config/mini-swe-agent/overrides.yaml"
exec /opt/agent/bin/mini -c mini.yaml -c "$HOME/.config/mini-swe-agent/overrides.yaml" -t "$(cat "$1")" \
  --yolo --exit-immediately -o /logs/agent/mini.traj.json < /dev/null > /logs/agent/mini-console.txt
