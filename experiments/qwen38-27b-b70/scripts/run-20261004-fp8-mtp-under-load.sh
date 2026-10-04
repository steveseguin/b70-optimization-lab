#!/usr/bin/env bash
# Two preregistered tests (notes/2026-10-04-fp8-multiuser-prereg.md, 06:30 and 06:40 EDT addenda):
#  1. Speculation under load: shipped depth-5 MTP plus the three exactness overlays,
#     4 users, then 8 if 4 is exact on long prompts.
#  2. One logits exchange per step (B70_LM_HEAD_CHUNK_AT=head), speculation off, 64 users then 16.
#
# The first attempt faulted at weight load (notes/2026-10-04-gpu-fault-mtp-start.md),
# the second fault on that boot, so this refuses to run on that boot or on any
# boot whose kernel log already has a GPU fault line. Run it in its own unit:
#   systemd-run --user --unit fp8-mtp-under-load --collect \
#     bash experiments/qwen38-27b-b70/scripts/run-20261004-fp8-mtp-under-load.sh
# It leaves no server running.
set -u
cd "$(dirname "$0")/../../.." || exit 2
FAULTED_BOOT=66541315-49f1-41f7-af1d-4756d6b89c9c
if [ "$(cat /proc/sys/kernel/random/boot_id)" = "$FAULTED_BOOT" ]; then
  echo "refusing: still on the boot that faulted twice; a reboot is needed first" >&2; exit 3
fi
if journalctl -k -b --no-pager | grep -qE 'xe 0000:.*(Fault response|Engine memory CAT error|Timedout job|device coredump)'; then
  echo "refusing: this boot's kernel log already has a GPU fault line" >&2; exit 3
fi
STAMP=${STAMP:-$(date +%Y%m%d)}
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
