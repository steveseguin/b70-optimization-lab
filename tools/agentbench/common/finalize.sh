#!/bin/sh
# finalize.sh: the last step of every agent image (runs as root at build time). The agent runs as the unprivileged
# user `agent` (uid 10001); it owns only what the task needs it to change: /app (the library), /opt/repair (where
# `next` keeps its position and log) and /logs/agent.
set -e
useradd -m -u 10001 -s /bin/bash agent
mkdir -p /logs/agent /opt/agentbench/task
chown -R agent:agent /app /opt/repair /logs/agent
chmod -R a+rX /opt/agentbench
