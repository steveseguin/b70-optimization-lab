#!/bin/sh
# freeagent, unmodified; its trajectory/usage/timing go to /logs/agent/freeagent/agent/.
exec env PATH="/opt/agentbench/shim:$PATH" python3 -I /opt/agent/freeagent.py --api-base "$AB_PROXY_URL" \
  --model "$AB_MODEL" --container local --instruction "$1" --out /logs/agent/freeagent \
  --max-steps 900 --time-limit "$AB_TIME_LIMIT"
