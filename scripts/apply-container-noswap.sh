#!/usr/bin/env bash
# Take the swap allowance away from a service container as soon as it appears, before its weight load.
#
# SUPERSEDED (2026-09-19): the three validation starts this script was written for all passed, and both FP8
# launchers now ship `--memory 12g --memory-swap 12g` themselves, so a normally started service already comes up
# with memory.swap.max=0 and this script has nothing left to fix. It does NOT need to be armed beside a start any
# more. It is kept, not deleted, because it is still the way to (a) apply or check the setting on a container that
# was started from an older launcher or from a pinned published packet -- the evidence packets carry the previous
# `--memory-swap 16g` bytes until the next acceptance run re-freezes them -- and (b) do the same experiment again
# with a different cap, by passing --memory. Running it beside a current start is harmless: it finds the container
# already at memory.swap.max=0 and the `docker update` is a no-op.
#
# Why this exists
# ---------------
# Both FP8 launchers ran the server with `--memory 12g --memory-swap 16g` until 2026-09-19, which in cgroup v2 is
# memory.max=12G plus memory.swap.max=4G. The 29 GB of safetensors stream through the CONTAINER's page cache, the
# cgroup hits its own 12 GiB ceiling about two thousand times, and cgroup reclaim swaps the container's anonymous
# pages out to its 4 GiB allowance -- whatever the host's vm.swappiness is. Measured on 2026-09-19 at
# vm.swappiness=1: 4.41 GiB swapped out during a start, 3.94 GiB of it from inside the container, memory.peak
# exactly memory.max and memory.swap.peak exactly memory.swap.max.
#
#   experiments/qwen38-27b-b70/notes/2026-09-19-container-memory-cap-swap.md
#
# Docker's `--memory-swap` is memory PLUS swap, so setting it equal to `--memory` means no swap at all: cgroup v2
# gets memory.swap.max=0, and at the ceiling the kernel must drop clean file pages (the weight file's cache,
# re-readable from disk) instead of swapping live anonymous pages the GPU copy engine may be reading.
#
# This script validated that change on a RUNNING container, before either `serve.py` was edited -- those files are
# byte-pinned by published evidence packets, so the edit was the last step, not the first. Three starts passed
# (container pswpout 0, oom_kill 0, 12/12 exact, no fault lines, weight load no slower) and the edit is now in.
#
# What it does
# ------------
#   1. Records the container ids that already exist when it starts. Those are ignored: it waits for a NEW one.
#   2. Polls for a container whose name starts with --name-prefix and which was created after this script started.
#   3. Refuses (exit 4) if that container's memory.current is already above --max-current (default 6 GiB), which
#      means the weight load is well under way and applying the change now measures nothing.
#   4. Logs the before values, runs `docker update --memory <m> --memory-swap <m> <name>`, logs the after values.
#   5. Verifies the cgroup now reads memory.swap.max = 0 and memory.max = <m>. Exits 5 if it does not.
#
# It touches ONE container -- the new one it was waiting for -- and only its memory limits. It starts nothing,
# stops nothing, kills nothing, and never touches the GPU, a systemd unit or a sysctl.
#
# Usage
# -----
#   scripts/apply-container-noswap.sh --name-prefix neural-fp8
#   scripts/apply-container-noswap.sh --name-prefix neural-fp8 --memory 12g --timeout 300
#
# Intended use: start it in the background FIRST, then start the service, so it is already waiting when the
# container is created. The window is wide -- on 2026-09-19 the container appeared at t=17 s and the first
# safetensors read was at t=76 s -- but it is not unlimited, which is what --max-current guards.
#
# Do NOT run it against a container that is already serving: a running server's limits are not a thing to change
# under load, and --max-current will refuse it anyway.
#
# Afterwards, confirm the change did its job by reading the container's own counters:
#   docker inspect <name> --format '{{.HostConfig.Memory}} {{.HostConfig.MemorySwap}}'
#   grep -E '^(pswpout|pswpin|anon|file) ' /sys/fs/cgroup/system.slice/docker-<id>.scope/memory.stat
#   cat /sys/fs/cgroup/system.slice/docker-<id>.scope/memory.events     # max > 0 is expected; oom_kill must be 0
#
# Exit codes: 0 applied and verified, 2 bad arguments, 3 timed out with no new container, 4 found it too late,
# 5 docker update failed or the cgroup did not read back as expected.
set -uo pipefail

NAME_PREFIX=""
MEMORY="12g"
TIMEOUT=300
INTERVAL=0.5
MAX_CURRENT=$(( 6 * 1024 * 1024 * 1024 ))

usage() {
    sed -n '2,50p' "$0"
    exit "${1:-0}"
}

log() { printf '[%s] %s\n' "$(date -Is)" "$*"; }

while [ $# -gt 0 ]; do
    case "$1" in
        --name-prefix)  NAME_PREFIX="${2:-}"; shift 2 ;;
        --memory)       MEMORY="${2:-}"; shift 2 ;;
        --timeout)      TIMEOUT="${2:-}"; shift 2 ;;
        --interval)     INTERVAL="${2:-}"; shift 2 ;;
        --max-current)  MAX_CURRENT="${2:-}"; shift 2 ;;
        -h|--help)      usage 0 ;;
        *)              echo "unknown argument: $1" >&2; usage 2 ;;
    esac
done

if [ -z "$NAME_PREFIX" ]; then
    echo "--name-prefix <prefix> is required (e.g. neural-fp8)" >&2
    exit 2
fi
case "$MEMORY" in
    [0-9]*[gGmM]|[0-9]*) : ;;
    *) echo "--memory must be a docker size such as 12g: got '$MEMORY'" >&2; exit 2 ;;
esac
case "$TIMEOUT" in
    ''|*[!0-9]*) echo "--timeout must be a whole number of seconds: got '$TIMEOUT'" >&2; exit 2 ;;
esac
case "$MAX_CURRENT" in
    ''|*[!0-9]*) echo "--max-current must be a whole number of bytes: got '$MAX_CURRENT'" >&2; exit 2 ;;
esac
command -v docker > /dev/null 2>&1 || { echo "docker is not on PATH" >&2; exit 2; }

# Bytes for the --memory value, so the verification can compare against memory.max.
memory_bytes() {
    local v="$1" n unit
    n="${v%[gGmMkK]}"
    unit="${v#"$n"}"
    case "$unit" in
        g|G) echo $(( n * 1024 * 1024 * 1024 )) ;;
        m|M) echo $(( n * 1024 * 1024 )) ;;
        k|K) echo $(( n * 1024 )) ;;
        *)   echo "$n" ;;
    esac
}
WANT_MAX=$(memory_bytes "$MEMORY")

# The cgroup directory of a container id, under either the system slice (dockerd as a system service, the layout
# on this host) or the cgroupfs driver's own tree. Prints nothing if neither exists.
cgroup_dir() {
    local id="$1" d
    for d in "/sys/fs/cgroup/system.slice/docker-$id.scope" \
             "/sys/fs/cgroup/docker/$id" \
             "/sys/fs/cgroup/system.slice/docker.service/docker-$id.scope"; do
        [ -d "$d" ] && { echo "$d"; return 0; }
    done
    return 1
}

cg_read() {  # $1 = cgroup dir, $2 = file; prints the value or "unreadable"
    if [ -r "$1/$2" ]; then cat "$1/$2"; else echo unreadable; fi
}

report_cgroup() {  # $1 = label, $2 = cgroup dir
    local d="$2" f
    if [ -z "$d" ]; then
        log "$1: cgroup directory not found; reporting docker inspect only"
        return
    fi
    for f in memory.max memory.swap.max memory.current memory.swap.current memory.peak memory.swap.peak; do
        log "$1: $f = $(cg_read "$d" "$f")"
    done
    log "$1: memory.events = $(tr '\n' ' ' < "$d/memory.events" 2> /dev/null || echo unreadable)"
}

report_inspect() {  # $1 = label, $2 = container name
    log "$1: HostConfig Memory/MemorySwap = $(docker inspect "$2" \
        --format '{{.HostConfig.Memory}} / {{.HostConfig.MemorySwap}}' 2> /dev/null || echo unreadable)"
}

log "waiting up to ${TIMEOUT}s for a NEW container named ${NAME_PREFIX}* (poll ${INTERVAL}s)"

# Every container that exists right now, running or not. A container already in this set is not ours.
# --no-trunc matters: the poll below reads full ids, and a truncated id here would never match one, which would
# make the live service container look new.
PRE_EXISTING=$(docker ps -aq --no-trunc 2> /dev/null | tr '\n' ' ')
log "ignoring containers that already exist: ${PRE_EXISTING:-none}"

started=$(date +%s)
FOUND_ID=""
FOUND_NAME=""

while :; do
    now=$(date +%s)
    if [ $(( now - started )) -ge "$TIMEOUT" ]; then
        log "timed out after ${TIMEOUT}s with no new ${NAME_PREFIX}* container; nothing was changed"
        exit 3
    fi

    while read -r id name; do
        [ -n "$id" ] || continue
        case "$name" in "$NAME_PREFIX"*) ;; *) continue ;; esac
        case " $PRE_EXISTING " in *" $id "*) continue ;; esac
        FOUND_ID="$id"
        FOUND_NAME="$name"
        break
    done <<< "$(docker ps -a --no-trunc --format '{{.ID}} {{.Names}}' 2> /dev/null)"

    [ -n "$FOUND_ID" ] && break
    sleep "$INTERVAL"
done

log "found new container $FOUND_NAME ($FOUND_ID) after $(( $(date +%s) - started ))s"

CG=""
if CG=$(cgroup_dir "$FOUND_ID"); then
    log "cgroup $CG"
else
    CG=""
    log "WARNING: no cgroup directory found for $FOUND_ID; the update will be applied but cannot be verified in sysfs"
fi

# Too late? A container part-way through its weight load is not a valid measurement.
CURRENT=""
if [ -n "$CG" ] && [ -r "$CG/memory.current" ]; then
    CURRENT=$(cat "$CG/memory.current")
fi
if [ -n "$CURRENT" ] && [ "$CURRENT" -gt "$MAX_CURRENT" ]; then
    log "TOO LATE: memory.current is $CURRENT bytes, above the $MAX_CURRENT limit -- the weight load has begun."
    log "Nothing was changed. Let this start finish and catch the next one earlier."
    exit 4
fi
log "memory.current at discovery = ${CURRENT:-unknown} bytes (limit $MAX_CURRENT)"

report_inspect BEFORE "$FOUND_NAME"
report_cgroup BEFORE "$CG"

log "applying: docker update --memory $MEMORY --memory-swap $MEMORY $FOUND_NAME"
if ! docker update --memory "$MEMORY" --memory-swap "$MEMORY" "$FOUND_NAME"; then
    log "docker update FAILED; the container keeps its original limits"
    exit 5
fi

report_inspect AFTER "$FOUND_NAME"
report_cgroup AFTER "$CG"

# Verify. `--memory-swap` == `--memory` is docker's way of saying "no swap"; cgroup v2 shows memory.swap.max = 0.
if [ -z "$CG" ]; then
    log "applied, but the cgroup could not be read back; verify by hand before trusting this run"
    exit 5
fi
GOT_MAX=$(cg_read "$CG" memory.max)
GOT_SWAP=$(cg_read "$CG" memory.swap.max)
if [ "$GOT_SWAP" != "0" ]; then
    log "VERIFY FAILED: memory.swap.max is '$GOT_SWAP', expected 0"
    exit 5
fi
if [ "$GOT_MAX" != "$WANT_MAX" ]; then
    log "VERIFY FAILED: memory.max is '$GOT_MAX', expected $WANT_MAX (from --memory $MEMORY)"
    exit 5
fi

log "OK: $FOUND_NAME now has memory.max=$GOT_MAX and memory.swap.max=0 -- it cannot swap."
log "After the start, check: container pswpout ~0, memory.events max > 0, memory.events oom_kill = 0."
exit 0
