#!/bin/bash
# two-card-run.sh <ink_run binary> <cardA> <cardB> <out dir> [stages]: the model split over two cards (INK_SPLIT=25,
# applications 0-24 on cardA, 25-47 on cardB: the halves' times balance best there, notes/2026-11-26-two-card-1m-plan.md; rows through host memory, no card-to-card reads), one unattended run.
# More cards: INK_RUN_CARDS="1 2 3 4" INK_RUN_SPLIT=12,24,36 (one cut per card after the first; cardA / cardB are
# then ignored, the last card of the list runs the last part, the drafter and the one-card comparisons).
# Stages (default "gate speed shard needle"):
#   gate:   the gate's checks a split supports, against the baselines (haiku 64 logits rows, code 128 ids, 16 rows
#           after the 3,127-token prompt in one pipelined pass and in steps of 1,024, drafter haiku rows / code ids)
#   speed:  100K and 200K prompts (n100k, n200k), each in both orders against one engine on cardB (same ids)
#   shard:  writing 128 tokens after the 200K prompt (read once and saved, then loaded) with the caches shared between
#           the cards and without, both orders: copies (INK_SHARD_COPY, ~200K / cards positions per card), and with two
#           cards also moved (INK_SHARD=98304); logits rows of all 128 steps identical, writing speed
#   needle: the 1,042,081-token needle (prompts/needle1m.tokens), context 1,048,576, plain writing, the first 200
#           tokens with the caches shared (two cards: moved, INK_SHARD=524288; more: copies of ~1M / cards each), the
#           rest without
# Stops at the first card fault line in the kernel log (Fault response, CAT error, engine reset, GuC, coredump).
set -u
bin=$1; cA=$2; cB=$3; out=$4; stages=${5:-gate speed shard needle}
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
rc=0
log() { echo "$(date +%T) $*" | tee -a "$out/run.txt"; case "$*" in FAIL*) rc=1 ;; esac; }
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
        want=
        for o in split one one split; do
            if [ $o = split ]; then split $W/prompts/$p.tokens 1 > $out/$p-$o.ids 2> $out/$p-$o.err
            else one $W/prompts/$p.tokens 1 > $out/$p-$o.ids 2> $out/$p-$o.err; fi
            got=$(md5sum < $out/$p-$o.ids | cut -c1-8)
            if [ -z "$want" ]; then want=$got; fi
            if [ "$got" != "$want" ]; then log "FAIL $p $o: ids differ from the first arm"; fi
            log "$p $o: $(grep -h '\[ink\] prompt' $out/$p-$o.err | sed 's/.*prompt/prompt/') ids $got"
            check_faults
        done
    done ;;
shard)
    nc=${#cl[@]}; F=/mnt/fast-ai/inkling-cache/tests/two-card-run-s200k.inkc
    sc=$(( (200001 / nc + 8192) / 16384 * 16384 ))
    if [ $nc -eq 2 ]; then orders="plain move copy copy move plain"; else orders="plain copy copy plain"; fi
    INK_SAVE_CACHE=$F INK_SPEC_LOOKUP=0 INK_SAVE_GEN=$out/s200k-read.gen split $W/prompts/n200k.tokens 128 > $out/s200k-read.ids 2> $out/s200k-read.err
    log "200K read and saved: $(grep -h '\[ink\] prompt' $out/s200k-read.err | sed 's/.*prompt/prompt/')"
    check_faults
    for o in $orders; do
        # (a subshell exports the settings: split is this script's function, which env cannot run)
        ( export INK_LOAD_CACHE=$F
          case $o in move) export INK_SHARD=98304 ;; copy) export INK_SHARD_COPY=$sc ;; esac
          INK_SPEC_LOOKUP=0 INK_SAVE_GEN=$out/s200k-$o.gen split $W/prompts/n200k.tokens 128 > $out/s200k-$o.ids 2> $out/s200k-$o.err )
        log "200K writing, $o: $(grep -h 'generated' $out/s200k-$o.err | sed 's/.*generated/generated/') $(grep -h 'shard:' $out/s200k-$o.err | sed 's/.*shard://')"
        check_faults
    done
    for o in $orders; do cmp -s $out/s200k-read.gen $out/s200k-$o.gen || log "FAIL shard: $o rows differ"; done
    log "shard: all 128 logits rows of every run compared with the read run (FAIL lines above if any)"
    rm -f $F ;;
needle)
    ( if [ ${#cl[@]} -eq 2 ]; then export INK_SHARD=524288 INK_SHARD_END=200
      else export INK_SHARD_COPY=$(( (1042081 / ${#cl[@]} + 8192) / 16384 * 16384 )) INK_SHARD_END=200; fi
      INK_UBATCH=2048 INK_SPEC_LOOKUP=0 split $W/prompts/needle1m.tokens 400 1048576 > $out/needle1m.ids 2> $out/needle1m.err )
    grep -h "shard:" $out/needle1m.err | while read -r l; do log "  $l"; done
    log "needle 1M: $(grep -h '\[ink\] prompt' $out/needle1m.err | sed 's/.*prompt/prompt/')"
    ans=$(/home/steve/inkling-work/venv/bin/python -I "$(dirname "$OC")/../tools/detok.py" "$M" $out/needle1m.ids 2>/dev/null | tail -c 400 | tr '\n' ' ')
    log "needle 1M answer: $ans"
    if [[ "$ans" == *7351-QX-4829* && "$ans" == *Juniper-12* ]]; then log "PASS needle: both hidden answers"
    else log "FAIL needle: missing a hidden answer"; fi
    grep -h "at the end\|split:" $out/needle1m.err | while read -r l; do log "  $l"; done
    check_faults ;;
esac
done
log "done"
exit "$rc"
