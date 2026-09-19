#!/usr/bin/env bash
# Sample host swap and memory pressure beside a two-card service start, to CSV.
#
# Why this exists
# ---------------
# Five GPU faults on this host have the same shape: the copy engine (bcs) of a B70 takes page faults with
# "Fault response: Unsuccessful -EINVAL" during a model weight load, never during steady-state serving. Three of the
# no-P2P ones are a two-card service start that followed one-card GPU work earlier on the same boot. The working
# hypothesis (NOT proven) is that the kernel swaps or migrates the host staging pages the copy engine reads through
# userptr mappings, and the xe driver answers the resulting GPU page fault with -EINVAL instead of rebinding.
#
# The 2026-09-15 fault note recorded ~4.6 GiB swapped out in the five seconds before that fault, and the boot that
# ended in the 2026-09-19 fault swapped out 15.1 GiB in 49 minutes at vm.swappiness=60. Neither was sampled at
# second resolution, so neither confirms nor kills the hypothesis. This script is the missing measurement.
#
#   CONFIRMS the hypothesis: a pswpout burst in the same second as the fault.
#   KILLS it:                a fault with pswpout flat, or a clean start with a burst.
#
# What it does
# ------------
# Every INTERVAL seconds (default 0.5) it appends one CSV row with, all read from /proc:
#   pswpin, pswpout            /proc/vmstat, cumulative pages since boot
#   pswpin_d, pswpout_d        pages since the previous sample (the burst signal)
#   pgmajfault, pgscan_d       /proc/vmstat, major faults and reclaim scanning since the previous sample
#   mem_available_kb, swap_free_kb, dirty_kb, cached_kb   /proc/meminfo
#   psi_mem_some_avg10, psi_mem_full_avg10                /proc/pressure/memory
# It stops when the watched pid or systemd unit is gone, when TIMEOUT seconds have passed, or on Ctrl-C -- and it
# always writes the trailing summary line to stderr so a truncated run is still readable.
#
# It is READ-ONLY. It starts nothing, stops nothing, kills nothing, and touches no GPU, container or sysctl.
#
# Usage
# -----
#   scripts/measure-swap-during-start.sh --unit fp8-service-20260920-boot --out /mnt/fast-ai/bench-results/swap-20260920.csv
#   scripts/measure-swap-during-start.sh --pid 12870 --timeout 1800 --interval 0.25
#   scripts/measure-swap-during-start.sh --out /tmp/swap.csv --timeout 300          # no target: run for the timeout
#
# Intended use: start it in the background FIRST, then start the service, so the first rows predate the load.
# Do not point it at a service and walk away expecting it to act on anything -- it only records.
#
# Afterwards, line the CSV's `at` column up against the fault second in the kernel log:
#   grep -n 'Fault response: Unsuccessful' <kernel log> | head -1
#   sort -t, -k5 -g -r <csv> | head        # the biggest pswpout_d samples
set -uo pipefail

INTERVAL=0.5
TIMEOUT=3600
PID=""
UNIT=""
OUT=""

usage() {
    sed -n '2,45p' "$0"
    exit "${1:-0}"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --pid)      PID="${2:-}"; shift 2 ;;
        --unit)     UNIT="${2:-}"; shift 2 ;;
        --out)      OUT="${2:-}"; shift 2 ;;
        --interval) INTERVAL="${2:-}"; shift 2 ;;
        --timeout)  TIMEOUT="${2:-}"; shift 2 ;;
        -h|--help)  usage 0 ;;
        *)          echo "unknown argument: $1" >&2; usage 2 ;;
    esac
done

if [ -z "$OUT" ]; then
    echo "--out <csv path> is required" >&2
    exit 2
fi
if [ -n "$PID" ] && [ -n "$UNIT" ]; then
    echo "give --pid or --unit, not both" >&2
    exit 2
fi
if [ -n "$PID" ] && [ ! -d "/proc/$PID" ]; then
    echo "pid $PID is not running; nothing to watch" >&2
    exit 2
fi

mkdir -p "$(dirname "$OUT")" || exit 1

# One field out of /proc/vmstat or /proc/meminfo; 0 if the kernel does not export it.
vmstat_field() { awk -v k="$1" '$1 == k { print $2; found = 1 } END { if (!found) print 0 }' /proc/vmstat; }
meminfo_field() { awk -v k="$1:" '$1 == k { print $2; found = 1 } END { if (!found) print 0 }' /proc/meminfo; }

psi_field() {  # $1 = "some" | "full"; avg10 out of /proc/pressure/memory, 0 if PSI is off
    [ -r /proc/pressure/memory ] || { echo 0; return; }
    awk -v k="$1" '$1 == k { for (i = 2; i <= NF; i++) if (split($i, kv, "=") == 2 && kv[1] == "avg10") print kv[2] }' \
        /proc/pressure/memory | head -1 | grep -E '^[0-9.]+$' || echo 0
}

target_alive() {
    if [ -n "$PID" ]; then
        [ -d "/proc/$PID" ]
    elif [ -n "$UNIT" ]; then
        # --user first (this lab's services are systemd-run --user), then system scope.
        systemctl --user is-active --quiet "$UNIT" 2>/dev/null && return 0
        systemctl is-active --quiet "$UNIT" 2>/dev/null
    else
        return 0   # no target: run until the timeout
    fi
}

STOP=0
trap 'STOP=1' INT TERM

echo "at,elapsed_s,pswpin,pswpout,pswpin_d,pswpout_d,pgmajfault_d,pgscan_d,mem_available_kb,swap_free_kb,dirty_kb,cached_kb,psi_mem_some_avg10,psi_mem_full_avg10,target" > "$OUT"

started=$(date +%s)
prev_in=""; prev_out=""; prev_major=""; prev_scan=""
peak_out_d=0; total_out_d=0; samples=0

# The target may not exist yet when the sampler starts first (the intended order); wait for the timeout, not for it.
while [ "$STOP" -eq 0 ]; do
    now=$(date +%s)
    elapsed=$(( now - started ))
    [ "$elapsed" -ge "$TIMEOUT" ] && break

    swin=$(vmstat_field pswpin)
    swout=$(vmstat_field pswpout)
    major=$(vmstat_field pgmajfault)
    # pgscan_* names vary by kernel; sum whatever is exported.
    scan=$(awk '$1 ~ /^pgscan_/ { s += $2 } END { print s + 0 }' /proc/vmstat)

    if [ -z "$prev_in" ]; then
        din=0; dout=0; dmajor=0; dscan=0
    else
        din=$(( swin - prev_in ))
        dout=$(( swout - prev_out ))
        dmajor=$(( major - prev_major ))
        dscan=$(( scan - prev_scan ))
    fi
    prev_in=$swin; prev_out=$swout; prev_major=$major; prev_scan=$scan

    if target_alive; then alive=1; else alive=0; fi

    printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
        "$(date --iso-8601=seconds)" "$elapsed" \
        "$swin" "$swout" "$din" "$dout" "$dmajor" "$dscan" \
        "$(meminfo_field MemAvailable)" "$(meminfo_field SwapFree)" \
        "$(meminfo_field Dirty)" "$(meminfo_field Cached)" \
        "$(psi_field some)" "$(psi_field full)" "$alive" >> "$OUT"

    samples=$(( samples + 1 ))
    total_out_d=$(( total_out_d + dout ))
    [ "$dout" -gt "$peak_out_d" ] && peak_out_d=$dout

    # Only stop on a dead target once it has been seen alive, so starting the sampler first is safe.
    if { [ -n "$PID" ] || [ -n "$UNIT" ]; } && [ "$alive" -eq 0 ] && [ "${seen_alive:-0}" -eq 1 ]; then
        break
    fi
    [ "$alive" -eq 1 ] && seen_alive=1

    sleep "$INTERVAL"
done

# 4 KiB pages, reported in MiB so the numbers are readable next to MemAvailable.
peak_mib=$(( peak_out_d / 256 ))
total_mib=$(( total_out_d / 256 ))
{
    echo "measure-swap-during-start: $samples samples over $(( $(date +%s) - started )) s -> $OUT"
    echo "  swapped out during the window: ${total_mib} MiB total, peak ${peak_mib} MiB in one ${INTERVAL}s sample"
    echo "  a burst in the same second as an xe fault supports the swap hypothesis; flat pswpout during a fault kills it"
} >&2
