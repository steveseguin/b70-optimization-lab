#!/usr/bin/env bash
# Static + behavioral tests for server-supervision.sh using harmless dummy
# process trees (sleep only; no GPU, no vLLM). Run before trusting the
# candidate runner's cleanup path.
set -uo pipefail

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
lib="$here/server-supervision.sh"
runner="$here/run-vllm-candidate.sh"

fails=0
check() {
  local name=$1 result=$2
  if [[ "$result" == "0" ]]; then
    printf 'PASS %s\n' "$name"
  else
    printf 'FAIL %s\n' "$name"
    fails=$((fails + 1))
  fi
}

# --- static -------------------------------------------------------------
bash -n "$lib" && bash -n "$runner"
check "static: bash -n library and runner" "$?"
if command -v shellcheck > /dev/null 2>&1; then
  shellcheck -x "$lib" > /dev/null
  check "static: shellcheck library" "$?"
else
  printf 'SKIP static: shellcheck not installed\n'
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# Assign tunables as ordinary shell variables; env-prefixed `source` would
# lose them again as soon as the builtin returns.
SUPP_TERM_GRACE_S=2
SUPP_KILL_GRACE_S=2
SUPP_WATCHDOG_POLL_S=1
SUPP_WATCHDOG_CONFIRM=1
SUPP_WATCHDOG_SNAPSHOT_S=1
# shellcheck source=server-supervision.sh
source "$lib"

harness_pid=""

teardown() {
  supp_stop_watchdog
  supp_stop_group > /dev/null 2>&1 || true
  if [[ -n "$harness_pid" ]]; then
    kill -KILL "$harness_pid" 2>/dev/null || true
    wait "$harness_pid" 2>/dev/null || true
    harness_pid=""
  fi
}
trap 'teardown; rm -rf "$tmp"' EXIT

# --- test 1: dedicated group, full-tree teardown -------------------------
SUPP_LOG="$tmp/t1.log"
supp_start_group /dev/null bash -c 'sleep 300 & sleep 300 & exec sleep 300'
rc=$?
check "start_group returns success" "$rc"

own_pgid=$(ps -o pgid= -p $$ | tr -d '[:space:]')
[[ -n "$SUPP_PGID" && "$SUPP_PGID" != "$own_pgid" ]]
check "group is dedicated (pgid != caller pgid)" "$?"

count=$(supp_group_procs | wc -l)
[[ "$count" == "3" ]]
check "dummy tree has all 3 members in group (got $count)" "$?"

supp_alive
check "group alive before stop" "$?"

saved_pgid=$SUPP_PGID
supp_stop_group
rc=$?
kill -0 -- "-$saved_pgid" 2>/dev/null
alive_after=$?
[[ "$rc" == "0" && "$alive_after" != "0" ]]
check "stop_group drains SIGTERM-responsive tree completely" "$?"

# --- test 2: TERM-ignoring leader escalates to SIGKILL -------------------
SUPP_LOG="$tmp/t2.log"
supp_start_group /dev/null bash -c 'trap "" TERM; sleep 300 & wait'
start=$(date +%s)
supp_stop_group
elapsed=$(( $(date +%s) - start ))
grep -q 'escalating to SIGKILL' "$tmp/t2.log"
escalated=$?
[[ "$elapsed" -lt $((SUPP_TERM_GRACE_S + SUPP_KILL_GRACE_S + 5)) ]]
bounded=$?
[[ "$escalated" == "0" && "$bounded" == "0" ]]
check "TERM-ignoring leader escalates to SIGKILL within bounded time (${elapsed}s)" "$?"

# --- test 3: low-memory watchdog terminates the group --------------------
SUPP_LOG="$tmp/t3.log"
SUPP_WATCHDOG_MIN_AVAILABLE_KB=99999999999
supp_start_group /dev/null sleep 300
supp_start_watchdog
saved_pgid=$SUPP_PGID
deadline=$((SECONDS + 15))
while kill -0 -- "-$saved_pgid" 2>/dev/null && (( SECONDS < deadline )); do
  sleep 0.5
done
kill -0 -- "-$saved_pgid" 2>/dev/null
still_alive=$?
grep -q 'WATCHDOG LOW MEM' "$tmp/t3.log"
logged=$?
[[ "$still_alive" != "0" && "$logged" == "0" ]]
check "watchdog kills group on low MemAvailable and logs the event" "$?"
supp_stop_watchdog
SUPP_PGID=""
SUPP_PID=""
unset SUPP_WATCHDOG_MIN_AVAILABLE_KB

# --- test 4: runner-style INT trap tears down the whole group -------------
cat > "$tmp/harness.sh" <<EOS
#!/usr/bin/env bash
set -euo pipefail
SUPP_LOG="\$1"
source "$lib"
supp_start_group /dev/null bash -c 'sleep 300 & exec sleep 300'
echo "\$SUPP_PGID" > "\$2"
trap 'supp_stop_group || true' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
while true; do sleep 1; done
EOS
chmod +x "$tmp/harness.sh"
"$tmp/harness.sh" "$tmp/t4.log" "$tmp/t4.pgid" > /dev/null 2>&1 &
harness_pid=$!
deadline=$((SECONDS + 10))
until [[ -s "$tmp/t4.pgid" ]] || (( SECONDS >= deadline )); do
  sleep 0.2
done
[[ -s "$tmp/t4.pgid" ]]
check "harness established group" "$?"
harness_pgid=$(tr -d '[:space:]' < "$tmp/t4.pgid")
# SIGTERM, not SIGINT: a runner launched as a background job with job control
# off inherits SIGINT ignored, and signals ignored on shell entry cannot be
# trapped. The INT trap still covers interactive foreground Ctrl-C.
kill -TERM "$harness_pid"
deadline=$((SECONDS + 15))
while kill -0 "$harness_pid" 2>/dev/null && (( SECONDS < deadline )); do
  sleep 0.5
done
kill -0 "$harness_pid" 2>/dev/null
harness_alive=$?
kill -0 -- "-$harness_pgid" 2>/dev/null
group_alive=$?
[[ "$harness_alive" != "0" && "$group_alive" != "0" ]]
check "SIGTERM to runner tears down entire server group" "$?"
if kill -0 "$harness_pid" 2>/dev/null; then
  kill -KILL "$harness_pid" 2>/dev/null || true
fi
kill -KILL -- "-$harness_pgid" 2>/dev/null || true
wait "$harness_pid" 2>/dev/null || true
harness_pid=""
grep -q 'stop_group complete: group empty' "$tmp/t4.log"
check "cleanup event recorded in run log" "$?"

# --- summary --------------------------------------------------------------
if [[ "$fails" -ne 0 ]]; then
  printf '%d test(s) FAILED\n' "$fails" >&2
  exit 1
fi
printf 'all server-supervision tests passed\n'
