#!/bin/bash
# check-fast.sh <ink_run binary> [card] [baseline dir]:
# Fast single-card exactness screening gate (~60-90 s) for tier-1 variant screening.
# Verifies:
#   1. haiku 64 greedy ids + all 64 logits rows (INK_SAVE_GEN) bit-identical to baseline
#   2. code 128 greedy ids bit-identical to baseline
#   3. DSpark code 128 (INK_SPEC=7) greedy ids bit-identical to baseline
#   4. 3,127-token prompt + 16 greedy tokens logits rows (long16.gen) bit-identical to baseline
#   5. Zero new xe GPU fault lines in kernel journal during the run
# Always run the full check-exact.sh before adopting a winner as default.
set -u
bin=${1:?usage: check-fast.sh <ink_run binary> [card=0] [baseline_dir]}
card=${2:-0}
base=${3:-/home/steve/inkling-work/baseline}
W=/home/steve/inkling-work
M=${INK_MODEL:-/mnt/fast-ai/llm-models/Inkling-2-Mini-GGUF/Inkling-2-Mini-UD-IQ4_XS.gguf}
DR=${INK_DRAFT_MODEL:-/mnt/fast-ai/llm-models/Inkling-2-Mini-GGUF/dspark-Inkling-2-Mini-Q8_0.gguf}
HERE=$(cd "$(dirname "$0")" && pwd)
S="$HERE/on-card.sh"
COMMON="$HERE/../../common"

[ -x "$bin" ] || { echo "check-fast: binary not executable: $bin"; exit 2; }
[ -d "$base" ] || { echo "check-fast: baseline dir missing: $base"; exit 2; }

start_ts=$(date '+%Y-%m-%d %H:%M:%S')
out=$(mktemp -d "$W/fastcheck.XXXXXX")
rc=0

run_check() {
    local label=$1; shift
    if ! "$@"; then
        echo "FAIL $label: command exited non-zero"
        rc=1
    fi
}

run_check "haiku" env INK_SAVE_GEN="$out/haiku.gen" \
    "$S" "$card" "$bin" "$M" "$card" "$W/prompts/haiku.tokens" 64 \
    > "$out/haiku.ids" 2> "$out/haiku.err"

run_check "code" \
    "$S" "$card" "$bin" "$M" "$card" "$W/prompts/code.tokens" 128 \
    > "$out/code.ids" 2> "$out/code.err"

run_check "dspark-code" env INK_DRAFT="$DR" INK_SPEC=7 \
    "$S" "$card" "$bin" "$M" "$card" "$W/prompts/code.tokens" 128 \
    > "$out/dspark-code.ids" 2> "$out/dspark-code.err"

run_check "long16" env INK_SAVE_GEN="$out/long16.gen" \
    "$S" "$card" "$bin" "$M" "$card" "$W/prompts/long.tokens" 16 4200 \
    > "$out/long16.ids" 2> "$out/long16.err"

for n in haiku code; do
    if cmp -s "$base/$n.ids" "$out/$n.ids"; then echo "PASS $n ids"
    else echo "FAIL $n ids differ"; rc=1; fi
done

if [ -f "$base/haiku.gen" ]; then
    if cmp -s "$base/haiku.gen" "$out/haiku.gen"; then echo "PASS haiku 64-step logits bit-identical"
    else echo "FAIL haiku logits differ ($(cmp "$base/haiku.gen" "$out/haiku.gen" | head -1))"; rc=1; fi
fi

if cmp -s "$base/code.ids" "$out/dspark-code.ids"; then
    echo "PASS dspark-code ids ($(grep -h '\[spec\] [0-9]* checks' "$out/dspark-code.err" | cut -d' ' -f2-8 | tr -d '()'))"
else
    echo "FAIL dspark-code ids differ"; rc=1
fi

if [ -f "$base/long16.gen" ]; then
    if cmp -s "$base/long16.gen" "$out/long16.gen"; then echo "PASS long16 3K-prompt logits bit-identical"
    else echo "FAIL long16 logits differ ($(cmp "$base/long16.gen" "$out/long16.gen" | head -1))"; rc=1; fi
fi

grep -h "^error" "$out"/*.err && rc=1

if [ -x "$COMMON/check-journal-faults.sh" ]; then
    "$COMMON/check-journal-faults.sh" "$start_ts" || rc=1
fi

for n in haiku code dspark-code long16; do
    grep -h "generated" "$out/$n.err" | sed "s/^/[$n] /"
done

if [ $rc -eq 0 ] && [ -z "${INK_CHECK_KEEP:-}" ]; then
    rm -rf -- "$out"
    echo "PASS check-fast (card $card; temp dir removed)"
else
    echo "check-fast finished rc=$rc (artifacts in $out)"
fi
exit $rc
