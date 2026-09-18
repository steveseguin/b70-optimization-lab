#!/usr/bin/env bash
# Host-RAM watchdog: kill OUR job before systemd-oomd touches the user's session.
#
#   ./mem-watchdog.sh <pid> <min_avail_mib> <logfile>
#   ./mem-watchdog.sh --self-test [logfile]
#
# Why this exists
# ---------------
# On 2026-09-17 23:09 EDT a MiniMax-H3 first-light run and a kernel-build container shared this
# 15 GiB host. The build's compilers were OOM-killed, and then `systemd-oomd` -- which watches
# MEMORY PRESSURE, not usage -- killed up through `user@1000.service` itself, taking the desktop
# and every `systemd-run --user` unit with it (see
# ../../qwen38-27b-b70/notes/2026-09-18-host-oomd-incident.md). The cgroup `MemoryMax=4G`
# "tripwire" on that run was the cause, not the cure: a limit below the real working set makes the
# cgroup reclaim-thrash, and sustained reclaim IS the pressure oomd kills on.
#
# oomd's rule on this host (`oomctl`): `/user.slice/user-1000.slice/user@1000.service`, memory
# pressure limit 50 % sustained for 20 s. So this watchdog has to fire first and it has to fire on
# a cheaper signal: a floor on MemAvailable, plus `some avg10` pressure well under oomd's limit and
# far under its 20 s window. It kills ONE process (ours). It never touches a service, a container,
# a driver or any kernel tunable, and it changes nothing about the host's oomd configuration.
#
# Trip rule
# ---------
# Every 0.5 s it reads `MemAvailable` from /proc/meminfo and the `some avg10` field of
# /proc/pressure/memory. A poll is BAD when either
#
#     MemAvailable < min_avail_mib          or      some avg10 > 40
#
# `TRIP_POLLS` consecutive bad polls (default 3, i.e. 1.5 s) SIGKILL the target; one good poll
# resets the counter. A hard floor (MemAvailable < min_avail_mib / 2) kills on the first poll --
# at that point waiting 1.5 s is itself the risk.
#
# What it kills: the pid, then the pid's process group, then any surviving direct children. The
# group kill is SKIPPED when the target shares this watchdog's own process group, so a watchdog
# started beside its job in a plain script can never take out the launcher. Give the job its own
# process group (`set -m` and `cmd &` in bash) to get the group kill.
#
# Exit codes: 0 the target exited on its own (or was never there); 3 the watchdog killed it;
# 2 usage error. The self-test needs no GPU, no model, no root, and allocates nothing.
#
# Env overrides: POLL_SECONDS (0.5), PRESSURE_LIMIT (40), TRIP_POLLS (3), HARD_FLOOR_DIVISOR (2).

set -uo pipefail

POLL_SECONDS="${POLL_SECONDS:-0.5}"
PRESSURE_LIMIT="${PRESSURE_LIMIT:-40}"
TRIP_POLLS="${TRIP_POLLS:-3}"
HARD_FLOOR_DIVISOR="${HARD_FLOOR_DIVISOR:-2}"

LOGFILE=""

log() {  # log <message>
    local line
    line="$(date -Is) mem-watchdog[$$] $*"
    printf '%s\n' "${line}" >&2
    if [ -n "${LOGFILE}" ]; then printf '%s\n' "${line}" >>"${LOGFILE}"; fi
}

mem_avail_mib() {
    awk '/^MemAvailable:/ {printf "%d", $2/1024; exit}' /proc/meminfo
}

# `some avg10` from /proc/pressure/memory, as an integer percent (rounded down).
pressure_some_avg10() {
    awk '/^some/ {sub("avg10=", "", $2); printf "%d", $2; exit}' /proc/pressure/memory 2>/dev/null
}

pressure_some_avg10_raw() {
    awk '/^some/ {sub("avg10=", "", $2); print $2; exit}' /proc/pressure/memory 2>/dev/null
}

pgid_of() {  # pgid_of <pid>
    ps -o pgid= -p "$1" 2>/dev/null | tr -d ' '
}

alive() {  # alive <pid>
    kill -0 "$1" 2>/dev/null
}

kill_target() {  # kill_target <pid> <reason>
    local pid="$1" reason="$2" tpgid wpgid kids
    tpgid="$(pgid_of "${pid}")"
    wpgid="$(pgid_of $$)"
    log "KILL pid=${pid} pgid=${tpgid:-?} reason: ${reason}"

    kill -KILL "${pid}" 2>/dev/null

    if [ -n "${tpgid}" ] && [ "${tpgid}" != "${wpgid}" ] && [ "${tpgid}" != "1" ]; then
        log "KILL process group -${tpgid}"
        kill -KILL -- "-${tpgid}" 2>/dev/null
    else
        log "skipping group kill (target pgid ${tpgid:-?} is this watchdog's own group ${wpgid}); \
give the job its own process group with 'set -m' to enable it"
    fi

    # Anything that reparented or escaped the group: direct children of the target.
    kids="$(ps -o pid= --ppid "${pid}" 2>/dev/null | tr -d ' ' | tr '\n' ' ')"
    if [ -n "${kids// /}" ]; then
        log "KILL surviving children: ${kids}"
        # shellcheck disable=SC2086
        kill -KILL ${kids} 2>/dev/null
    fi
}

watch_pid() {  # watch_pid <pid> <min_avail_mib>
    local pid="$1" min="$2"
    local hard=$(( min / HARD_FLOOR_DIVISOR ))
    local bad=0 avail press polls=0 low_avail=999999999 high_press=0

    log "watching pid=${pid} min_avail=${min} MiB (hard floor ${hard} MiB), pressure some avg10 > ${PRESSURE_LIMIT}, \
${TRIP_POLLS} consecutive bad polls at ${POLL_SECONDS}s"
    if ! alive "${pid}"; then
        log "pid ${pid} is not running; nothing to watch"
        return 0
    fi

    while alive "${pid}"; do
        avail="$(mem_avail_mib)"
        press="$(pressure_some_avg10)"
        [ -n "${avail}" ] || avail=999999999
        [ -n "${press}" ] || press=0
        polls=$(( polls + 1 ))
        [ "${avail}" -lt "${low_avail}" ] && low_avail="${avail}"
        [ "${press}" -gt "${high_press}" ] && high_press="${press}"

        if [ "${avail}" -lt "${hard}" ]; then
            kill_target "${pid}" "MemAvailable ${avail} MiB below the hard floor ${hard} MiB \
(pressure some avg10=$(pressure_some_avg10_raw))"
            log "summary: ${polls} polls, low MemAvailable ${low_avail} MiB, peak some avg10 ${high_press}"
            return 3
        fi

        if [ "${avail}" -lt "${min}" ] || [ "${press}" -gt "${PRESSURE_LIMIT}" ]; then
            bad=$(( bad + 1 ))
            log "bad poll ${bad}/${TRIP_POLLS}: MemAvailable=${avail} MiB (min ${min}), \
some avg10=$(pressure_some_avg10_raw) (limit ${PRESSURE_LIMIT})"
            if [ "${bad}" -ge "${TRIP_POLLS}" ]; then
                kill_target "${pid}" "${bad} consecutive bad polls: MemAvailable=${avail} MiB (min ${min}), \
some avg10=$(pressure_some_avg10_raw) (limit ${PRESSURE_LIMIT})"
                log "summary: ${polls} polls, low MemAvailable ${low_avail} MiB, peak some avg10 ${high_press}"
                return 3
            fi
        elif [ "${bad}" -ne 0 ]; then
            log "recovered: MemAvailable=${avail} MiB, some avg10=$(pressure_some_avg10_raw)"
            bad=0
        fi

        sleep "${POLL_SECONDS}"
    done

    log "pid ${pid} exited on its own; ${polls} polls, low MemAvailable ${low_avail} MiB, \
peak some avg10 ${high_press}"
    return 0
}

self_test() {
    # Three checks, no job, no GPU, no allocation:
    #   1. an impossible min_avail trips the watchdog and the target really dies;
    #   2. a target that exits on its own ends the watch with rc 0;
    #   3. the pressure limit alone trips it (PRESSURE_LIMIT=-1 makes every poll bad).
    local rc fails=0 pid t0 t1
    log "SELF-TEST start (MemAvailable now $(mem_avail_mib) MiB, some avg10 $(pressure_some_avg10_raw))"

    # --- 1. low-memory trip -------------------------------------------------------------------
    sleep 120 &
    pid=$!
    t0="$(date +%s)"
    ( TRIP_POLLS=2 watch_pid "${pid}" 99999999 )
    rc=$?
    t1="$(date +%s)"
    if [ "${rc}" -ne 3 ]; then log "SELF-TEST 1 FAIL: expected rc 3, got ${rc}"; fails=$(( fails + 1 ));
    elif alive "${pid}"; then log "SELF-TEST 1 FAIL: target ${pid} is still alive"; fails=$(( fails + 1 ));
    else log "SELF-TEST 1 pass: impossible min_avail killed the target in $(( t1 - t0 ))s (rc 3)"; fi
    wait "${pid}" 2>/dev/null

    # --- 2. clean exit ------------------------------------------------------------------------
    sleep 1 &
    pid=$!
    watch_pid "${pid}" 1
    rc=$?
    if [ "${rc}" -ne 0 ]; then log "SELF-TEST 2 FAIL: expected rc 0, got ${rc}"; fails=$(( fails + 1 ));
    else log "SELF-TEST 2 pass: target exited on its own, watchdog returned 0"; fi
    wait "${pid}" 2>/dev/null

    # --- 3. pressure trip ---------------------------------------------------------------------
    sleep 120 &
    pid=$!
    ( PRESSURE_LIMIT=-1 TRIP_POLLS=3 watch_pid "${pid}" 1 )
    rc=$?
    if [ "${rc}" -ne 3 ]; then log "SELF-TEST 3 FAIL: expected rc 3, got ${rc}"; fails=$(( fails + 1 ));
    elif alive "${pid}"; then log "SELF-TEST 3 FAIL: target ${pid} is still alive"; fails=$(( fails + 1 ));
    else log "SELF-TEST 3 pass: pressure limit killed the target (rc 3)"; fi
    wait "${pid}" 2>/dev/null

    # --- 4. group-kill guard ------------------------------------------------------------------
    # The watchdog must refuse to group-kill when the target shares its process group. Checked by
    # reading the log line, because the alternative (it does not refuse) kills this shell.
    if [ -n "${LOGFILE}" ] && grep -q "skipping group kill" "${LOGFILE}"; then
        log "SELF-TEST 4 pass: group kill was skipped for a same-group target"
    elif [ -n "${LOGFILE}" ]; then
        log "SELF-TEST 4 FAIL: expected a 'skipping group kill' line (same-group target)"
        fails=$(( fails + 1 ))
    else
        log "SELF-TEST 4 skipped (no logfile given)"
    fi

    # --- 5. the real group kill ---------------------------------------------------------------
    # A target in its OWN process group (setsid), holding a child: the group kill must take both.
    # This is the path a `set -m` background job in smoke_h3.sh actually takes.
    local pidfile leader child waited
    pidfile="$(mktemp)"
    setsid bash -c 'sleep 300 & echo "$$ $!" >"$1"; wait' bash "${pidfile}" &
    waited=0
    while [ ! -s "${pidfile}" ] && [ "${waited}" -lt 20 ]; do sleep 0.1; waited=$(( waited + 1 )); done
    read -r leader child <"${pidfile}" 2>/dev/null || true
    rm -f "${pidfile}"
    if [ -z "${leader:-}" ]; then
        log "SELF-TEST 5 FAIL: the setsid target never reported its pid"
        fails=$(( fails + 1 ))
    else
        ( TRIP_POLLS=2 watch_pid "${leader}" 99999999 )
        rc=$?
        sleep 0.3
        if [ "${rc}" -ne 3 ]; then
            log "SELF-TEST 5 FAIL: expected rc 3, got ${rc}"; fails=$(( fails + 1 ))
        elif alive "${leader}" || alive "${child}"; then
            log "SELF-TEST 5 FAIL: leader ${leader} or child ${child} survived the group kill"
            kill -KILL "${leader}" "${child}" 2>/dev/null
            fails=$(( fails + 1 ))
        else
            log "SELF-TEST 5 pass: group kill took the setsid leader ${leader} and its child ${child}"
        fi
    fi

    if [ "${fails}" -eq 0 ]; then log "SELF-TEST: all checks passed"; return 0; fi
    log "SELF-TEST: ${fails} check(s) FAILED"
    return 1
}

main() {
    case "${1:-}" in
        --self-test)
            LOGFILE="${2:-}"
            [ -n "${LOGFILE}" ] && : >"${LOGFILE}"
            self_test
            ;;
        -h|--help|"")
            sed -n '2,45p' "$0"
            exit 2
            ;;
        *)
            if [ "$#" -ne 3 ]; then
                echo "usage: $0 <pid> <min_avail_mib> <logfile>   |   $0 --self-test [logfile]" >&2
                exit 2
            fi
            case "$1$2" in *[!0-9]*) echo "pid and min_avail_mib must be integers" >&2; exit 2;; esac
            LOGFILE="$3"
            mkdir -p "$(dirname "${LOGFILE}")" 2>/dev/null
            watch_pid "$1" "$2"
            ;;
    esac
}

main "$@"
