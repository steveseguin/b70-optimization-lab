#!/bin/bash
# two-card-run.sh <ink_run binary> <cardA> <cardB> <out dir> [stages]: the model split over two cards (INK_SPLIT=25,
# applications 0-24 on cardA, 25-47 on cardB: the halves' times balance best there, notes/2026-11-26-two-card-1m-plan.md; rows through host memory, no card-to-card reads), one unattended run.
# More cards: INK_RUN_CARDS="1 2 3 4" INK_RUN_SPLIT=12,24,36 (one cut per card after the first; cardA / cardB are
# then ignored, the last card of the list runs the last part, the drafter and the one-card comparisons).
# Stages (default "gate speed needle"):
#   gate:   the gate's checks a split supports, against the baselines (haiku 64 logits rows, code 128 ids, 16 rows
#           after the 3,127-token prompt in one pipelined pass and in steps of 1,024, drafter haiku rows / code ids)
#   speed:  100K and 200K prompts (n100k, n200k), each in both orders against one engine on cardB (same ids)
#   needle: the 1,042,081-token needle (prompts/needle1m.tokens), context 1,048,576, plain writing
# Stops at the first card fault line in the kernel log (Fault response, CAT error, engine reset, GuC, coredump).
set -u
bin=$1; cA=$2; cB=$3; out=$4; stages=${5:-gate speed needle}
cards=${INK_RUN_CARDS:-$cA $cB}; cuts=${INK_RUN_SPLIT:-25}
read -r -a cl <<< "$cards"
cB=${cl[-1]}; before=$(echo "${cl[@]:0:${#cl[@]}-1}" | tr ' ' ',')
[ $(( ${#cl[@]} - 1 )) -eq $(echo "$cuts" | tr ',' ' ' | wc -w) ] || { echo "two-card-run: ${#cl[@]} cards need $(( ${#cl[@]} - 1 )) cut(s) in INK_RUN_SPLIT"; exit 2; }
W=/home/steve/inkling-work
M=${INK_MODEL:-/mnt/fast-ai/llm-models/Inkling-2-Mini-GGUF/Inkling-2-Mini-UD-IQ4_XS.gguf}
DR=${INK_DRAFT_MODEL:-/mnt/fast-ai/llm-models/Inkling-2-Mini-GGUF/dspark-Inkling-2-Mini-Q8_0.gguf}
base=${INK_BASE:-$W/baseline}
OC=$(cd "$(dirname "$0")" && pwd)/on-card.sh
mkdir -p "$out"
t0=$(date '+%Y-%m-%d %H:%M:%S')
log() { echo "$(date +%T) $*" | tee -a "$out/run.txt"; }
faults() { journalctl -k --since "$t0" -o cat 2>/dev/null | grep -E "Fault response|CAT error|engine reset|GuC.*(fail|crash|reset)|devcoredump" | head -3; }
check_faults() { local f; f=$(faults); if [ -n "$f" ]; then log "FAULT LINES, stopping: $f"; exit 3; fi; }
# (on-card.sh takes every card's lock for each split run: INK_SPLIT with INK_SPLIT_CARDS)
split() { INK_SPLIT=$cuts INK_SPLIT_CARDS=$before "$OC" "$cB" "$bin" "$M" "$cB" "$@"; }
one() { "$OC" "$cB" "$bin" "$M" "$cB" "$@"; }
log "start: $bin, cards $cards (split at $cuts), stages: $stages"
for st in $stages; do
case $st in
gate)
    INK_SAVE_GEN=$out/haiku.gen split $W/prompts/haiku.tokens 64 > $out/haiku.ids 2> $out/haiku.err
    cmp -s $out/haiku.gen $base/haiku.gen && cmp -s $out/haiku.ids $base/haiku.ids && log "PASS haiku: 64 logits rows identical" || log "FAIL haiku"
    check_faults
    split $W/prompts/code.tokens 128 > $out/code.ids 2> $out/code.err
    cmp -s $out/code.ids $base/code.ids && log "PASS code: ids identical" || log "FAIL code"
    INK_SAVE_GEN=$out/long16.gen split $W/prompts/long.tokens 16 4200 > $out/long16.ids 2> $out/long16.err
    cmp -s $out/long16.gen $base/long16.gen && log "PASS long: 16 rows identical (one step)" || log "FAIL long"
    INK_UBATCH=1024 INK_SAVE_GEN=$out/long16p.gen split $W/prompts/long.tokens 16 4200 > $out/long16p.ids 2> $out/long16p.err
    cmp -s $out/long16p.gen $base/long16.gen && log "PASS long pipelined: 16 rows identical ($(grep -h 'prompt 3127' $out/long16p.err | sed 's/.*prompt/prompt/'))" || log "FAIL long pipelined"
    INK_DRAFT=$DR INK_SPEC=7 INK_SPEC_ADAPT=0 INK_DSP_STOP=0 INK_SAVE_GEN=$out/dspark-haiku.gen split $W/prompts/haiku.tokens 64 > $out/dspark-haiku.ids 2> $out/dspark-haiku.err
    cmp -s $out/dspark-haiku.gen $base/haiku.gen && cmp -s $out/dspark-haiku.ids $base/haiku.ids && log "PASS drafter haiku: ids and chosen rows identical" || log "FAIL drafter haiku"
    INK_DRAFT=$DR INK_SPEC=7 split $W/prompts/code.tokens 128 > $out/dspark-code.ids 2> $out/dspark-code.err
    cmp -s $out/dspark-code.ids $base/code.ids && log "PASS drafter code: ids identical ($(grep -h 'generated' $out/dspark-code.err | sed 's/.*generated/generated/'))" || log "FAIL drafter code"
    for f in haiku code; do log "$f: $(grep -h 'generated' $out/$f.err | sed 's/.*generated/generated/')"; done
    check_faults ;;
speed)
    for p in n100k n200k; do
        for o in split one one split; do
            if [ $o = split ]; then split $W/prompts/$p.tokens 1 > $out/$p-$o.ids 2> $out/$p-$o.err
            else one $W/prompts/$p.tokens 1 > $out/$p-$o.ids 2> $out/$p-$o.err; fi
            log "$p $o: $(grep -h '\[ink\] prompt' $out/$p-$o.err | sed 's/.*prompt/prompt/') ids $(md5sum < $out/$p-$o.ids | cut -c1-8)"
            check_faults
        done
    done ;;
needle)
    INK_UBATCH=2048 INK_SPEC_LOOKUP=0 split $W/prompts/needle1m.tokens 400 1048576 > $out/needle1m.ids 2> $out/needle1m.err
    log "needle 1M: $(grep -h '\[ink\] prompt' $out/needle1m.err | sed 's/.*prompt/prompt/')"
    log "needle 1M answer: $(/home/steve/inkling-work/venv/bin/python -I "$(dirname "$OC")/../tools/detok.py" "$M" $out/needle1m.ids 2>/dev/null | tail -c 400 | tr '\n' ' ')"
    grep -h "at the end\|split:" $out/needle1m.err | while read -r l; do log "  $l"; done
    check_faults ;;
esac
done
log "done"
