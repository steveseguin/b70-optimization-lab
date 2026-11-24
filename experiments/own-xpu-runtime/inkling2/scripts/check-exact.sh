#!/bin/bash
# check-exact.sh <ink_run binary> [baseline dir]: the exactness gate for an engine change, four cards in parallel.
#   card A: the 5-token prompt with INK_DUMP; every dumped tensor must equal the baseline's bit for bit
#   card B: greedy 64 tokens of prompts/haiku; card C: greedy 128 tokens of prompts/code; ids must equal the baseline's,
#     and card B's logits rows of all 64 steps (INK_SAVE_GEN: the one-token path) must equal the baseline's bit for bit
#   card D: the 300-token prompt (prompts/p300 = first 300 tokens of prompts/long) with INK_DUMP: one step of 300
#     tokens, so the token-parallel expert kernels run (steps >= 128 tokens); every tensor must equal the baseline's
#     (made with INK_TILE_MIN=100000, i.e. the grouped kernels)
#   card E: the 3127-token prompt (prompts/long) and 16 greedy tokens (context 4200): the logits rows of all 16 steps
#     (INK_SAVE_GEN) must equal the baseline's bit for bit (long context: windowed and full attention past 1024 keys);
#     then the same with the drafter's guesses and the checks' shared key reads at any length (INK_ATT_SHARE_MIN=0)
#   card A, then: haiku 64 and code 128 with guesses checked in steps of 2-4 tokens (INK_SPEC=3, prompt lookup):
#     ids and every chosen logits row must equal the one-token baseline's; then haiku 64 with the DSpark drafter's
#     guesses (INK_DRAFT, INK_SPEC=3): ids and every chosen logits row
# Prints PASS or FAIL lines and the writing speed. Cards: INK_CHECK_CARDS (default "1 2 3 4 5"). The results folder
# (~1.2 GB) is removed when everything passes, kept on a failure.
set -u
bin=$1
base=${2:-/home/steve/inkling-work/baseline}
W=/home/steve/inkling-work
M=${INK_MODEL:-/mnt/fast-ai/llm-models/Inkling-2-Mini-GGUF/Inkling-2-Mini-UD-IQ4_XS.gguf}
DR=${INK_DRAFT_MODEL:-/mnt/fast-ai/llm-models/Inkling-2-Mini-GGUF/dspark-Inkling-2-Mini-Q8_0.gguf}
S=$(cd "$(dirname "$0")" && pwd)/on-card.sh
read -r cA cB cC cD cE <<< "${INK_CHECK_CARDS:-1 2 3 4 5}"
# five distinct cards (a missing one would run its checks on card 0)
[ -n "$cE" ] && [ $(printf '%s\n' $cA $cB $cC $cD $cE | sort -u | wc -l) -eq 5 ] || { echo "check-exact: INK_CHECK_CARDS needs five distinct cards"; exit 2; }
out=$(mktemp -d "$W/check.XXXXXX")
mkdir -p "$out/s5" "$out/p300"
INK_DUMP=$out/p300 "$S" "$cD" "$bin" "$M" "$cD" "$W/prompts/p300.tokens" 1 > /dev/null 2> "$out/p300.err" &
{ INK_DUMP=$out/s5 "$S" "$cA" "$bin" "$M" "$cA" "$W/ref-dumps/smoke5.tokens" 1 > /dev/null 2> "$out/s5.err"
  INK_SPEC=3 INK_SAVE_GEN=$out/spec-haiku.gen "$S" "$cA" "$bin" "$M" "$cA" "$W/prompts/haiku.tokens" 64 > "$out/spec-haiku.ids" 2> "$out/spec-haiku.err"
  INK_SPEC=3 "$S" "$cA" "$bin" "$M" "$cA" "$W/prompts/code.tokens" 128 > "$out/spec-code.ids" 2> "$out/spec-code.err"
  INK_DRAFT=$DR INK_SPEC=3 INK_SAVE_GEN=$out/dspark-haiku.gen "$S" "$cA" "$bin" "$M" "$cA" "$W/prompts/haiku.tokens" 64 > "$out/dspark-haiku.ids" 2> "$out/dspark-haiku.err"; } &
INK_SAVE_GEN=$out/haiku.gen "$S" "$cB" "$bin" "$M" "$cB" "$W/prompts/haiku.tokens" 64 > "$out/haiku.ids" 2> "$out/haiku.err" &
"$S" "$cC" "$bin" "$M" "$cC" "$W/prompts/code.tokens" 128 > "$out/code.ids" 2> "$out/code.err" &
{ INK_SAVE_GEN=$out/long16.gen "$S" "$cE" "$bin" "$M" "$cE" "$W/prompts/long.tokens" 16 4200 > "$out/long16.ids" 2> "$out/long16.err"
  INK_ATT_SHARE_MIN=0 INK_DRAFT=$DR INK_SPEC=3 INK_SAVE_GEN=$out/dspark-long16.gen "$S" "$cE" "$bin" "$M" "$cE" "$W/prompts/long.tokens" 16 4200 > "$out/dspark-long16.ids" 2> "$out/dspark-long16.err"; } &
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
        if cmp -s "$base/long16.gen" "$out/dspark-long16.gen" && cmp -s "$base/long16.ids" "$out/dspark-long16.ids"; then
            echo "PASS dspark long: checks after 3127 tokens with shared key reads, ids and every chosen row identical ($(grep -h '\[spec\] [0-9]* checks' "$out/dspark-long16.err" | cut -d' ' -f2-8 | tr -d '()'))"
        else echo "FAIL dspark long: ids or chosen rows differ"; rc=1; fi
    fi
    for n in haiku code; do
        if cmp -s "$base/$n.ids" "$out/spec-$n.ids"; then echo "PASS spec $n: ids identical ($(grep -h '\[spec\]' "$out/spec-$n.err" | cut -d' ' -f2-8 | tr -d '()'))"
        else echo "FAIL spec $n: ids differ"; rc=1; fi
    done
    if cmp -s "$base/haiku.ids" "$out/dspark-haiku.ids" && cmp -s "$base/haiku.gen" "$out/dspark-haiku.gen"; then
        echo "PASS dspark haiku: ids and every chosen logits row identical ($(grep -h '\[spec\] [0-9]* checks' "$out/dspark-haiku.err" | cut -d' ' -f2-8 | tr -d '()'))"
    else echo "FAIL dspark haiku: ids or chosen logits rows differ"; rc=1; fi
    if [ -f "$base/haiku.gen" ]; then
        if cmp -s "$base/haiku.gen" "$out/spec-haiku.gen"; then echo "PASS spec haiku: every chosen logits row bit-identical"
        else echo "FAIL spec haiku: chosen logits rows differ ($(cmp "$base/haiku.gen" "$out/spec-haiku.gen" | head -1))"; rc=1; fi
    fi
    if [ -f "$base/haiku.gen" ]; then
        if cmp -s "$base/haiku.gen" "$out/haiku.gen"; then echo "PASS haiku: logits rows of all 64 steps bit-identical ($(stat -c %s "$out/haiku.gen") bytes)"
        else echo "FAIL haiku: step logits differ ($(cmp "$base/haiku.gen" "$out/haiku.gen" | head -1))"; rc=1; fi
    fi
fi
for n in haiku code; do grep -h "generated" "$out/$n.err" | sed "s/^/$n: /"; done
grep -h "^error" "$out"/*.err && rc=1
if [ $rc -eq 0 ] && [ -z "${INK_CHECK_KEEP:-}" ]; then rm -rf -- "$out"; echo "all passed (results removed; INK_CHECK_KEEP=1 keeps them)"
else echo "results in $out"; fi
exit $rc
