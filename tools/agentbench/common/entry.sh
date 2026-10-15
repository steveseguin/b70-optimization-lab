#!/bin/sh
# entry.sh: runs inside the agent container as the unprivileged user `agent` (POSIX sh on purpose: the task image
# sets BASH_ENV to a file with `ulimit -v 163840`, which bash would apply to the agent program itself; the agent's
# own bash commands still get it, as freeagent's commands do).
#   1. start the in-container end of the bridge: 127.0.0.1:$AB_PORT -> /run/agentbench/proxy.sock (-> the proxy)
#   2. run the agent's run.sh with the task prompt, under the time limit
#   3. write /logs/agent/exit.json
set -u
mkdir -p /logs/agent
python3 -I /opt/agentbench/bridge.py --listen "tcp:127.0.0.1:$AB_PORT" --connect unix:/run/agentbench/proxy.sock \
  >/logs/agent/bridge.log 2>&1 &
i=0
until python3 -I -c "import socket,sys; socket.create_connection(('127.0.0.1', int(sys.argv[1])), 1)" "$AB_PORT" 2>/dev/null; do
  i=$((i + 1)); [ $i -gt 100 ] && { echo "entry: bridge did not come up" >&2; exit 97; }
  sleep 0.1
done
start=$(date +%s)
cd /app
timeout -k 30 "$AB_TIME_LIMIT" /opt/agentbench/run.sh /opt/agentbench/task/instruction.md
rc=$?
end=$(date +%s)
to=false; [ "$rc" = 124 ] || [ "$rc" = 137 ] && to=true
printf '{"exit_code": %s, "seconds": %s, "timed_out": %s}\n' "$rc" "$((end - start))" "$to" > /logs/agent/exit.json
exit $rc
