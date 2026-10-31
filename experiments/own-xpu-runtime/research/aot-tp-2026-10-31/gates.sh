#!/usr/bin/env bash
# The exactness gate of research/aot-tp-2026-10-31: arm lists and compare pairs (the launch and compare commands used).
# Usage: gates.sh launch-g1 | launch-g2 | compare-g1 | compare-g2   (JIT/AOT binaries from JIT_BIN / AOT_BIN)
# g1: one card (0000:43:00.0, lock card43), both ranks, every configuration once with the JIT r1 binary and once with the
#     AOT binary, in one phase. Two flag sets:
#   "4"  the four-card stack's flags as its one-card references ran them (hc-split-2026-10-30 g1): rd,hk=1,tf=1 (+ df=1 on
#        rank 0), plus ph,db for the batched two-request arms;
#   "B"  research/two-card-flags-2026-10-31/flags.py B (the two-card servers' set; two-card-flags g1 arms).
#   Rank 1: token by token (128 prompt rows + 64 halves, exports) and batched + RESET + second request.
#   Rank 0: h, hmcn, m (64 speculative steps with drafts) and batched + RESET + second request (dc for B, as its g1).
# g2: four cards, AOT only, the hsp flags (fc2 + OWNRT_TP_HC_SPLIT=low,gate,final,prefill): rank 1 on 23+47, rank 0 on
#     23+27, token by token and batched + second request; compared against the one-card g1 runs (both binaries) and the
#     archived JIT TP runs of hc-split-2026-10-30 g2 with the same flags (g2-r1-onp-b, g2-r0-onp-db).
set -eu
D=$(cd "$(dirname "$0")" && pwd)
JIT=${JIT_BIN:-/dev/shm/hcsplit-2026-10-30/build-r1/sc117-engine}
AOT=${AOT_BIN:-/dev/shm/aot-tp-2026-10-31/build-aot-r1/sc117-engine}
RUNS=/dev/shm/aot-tp-2026-10-31/runs
HC=/mnt/raid-models/ownrt-experiment-archives/2026-10-30/hc-split-gates-runs
g1() {
  for b in jit aot; do B=${b:0:1}; B=${B^^}
    echo "g1-r1-4$B:1:one:64:128:h:rd,hk=1,tf=1,$b"
    echo "g1-r1-4b$B:1:one:64:128:h:rd,hk=1,tf=1,ph,db,batched,sp=64,$b"
    echo "g1-r1-B$B:1:one:64:128:h:B,$b"
    echo "g1-r1-Bb$B:1:one:64:600:h:B,batched,sp=600,$b"
  done
  for b in jit aot; do B=${b:0:1}; B=${B^^}
    echo "g1-r0-4$B:0:one:64:128:h:rd,hk=1,df=1,tf=1,$b"
    echo "g1-r0-4hmcn$B:0:one:64:128:hmcn:rd,hk=1,df=1,tf=1,$b"
    echo "g1-r0-4m$B:0:one:64:128:m:rd,hk=1,df=1,tf=1,$b"
    echo "g1-r0-4b$B:0:one:64:128:h:rd,hk=1,ph,batched,dc,db,df=1,tf=1,sp=64,$b"
    echo "g1-r0-B$B:0:one:64:128:h:B,$b"
    echo "g1-r0-Bhmcn$B:0:one:64:128:hmcn:B,$b"
    echo "g1-r0-Bm$B:0:one:64:128:m:B,$b"
    echo "g1-r0-Bb$B:0:one:64:600:hmcn:B,batched,dc,sp=600,$b"
  done
}
g2() {
  echo "g2-r1-tA:1:full:64:128:h:ep,rd,hk=1,tf=1,hs=low+gate+final+prefill,aot"
  echo "g2-r1-tbA:1:full:64:128:h:ep,rd,hk=1,tf=1,ph,db,batched,sp=64,hs=low+gate+final+prefill,aot"
  echo "g2-r0-tA:0:full:64:128:h:ep,rd,hk=1,df=1,tf=1,hs=low+gate+final+prefill,aot"
  echo "g2-r0-tbA:0:full:64:128:h:ep,rd,hk=1,df=1,tf=1,ph,batched,dc,db,sp=64,hs=low+gate+final+prefill,aot"
}
case "$1" in
  launch-g1) TC_BDF=0000:43:00.0 LOCKS=43 bash "$D/launch_phase.sh" "$JIT" "$AOT" g1 $(g1) ;;
  launch-g2) TC_BDF=0000:43:00.0 LOCKS="23 27 47" bash "$D/launch_phase.sh" "$JIT" "$AOT" g2 $(g2) ;;
  compare-g1)  # JIT vs AOT, every configuration (state, tokens, drafts, exports, second request, inventories, ones)
    pairs=(); for c in 4 4b B Bb; do pairs+=("1:g1-r1-${c}J:g1-r1-${c}A"); done
    for c in 4 4hmcn 4m 4b B Bhmcn Bm Bb; do pairs+=("0:g1-r0-${c}J:g1-r0-${c}A"); done
    bash "$D/compare.sh" g1 "$RUNS" "${pairs[@]}" ;;
  compare-g2)  # four-card AOT vs one card (both binaries); batched TP vs the archived JIT TP runs (same flags)
    bash "$D/compare.sh" g2 "$RUNS" 1:g1-r1-4A:g2-r1-tA 1:g1-r1-4J:g2-r1-tA 0:g1-r0-4A:g2-r0-tA 0:g1-r0-4J:g2-r0-tA \
      1:g1-r1-4bA:g2-r1-tbA 1:g1-r1-4bJ:g2-r1-tbA 0:g1-r0-4bA:g2-r0-tbA 0:g1-r0-4bJ:g2-r0-tbA \
      "1:$HC/g2-r1-onp-b:g2-r1-tbA" "0:$HC/g2-r0-onp-db:g2-r0-tbA" ;;
  compare-g1x)  # AOT vs the archived JIT runs of the same configurations (other cards: hc-split g1 on 43, two-card g1 on 47)
    TC=/mnt/raid-models/ownrt-experiment-archives/2026-10-31/two-card-flags-gates-runs
    bash "$D/compare.sh" g1x "$RUNS" "1:$HC/g1-r1-one:g1-r1-4A" "1:$HC/g1-r1-one-b:g1-r1-4bA" "0:$HC/g1-r0-one:g1-r0-4A" \
      "0:$HC/g1-r0-one-hmcn:g1-r0-4hmcnA" "0:$HC/g1-r0-one-m:g1-r0-4mA" "0:$HC/g1-r0-one-db:g1-r0-4bA" \
      "1:$TC/g1-r1-B:g1-r1-BA" "1:$TC/g1-r1-B-b:g1-r1-BbA" "0:$TC/g1-r0-B:g1-r0-BA" "0:$TC/g1-r0-B-hmcn:g1-r0-BhmcnA" \
      "0:$TC/g1-r0-B-m:g1-r0-BmA" "0:$TC/g1-r0-B-b:g1-r0-BbA" ;;
  *) echo "usage: $0 launch-g1|launch-g2|compare-g1|compare-g1x|compare-g2"; exit 2 ;;
esac
