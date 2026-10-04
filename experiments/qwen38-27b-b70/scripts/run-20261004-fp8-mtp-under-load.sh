#!/usr/bin/env bash
# The load-fault fix test (step 0 below), then two preregistered tests (notes/2026-10-04-fp8-multiuser-prereg.md, 06:30 and 06:40 EDT addenda):
#  1. Speculation under load: shipped depth-5 MTP plus the three exactness overlays,
#     4 users, then 8 if 4 is exact on long prompts.
#  2. One logits exchange per step (B70_LM_HEAD_CHUNK_AT=head), speculation off, 64 users then 16.
#
# The first attempt faulted at weight load (notes/2026-10-04-gpu-fault-mtp-start.md),
# so this refuses to run on that boot or on any boot whose kernel log already has
# a GPU fault line. If a server hits that same model-load fault here, the campaign
# recovers once by itself (stop, health probe, one fresh start); a second fault halts. Run it in its own unit:
#   systemd-run --user --unit fp8-mtp-under-load --collect \
#     bash experiments/qwen38-27b-b70/scripts/run-20261004-fp8-mtp-under-load.sh
# It leaves no server running.
set -u
cd "$(dirname "$0")/../../.." || exit 2
FAULTED_BOOT=66541315-49f1-41f7-af1d-4756d6b89c9c
# OWNER_OK_SINCE="2026-10-04 09:40": the owner chose a health check over a reboot (2026-10-04, probe passed 09:40 EDT).
# Then only kernel lines after that time count, and any new fault halts everything: the next step is a reboot.
if [ -n "${OWNER_OK_SINCE:-}" ]; then
  SINCE=(--since "$OWNER_OK_SINCE")
elif [ "$(cat /proc/sys/kernel/random/boot_id)" = "$FAULTED_BOOT" ]; then
  echo "refusing: still on the boot that faulted; reboot, or set OWNER_OK_SINCE after a passing health check" >&2; exit 3
else
  SINCE=()
fi
if journalctl -k -b --no-pager "${SINCE[@]}" | grep -qE 'xe 0000:.*(Fault response|Engine memory CAT error|Timedout job|device coredump has been created)'; then
  echo "refusing: the kernel log already has a GPU fault line" >&2; exit 3
fi
STAMP=${STAMP:-$(date +%Y%m%d)}
# 0. The load-fault fix (chunked upload overlay): allocation log with it, then the strict gate.
O=/mnt/fast-ai/bench-results/fp8-loadcopy-$STAMP
[ -e "$O" ] && O=$O-$(date +%H%M)
MU_MODE=loadcopy CAMPAIGN_OUT=$O python3 experiments/qwen38-27b-b70/scripts/run-20261004-fp8-multiuser-campaign.py
[ -f "$O/FAULT-HALT.json" ] && exit 4
# Later starts use the overlay only if it gave 12/12 exact answers.
if python3 -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if any(d.get(k,{}).get('strict',{}).get('exact')=='12/12' for k in ('tp2-loadcopy-chunked','tp2-loadcopy-chunked-retry')) else 1)" "$O/results.json"; then
  export MU_LOADCOPY_FIX=1; echo "chunked upload passed the strict gate; later starts use it"
else
  echo "chunked upload did not pass the strict gate; later starts do not use it"
fi
for n in 4 8; do
  O=/mnt/fast-ai/bench-results/fp8-multiuser-three-mtp5-s$n-$STAMP
  [ -e "$O" ] && O=$O-$(date +%H%M)
  MU_MODE=longsweep MU_PURE=1 MU_HEAD_ROWS=4 MU_FA_PER_SEQ=1 MU_MTP=1 MU_SEQS=$n CAMPAIGN_OUT=$O \
    python3 experiments/qwen38-27b-b70/scripts/run-20261004-fp8-multiuser-campaign.py || break
  [ -f "$O/FAULT-HALT.json" ] && break
  # stop after the first width that is not exact on long prompts
  grep -q 'LONG prompts, pass 1: 64/64' "$O/campaign.log" && grep -q 'LONG prompts, pass 2: 64/64' "$O/campaign.log" || break
done
[ -f "$O/FAULT-HALT.json" ] && exit 4
for n in 64 16; do
  O=/mnt/fast-ai/bench-results/fp8-multiuser-headlocal-s$n-$STAMP
  [ -e "$O" ] && O=$O-$(date +%H%M)
  MU_MODE=longsweep MU_PURE=1 MU_HEAD_ROWS=4 MU_HEAD_AT=head MU_FA_PER_SEQ=1 MU_SEQS=$n CAMPAIGN_OUT=$O \
    python3 experiments/qwen38-27b-b70/scripts/run-20261004-fp8-multiuser-campaign.py || break
  [ -f "$O/FAULT-HALT.json" ] && break
  grep -q 'LONG prompts, pass 1: 64/64' "$O/campaign.log" && grep -q 'LONG prompts, pass 2: 64/64' "$O/campaign.log" || break
done
