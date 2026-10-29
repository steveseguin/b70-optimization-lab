#!/usr/bin/env bash
# One more arm of the target-head-split-2026-10-29 suite, launched once after suite_chain.sh finished (not a retry):
# tpts = TP with both the rank-1 target head split and the rank-0 draft head split, same binary, context and cards.
# A fresh lock holder holds all four card locks for the arm, then stops.
set -u
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/target-head-split-2026-10-29
R=/home/steve/llm-optimizations/experiments/own-xpu-runtime/engine/receipts/b7786ad42675.json
exec >>"$D/logs/suite-extra.log" 2>&1
echo "=== extra start $(date -Is)"
grep -q "chain end" "$D/logs/suite-chain.log" || { echo "suite chain not finished"; exit 1; }
[ "$(systemctl --user is-active sc117-tp-svc-th-locks-20261029)" = active ] && { echo "lock holder still active"; exit 1; }
systemd-run --user --unit=sc117-tp-svc-th-locks-20261029 -p Restart=no flock -n -E 75 /dev/shm/card23.lock flock -n -E 75 /dev/shm/card27.lock \
  flock -n -E 75 /dev/shm/card43.lock flock -n -E 75 /dev/shm/card47.lock sleep 7200 || { echo "lock holder failed"; exit 1; }
sleep 2; [ "$(systemctl --user is-active sc117-tp-svc-th-locks-20261029)" = active ] || { echo "lock holder not active"; exit 1; }
echo "--- arm tpts start $(date -Is)"
systemd-run --user --unit=sc117-tp-svc-th-run-tpts-20261029 -p Restart=no --wait --collect -E SC117_ENGINE_RECEIPT=$R bash $D/run_arm.sh tpts
echo "arm tpts: $(cat "$D/logs/STATUS-tpts" 2>/dev/null) at $(date -Is)"
systemctl --user stop sc117-tp-svc-th-locks-20261029
echo "=== extra end $(date -Is)"
