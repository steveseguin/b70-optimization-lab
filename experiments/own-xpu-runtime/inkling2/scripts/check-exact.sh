#!/bin/bash
# check-exact.sh <ink_run binary> [baseline dir]: the exactness gate for an engine change, four cards in parallel.
#   card A: the 5-token prompt with INK_DUMP; every dumped tensor must equal the baseline's bit for bit
#   card B: greedy 64 tokens of prompts/haiku; card C: greedy 128 tokens of prompts/code; ids must equal the baseline's
#   card D: the 300-token prompt (prompts/p300 = first 300 tokens of prompts/long) with INK_DUMP: one step of 300
#     tokens, so the token-parallel expert kernels run (steps >= 128 tokens); every tensor must equal the baseline's
#     (made with INK_TILE_MIN=100000, i.e. the grouped kernels)
# Prints PASS or FAIL lines and the writing speed. Cards: INK_CHECK_CARDS (default "1 2 3 4").
set -u
bin=$1
base=${2:-/home/steve/inkling-work/baseline}
W=/home/steve/inkling-work
M=${INK_MODEL:-/mnt/fast-ai/llm-models/Inkling-2-Mini-GGUF/Inkling-2-Mini-UD-IQ4_XS.gguf}
S=$(cd "$(dirname "$0")" && pwd)/on-card.sh
read -r cA cB cC cD <<< "${INK_CHECK_CARDS:-1 2 3 4}"
out=$(mktemp -d "$W/check.XXXXXX")
mkdir -p "$out/s5" "$out/p300"
INK_DUMP=$out/p300 "$S" "$cD" "$bin" "$M" "$cD" "$W/prompts/p300.tokens" 1 > /dev/null 2> "$out/p300.err" &
INK_DUMP=$out/s5 "$S" "$cA" "$bin" "$M" "$cA" "$W/ref-dumps/smoke5.tokens" 1 > /dev/null 2> "$out/s5.err" &
"$S" "$cB" "$bin" "$M" "$cB" "$W/prompts/haiku.tokens" 64 > "$out/haiku.ids" 2> "$out/haiku.err" &
"$S" "$cC" "$bin" "$M" "$cC" "$W/prompts/code.tokens" 128 > "$out/code.ids" 2> "$out/code.err" &
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
fi
for n in haiku code; do grep -h "generated" "$out/$n.err" | sed "s/^/$n: /"; done
grep -h "^error" "$out"/*.err && rc=1
echo "results in $out"
exit $rc
