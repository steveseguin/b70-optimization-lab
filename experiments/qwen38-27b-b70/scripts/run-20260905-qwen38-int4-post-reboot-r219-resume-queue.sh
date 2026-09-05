#!/usr/bin/env bash
# R219 (2026-09-05): resume the INT4 gptq-relabel queue on a FRESH BOOT after the 01:43:30 xe fault on 0000:03:00.0
# (weight staging of the depth-5 candidate b; same signature as the FP8 lane's 2026-09-04 fault). Sequence:
#   1. R216 chain: depths 5, 3, 2, 1, 6, 7 strict pairs vs the R216 depth-4 MTP0 oracle, then ladders per depth
#   2. R215: TP1 single-card full campaign (depth 4)
#   3. R218: depth-4 ladders in the strict 8-row-chunk mode (r213c image)
# Aborted roots from the faulted boot are removed first (they carry ABORTED markers and root-owned caches).
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts
boot=$(cat /proc/sys/kernel/random/boot_id); [[ "$boot" != "4634e845-e682-457b-815d-15d069e2638a" ]] || { echo "still the faulted boot ($boot); reboot first"; exit 2; }
for r in $out/qwen38-int4-gptq-relabel-r187-stack-mtp{5,3,2,1,6,7}-{strict,ladders}-20260905-r216 $out/qwen38-int4-gptq-relabel-r187-stack-mtp4-tp1-detpad-full-20260905-r215 $out/qwen38-int4-gptq-relabel-r187-stack-mtp4-chunk8-ladders-20260905-r218; do
  [[ -d "$r" ]] && { [[ -f "$r/ABORTED" || ! -f "$r/campaign.log" ]] && sudo rm -rf "$r"; }
done
bash $S/run-20260905-qwen38-int4-gptq-relabel-r216-depth-spectrum-after-r216.sh > $out/logs/r216-chain.log 2>&1
bash $S/run-20260905-qwen38-int4-gptq-relabel-r215-tp1-full-after-r214b.sh > $out/logs/r215-tp1.log 2>&1
bash $S/run-20260905-qwen38-int4-gptq-relabel-r218-chunk8-ladders-after-r215.sh > $out/logs/r218-chunk8-ladders.log 2>&1
