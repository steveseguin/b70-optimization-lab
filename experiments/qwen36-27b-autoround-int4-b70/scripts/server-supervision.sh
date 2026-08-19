#!/usr/bin/env bash
# Process-group supervision for vLLM candidate servers.
#
# Source this file; do not execute it directly.
#
# Why this exists: vLLM's API server spawns EngineCore and VLLM::Worker_TP
# children via multiprocessing. Killing only the API parent orphans those
# workers; on this 15 GiB host they kept consuming pinned/unswappable memory
# until the kernel OOM-killed unrelated desktop processes (see
# experiments/qwen38-27b-b70/notes/2026-08-18-autoround-int4-target-baseline-orphan-workers-lowmem-unsafe.md).
#
# Contract:
#   supp_start_group LOGFILE CMD [ARGS...]
#       Launch CMD in a dedicated session/process group (setsid). Records the
#       leader PID in SUPP_PID and the process-group ID in SUPP_PGID.
#       Returns non-zero if a distinct, safe group could not be established.
#   supp_alive
#       True while any member of the supervised group exists.
#   supp_stop_group
#       SIGTERM the entire group, wait SUPP_TERM_GRACE_S, SIGKILL survivors,
#       wait SUPP_KILL_GRACE_S, reap the direct child, and verify the group is
#       empty. Events are appended to SUPP_LOG (default /dev/null).
#   supp_start_watchdog / supp_stop_watchdog
#       Background poller that terminates the whole group before MemAvailable
#       becomes critically low. Requires SUPP_PGID. Events and periodic memory
#       snapshots are appended to SUPP_LOG.
#
# Tunables (set before calling, or export):
#   SUPP_TERM_GRACE_S             default 20
#   SUPP_KILL_GRACE_S             default 5
#   SUPP_WATCHDOG_POLL_S          default 5
#   SUPP_WATCHDOG_MIN_AVAILABLE_KB default 2621440 (2.5 GiB)
#   SUPP_WATCHDOG_CONFIRM         default 2 consecutive low readings required
#   SUPP_WATCHDOG_SNAPSHOT_S      default 15
#   SUPP_LOG                      default /dev/null

: "${SUPP_TERM_GRACE_S:=20}"
: "${SUPP_KILL_GRACE_S:=5}"
: "${SUPP_WATCHDOG_POLL_S:=5}"
: "${SUPP_WATCHDOG_MIN_AVAILABLE_KB:=2621440}"
: "${SUPP_WATCHDOG_CONFIRM:=2}"
: "${SUPP_WATCHDOG_SNAPSHOT_S:=15}"
: "${SUPP_LOG:=/dev/null}"

SUPP_PID=""
SUPP_PGID=""
SUPP_WATCHDOG_PID=""

supp_log() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$SUPP_LOG" || true
}

supp_group_procs() {
  # Print "pid pgid comm" rows for every process still in the supervised
  # group. Empty output means the group is gone.
  [[ -n "$SUPP_PGID" ]] || return 0
  ps -eo pid=,pgid=,comm= 2>/dev/null \
    | awk -v pg="$SUPP_PGID" '$2 == pg' || true
}

supp_group_stat() {
  # Detailed per-member memory anatomy from /proc: anonymous, file-backed,
  # locked (pinned), and swapped pages. A 6-second host-memory collapse
  # (2026-08-18 smoke) was invisible to ps RSS alone; these fields separate
  # pinned growth from ordinary swapping.
  [[ -n "$SUPP_PGID" ]] || return 0
  local pid
  for pid in $(ps -eo pid=,pgid= 2>/dev/null \
      | awk -v pg="$SUPP_PGID" '$2 == pg {print $1}'); do
    [[ -r "/proc/$pid/status" ]] || continue
    awk -v pid="$pid" '
      /^Name:/    { name=$2 }
      /^VmRSS:/   { rss=$2 }
      /^RssAnon:/ { anon=$2 }
      /^RssFile:/ { file=$2 }
      /^RssShmem:/{ shmem=$2 }
      /^VmLck:/   { lck=$2 }
      /^VmSwap:/  { swap=$2 }
      END { printf "    %s %s rss=%skB anon=%skB file=%skB shmem=%skB locked=%skB swap=%skB\n",
                  pid, name, rss, anon, file, shmem, lck, swap }
    ' "/proc/$pid/status" 2>/dev/null
  done
}

supp_alive() {
  if [[ -n "$SUPP_PGID" ]]; then
    kill -0 -- "-$SUPP_PGID" 2>/dev/null
  elif [[ -n "$SUPP_PID" ]]; then
    kill -0 "$SUPP_PID" 2>/dev/null
  else
    return 1
  fi
}

supp_start_group() {
  local logfile=$1; shift
  local pgid_file own_pgid
  SUPP_PID=""
  SUPP_PGID=""
  pgid_file=$(mktemp "${TMPDIR:-/tmp}/supp-pgid.XXXXXX")

  # setsid gives the child its own session and process group. The inner bash
  # records its own PID (== PGID == SID after setsid) before exec so the
  # parent learns the group ID even if setsid had to fork.
  # shellcheck disable=SC2016 # $$ must expand in the child, not here
  setsid bash -c 'printf "%s\n" "$$" > "$1"; shift; exec "$@"' \
    bash "$pgid_file" "$@" >> "$logfile" 2>&1 &
  SUPP_PID=$!

  for _ in $(seq 1 200); do
    [[ -s "$pgid_file" ]] && break
    kill -0 "$SUPP_PID" 2>/dev/null || { sleep 0.05; [[ -s "$pgid_file" ]] && break; break; }
    sleep 0.05
  done
  if [[ -s "$pgid_file" ]]; then
    SUPP_PGID=$(tr -d '[:space:]' < "$pgid_file")
  fi
  rm -f "$pgid_file"

  if [[ ! "$SUPP_PGID" =~ ^[0-9]+$ ]] || (( SUPP_PGID <= 1 )); then
    supp_log "start_group FAILED: invalid pgid '$SUPP_PGID'"
    SUPP_PGID=""
    return 1
  fi
  # Never allow the recorded group to be the caller's own group: signalling
  # it would kill the runner and everything attached to its terminal.
  own_pgid=$(ps -o pgid= -p $$ 2>/dev/null | tr -d '[:space:]')
  if [[ -z "$own_pgid" || "$SUPP_PGID" == "$own_pgid" ]]; then
    supp_log "start_group FAILED: pgid $SUPP_PGID collides with caller group '$own_pgid'"
    SUPP_PGID=""
    return 1
  fi
  supp_log "start_group pid=$SUPP_PID pgid=$SUPP_PGID cmd=$*"
}

supp_signal_group() {
  # supp_signal_group SIGNAL GRACE_S -> 0 once the group is empty
  local sig=$1 grace=$2 waited=0
  [[ -n "$SUPP_PGID" ]] || return 0
  kill -"$sig" -- "-$SUPP_PGID" 2>/dev/null || true
  while kill -0 -- "-$SUPP_PGID" 2>/dev/null && (( waited < grace )); do
    sleep 1
    waited=$((waited + 1))
  done
  ! kill -0 -- "-$SUPP_PGID" 2>/dev/null
}

supp_stop_group() {
  local remaining rc=0
  supp_log "stop_group begin pid=${SUPP_PID:-} pgid=${SUPP_PGID:-}"
  if [[ -n "$SUPP_PGID" ]] && kill -0 -- "-$SUPP_PGID" 2>/dev/null; then
    if supp_signal_group TERM "$SUPP_TERM_GRACE_S"; then
      supp_log "stop_group SIGTERM drained group within ${SUPP_TERM_GRACE_S}s"
    else
      supp_log "stop_group escalating to SIGKILL after ${SUPP_TERM_GRACE_S}s grace"
      if supp_signal_group KILL "$SUPP_KILL_GRACE_S"; then
        supp_log "stop_group SIGKILL drained group within ${SUPP_KILL_GRACE_S}s"
      else
        supp_log "stop_group ERROR: group $SUPP_PGID still alive after SIGKILL grace"
        rc=1
      fi
    fi
  fi
  if [[ -n "$SUPP_PID" ]]; then
    wait "$SUPP_PID" 2>/dev/null || true
  fi
  remaining=$(supp_group_procs)
  if [[ -n "$remaining" ]]; then
    supp_log "stop_group ERROR: residual group members:"$'\n'"$remaining"
    rc=1
  else
    supp_log "stop_group complete: group empty"
  fi
  # Visibility only: report any vLLM engine/worker process anywhere on the
  # host so a leaked run is obvious in cleanup.log. Never signal these; they
  # may belong to someone else.
  local stray
  stray=$(ps -eo pid=,comm= 2>/dev/null | awk '$2 ~ /^VLLM::/ || $2 ~ /EngineCore/') || true
  if [[ -n "$stray" ]]; then
    supp_log "stop_group NOTE: vLLM-named processes still present on host:"$'\n'"$stray"
  fi
  SUPP_PID=""
  SUPP_PGID=""
  return "$rc"
}

supp_start_watchdog() {
  if [[ -z "$SUPP_PGID" && -z "$SUPP_PID" ]]; then
    supp_log "watchdog not started: no supervised group"
    return 1
  fi
  supp_stop_watchdog
  (
    low_streak=0
    elapsed=0
    last_snapshot=-$SUPP_WATCHDOG_SNAPSHOT_S
    while true; do
      if [[ -n "$SUPP_PGID" ]]; then
        kill -0 -- "-$SUPP_PGID" 2>/dev/null || break
      elif [[ -n "$SUPP_PID" ]]; then
        kill -0 "$SUPP_PID" 2>/dev/null || break
      else
        break
      fi
      avail=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo 2>/dev/null)
      swap_free=$(awk '/^SwapFree:/ {print $2}' /proc/meminfo 2>/dev/null)
      if [[ "$avail" =~ ^[0-9]+$ ]] \
        && (( avail < SUPP_WATCHDOG_MIN_AVAILABLE_KB )); then
        low_streak=$((low_streak + 1))
      else
        low_streak=0
      fi
      if (( low_streak >= SUPP_WATCHDOG_CONFIRM )); then
        {
          printf '%s WATCHDOG LOW MEM: MemAvailable=%skB < %skB (SwapFree=%skB), %s consecutive readings\n' \
            "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$avail" \
            "$SUPP_WATCHDOG_MIN_AVAILABLE_KB" "${swap_free:-?}" "$low_streak"
          printf '  terminating supervised group pgid=%s pid=%s\n' \
            "$SUPP_PGID" "$SUPP_PID"
        } >> "$SUPP_LOG"
        supp_group_stat >> "$SUPP_LOG" 2>/dev/null || true
        kill -TERM -- "-$SUPP_PGID" 2>/dev/null || true
        waited=0
        while kill -0 -- "-$SUPP_PGID" 2>/dev/null \
          && (( waited < SUPP_TERM_GRACE_S )); do
          sleep 1
          waited=$((waited + 1))
        done
        if kill -0 -- "-$SUPP_PGID" 2>/dev/null; then
          kill -KILL -- "-$SUPP_PGID" 2>/dev/null || true
          printf '%s WATCHDOG escalated to SIGKILL for pgid=%s\n' \
            "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$SUPP_PGID" >> "$SUPP_LOG"
        fi
        printf '%s WATCHDOG termination sequence finished\n' \
          "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$SUPP_LOG"
        break
      fi
      if (( elapsed - last_snapshot >= SUPP_WATCHDOG_SNAPSHOT_S )); then
        {
          printf '%s snapshot MemAvailable=%skB SwapFree=%skB committed_as=%skB group:\n' \
            "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${avail:-?}" "${swap_free:-?}" \
            "$(awk '/^Committed_AS:/ {print $2}' /proc/meminfo 2>/dev/null)"
        } >> "$SUPP_LOG"
        supp_group_stat >> "$SUPP_LOG" 2>/dev/null || true
        last_snapshot=$elapsed
      fi
      sleep "$SUPP_WATCHDOG_POLL_S"
      elapsed=$((elapsed + SUPP_WATCHDOG_POLL_S))
    done
  ) &
  SUPP_WATCHDOG_PID=$!
  supp_log "watchdog started pid=$SUPP_WATCHDOG_PID min_available_kb=$SUPP_WATCHDOG_MIN_AVAILABLE_KB poll_s=$SUPP_WATCHDOG_POLL_S"
}

supp_stop_watchdog() {
  if [[ -n "$SUPP_WATCHDOG_PID" ]]; then
    kill "$SUPP_WATCHDOG_PID" 2>/dev/null || true
    wait "$SUPP_WATCHDOG_PID" 2>/dev/null || true
    SUPP_WATCHDOG_PID=""
  fi
}
