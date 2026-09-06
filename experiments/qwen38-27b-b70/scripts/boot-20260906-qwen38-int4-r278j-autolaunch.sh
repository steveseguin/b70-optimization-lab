#!/usr/bin/env bash
# Boot autolaunch after the 12:48 xe fault (third of 2026-09-06): run R278j (profiled launcher-chain server at c32) on a fresh
# boot. Self-removing crontab line.
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts
sleep 120
for i in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 10; done
boot=$(cat /proc/sys/kernel/random/boot_id)
[[ "$boot" == "0f3e2d24-6c7b-4f54-9722-a62ae5d12853" ]] && { echo "faulted boot, not launching" > $out/logs/r278j-autolaunch.log; exit 2; }
echo "boot $boot $(date -Is): launching R278j" > $out/logs/r278j-autolaunch.log
crontab -l 2>/dev/null | grep -v r278j-autolaunch | crontab -
RUN=r278j2 SPEC_GROUP_OVERRIDE=64 SPLIT_MIXED=1 exec bash $S/run-20260906-qwen38-int4-r278j-launcher-chain-profile.sh > $out/logs/r278j2.log 2>&1
