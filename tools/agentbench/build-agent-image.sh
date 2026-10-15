#!/usr/bin/env bash
# build-agent-image.sh AGENT TASK_DIR: build agentbench-task:TASK (the task's own environment, as the freeagent runner
# builds it) and agentbench-AGENT:TASK = that image + the pinned agent + the agentbench entry files.
# Builds need the network (package registries); runs never do. The build context is tools/ (4 MB), so an agent
# Dockerfile can copy agentbench/common/* and, for the control arm, freeagent/freeagent.py.
set -euo pipefail
AGENT=${1:?usage: build-agent-image.sh AGENT TASK_DIR}
TASK=$(cd "${2:?}" && pwd)
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TNAME=$(basename "$TASK")
TASK_IMG="agentbench-task:$TNAME"
docker image inspect "$TASK_IMG" >/dev/null 2>&1 || docker build -q -t "$TASK_IMG" "$TASK/environment" >/dev/null
docker build ${QUIET:+-q} -t "agentbench-$AGENT:$TNAME" --build-arg TASK_IMAGE="$TASK_IMG" \
  -f "$HERE/agents/$AGENT/Dockerfile" "$HERE/.."
