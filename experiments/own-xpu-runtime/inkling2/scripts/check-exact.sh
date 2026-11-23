#!/bin/bash
# check-exact.sh <ink_run binary> [baseline dir]: the exactness gate for an engine change, four cards in parallel.
#   card A: the 5-token prompt with INK_DUMP; every dumped tensor must equal the baseline's bit for bit
#   card B: greedy 64 tokens of prompts/haiku; card C: greedy 128 tokens of prompts/code; ids must equal the baseline's,
#     and card B's logits rows of all 64 steps (INK_SAVE_GEN: the one-token path) must equal the baseline's bit for bit
#   card D: the 300-token prompt (prompts/p300 = first 300 tokens of prompts/long) with INK_DUMP: one step of 300
#     tokens, so the token-parallel expert kernels run (steps >= 128 tokens); every tensor must equal the baseline's
#     (made with INK_TILE_MIN=100000, i.e. the grouped kernels)
#   card E: the 3127-token prompt (prompts/long) and 16 greedy tokens (context 4200): the logits rows of all 16 steps
#     (INK_SAVE_GEN) must equal the baseline's bit for bit (long context: windowed and full attention past 1024 keys)
# Prints PASS or FAIL lines and the writing speed. Cards: INK_CHECK_CARDS (default "1 2 3 4 5").
set -u
bin=$1
base=${2:-/home/steve/inkling-work/baseline}
W=/home/steve/inkling-work
M=${INK_MODEL:-/mnt/fast-ai/llm-models/Inkling-2-Mini-GGUF/Inkling-2-Mini-UD-IQ4_XS.gguf}
S=$(cd "$(dirname "$0")" && pwd)/on-card.sh
read -r cA cB cC cD cE <<< "${INK_CHECK_CARDS:-1 2 3 4 5}"
out=$(mktemp -d "$W/check.XXXXXX")
mkdir -p "$out/s5" "$out/p300"
INK_DUMP=$out/p300 "$S" "$cD" "$bin" "$M" "$cD" "$W/prompts/p300.tokens" 1 > /dev/null 2> "$out/p300.err" &
INK_DUMP=$out/s5 "$S" "$cA" "$bin" "$M" "$cA" "$W/ref-dumps/smoke5.tokens" 1 > /dev/null 2> "$out/s5.err" &
INK_SAVE_GEN=$out/haiku.gen "$S" "$cB" "$bin" "$M" "$cB" "$W/prompts/haiku.tokens" 64 > "$out/haiku.ids" 2> "$out/haiku.err" &
"$S" "$cC" "$bin" "$M" "$cC" "$W/prompts/code.tokens" 128 > "$out/code.ids" 2> "$out/code.err" &
INK_SAVE_GEN=$out/long16.gen "$S" "$cE" "$bin" "$M" "$cE" "$W/prompts/long.tokens" 16 4200 > "$out/long16.ids" 2> "$out/long16.err" &
wait
rc=0
if [ ! -d "$base" ]; then
    mkdir -p "$base" && cp -r "$out/s5" "$base/s5" && cp "$out/haiku.ids" "$out/code.ids" "$base/" && echo "baseline created in $base"
else
    for dd in s5 p300; do
    "$W/venv/bin/python" -I - "$base/$dd" "$out/$dd" "$dd" <<'PY' || rc=1
import sys
a, b, tag = sys.argv[1], sys.argv[2], sys.argv[3]
names = [l.split('\t')[0] for l in open(a + '/index.tsv')]
try:
    diff = [n for n in names if open(f'{a}/{n}.f32', 'rb').read() != open(f'{b}/{n}.f32', 'rb').read()]
except FileNotFoundError as e:
    print(f'FAIL dumps {tag}: missing', e.filename); sys.exit(1)
print(('PASS' if not diff else 'FAIL') + f' dumps {tag}: {len(names) - len(diff)} of {len(names)} tensors bit-identical' + (f'; first differing {diff[:3]}' if diff else ''))
sys.exit(1 if diff else 0)
PY
    done
    for n in haiku code; do
        if cmp -s "$base/$n.ids" "$out/$n.ids"; then echo "PASS $n: ids identical"; else echo "FAIL $n: ids differ"; rc=1; fi
    done
    if [ -f "$base/long16.gen" ]; then
        if cmp -s "$base/long16.gen" "$out/long16.gen"; then echo "PASS long: logits rows of all 16 steps after 3127 tokens bit-identical"
        else echo "FAIL long: step logits differ ($(cmp "$base/long16.gen" "$out/long16.gen" | head -1))"; rc=1; fi
    fi
    if [ -f "$base/haiku.gen" ]; then
        if cmp -s "$base/haiku.gen" "$out/haiku.gen"; then echo "PASS haiku: logits rows of all 64 steps bit-identical ($(stat -c %s "$out/haiku.gen") bytes)"
        else echo "FAIL haiku: step logits differ ($(cmp "$base/haiku.gen" "$out/haiku.gen" | head -1))"; rc=1; fi
    fi
fi
for n in haiku code; do grep -h "generated" "$out/$n.err" | sed "s/^/$n: /"; done
grep -h "^error" "$out"/*.err && rc=1
echo "results in $out"
exit $rc
