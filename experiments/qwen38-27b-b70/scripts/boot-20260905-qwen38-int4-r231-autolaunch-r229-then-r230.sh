#!/usr/bin/env bash
# Boot autolaunch after the 13:07:50 xe fault (second weight-staging fault on 0000:03:00.0 today): on a fresh boot run the
# R229 ladder screen (R228 grouped GDN spec, depth 4, TP2), then the R230 matrix (TP2 then TP1, depths 0-4) on R228.
# Self-removing crontab line.
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts
sleep 120
for i in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 10; done
boot=$(cat /proc/sys/kernel/random/boot_id)
[[ "$boot" == "9da84c02-7404-4a11-8b45-8b660360e7b1" ]] && { echo "faulted boot, not launching" > $out/logs/r231-autolaunch.log; exit 2; }
echo "boot $boot $(date -Is): launching R229 then R230" > $out/logs/r231-autolaunch.log
crontab -l 2>/dev/null | grep -v r231-autolaunch | crontab -
bash $S/run-20260905-qwen38-int4-r229-r228-gdn-group-ladders-tp2-mtp4.sh > $out/logs/r229-ladders.log 2>&1
exec bash $S/run-20260905-qwen38-int4-r230-matrix-r228-binv-tp2-tp1-mtp0-4.sh > $out/logs/r230-matrix.log 2>&1
