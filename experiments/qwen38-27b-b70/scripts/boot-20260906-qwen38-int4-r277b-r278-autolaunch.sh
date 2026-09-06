#!/usr/bin/env bash
# Boot autolaunch after the 04:47:00 xe fault on 0000:03:00.0 (weight-staging fault during the R277 load): on a fresh boot
# run R277b (R276 sync-free image, GDN spec group 16, capture sizes to 320, two-pass c1-c64 ladders) then the R278 c32
# request-shape A/B. Self-removing crontab line.
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts
sleep 120
for i in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 10; done
boot=$(cat /proc/sys/kernel/random/boot_id)
[[ "$boot" == "ed4d21d5-0c16-4e74-9aac-79476d203966" ]] && { echo "faulted boot, not launching" > $out/logs/r277b-autolaunch.log; exit 2; }
echo "boot $boot $(date -Is): launching R277b then R278" > $out/logs/r277b-autolaunch.log
crontab -l 2>/dev/null | grep -v r277b-r278-autolaunch | crontab -
RUN=r277b bash $S/run-20260906-qwen38-int4-r277-r276-image-sizes-320-ladders.sh > $out/logs/r277b-ladders.log 2>&1
exec bash $S/run-20260906-qwen38-int4-r278-c32-request-shape-ab.sh > $out/logs/r278-ab.log 2>&1
