#!/usr/bin/env bash
# Launched by `@reboot` cron (installed 2026-09-05 03:00) on the boot after the 01:43 xe fault: waits for docker, checks
# the boot is fresh (not the faulted one), then runs the R222 INT4 fixed-K matrix (TP2 then TP1, depths 0-3) (see
# scripts/run-20260905-qwen38-int4-fixed-k-r222-matrix-tp2-tp1-mtp0-3.sh).
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts
sleep 120
for i in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 10; done
boot=$(cat /proc/sys/kernel/random/boot_id)
[[ "$boot" == "4634e845-e682-457b-815d-15d069e2638a" ]] && { echo "faulted boot, not launching" > $out/logs/r222-autolaunch.log; exit 2; }
echo "boot $boot $(date -Is): launching R222 matrix" > $out/logs/r222-autolaunch.log
crontab -l 2>/dev/null | grep -v r222-matrix-autolaunch | crontab -
exec bash $S/run-20260905-qwen38-int4-fixed-k-r222-matrix-tp2-tp1-mtp0-3.sh > $out/logs/r222-matrix.log 2>&1
