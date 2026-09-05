#!/usr/bin/env bash
# Launched by `@reboot` cron (installed 2026-09-05 03:00) on the boot after the 01:43 xe fault: waits for docker, checks
# the boot is fresh (not the faulted one), then runs the R215 TP1 full campaign on GPU 0 (leaves GPU 1 free for
# kernel work). Remove the crontab line once the campaign has run: `crontab -l | grep -v r215-tp1-autolaunch | crontab -`.
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts
sleep 120
for i in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 10; done
boot=$(cat /proc/sys/kernel/random/boot_id)
[[ "$boot" == "4634e845-e682-457b-815d-15d069e2638a" ]] && { echo "faulted boot, not launching" > $out/logs/r215-autolaunch.log; exit 2; }
echo "boot $boot $(date -Is): launching R215 TP1" > $out/logs/r215-autolaunch.log
crontab -l 2>/dev/null | grep -v r215-tp1-autolaunch | crontab -
exec bash $S/run-20260905-qwen38-int4-gptq-relabel-r215-tp1-full-after-r214b.sh > $out/logs/r215-tp1.log 2>&1
