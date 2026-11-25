#!/bin/bash
# make-baseline.sh <ink_run binary> <new baseline dir>: the reference results for check-exact.sh, made through the
# engine's alternative paths so that check-exact (default paths) also proves the paths agree bit for bit:
#   s5     5-token prompt dumps (writing-step kernels throughout)
#   p300   300-token step dumps with the grouped expert kernels (INK_TILE_MIN=100000) and the general attention
#          kernels (INK_ATT_TILE=0) instead of the tiles
#   haiku  64 tokens: prompt through the general attention kernels, every step through the general scores and
#          normalizing softmax (INK_DEC_ATTN=0) and the separate projections (INK_MULTI=0); ids + all step logits
#   code   128 tokens, general prompt attention; ids
#   long16 3,127-token prompt (general attention kernels) in steps of 8 tokens (INK_UBATCH=8: the writing-size
#          kernels, where check-exact reads it in one step) + 16 steps (INK_DEC_ATTN=0), context 4200; all step logits
# Cards: INK_CHECK_CARDS (default "1 2 3 4 5"), as check-exact.sh.
set -eu
bin=$1
base=$2
W=/home/steve/inkling-work
M=${INK_MODEL:-/mnt/fast-ai/llm-models/Inkling-2-Mini-GGUF/Inkling-2-Mini-UD-IQ4_XS.gguf}
S=$(cd "$(dirname "$0")" && pwd)/on-card.sh
read -r cA cB cC cD cE <<< "${INK_CHECK_CARDS:-1 2 3 4 5}"
[ -e "$base" ] && { echo "make-baseline: $base exists"; exit 2; }
mkdir -p "$base/s5" "$base/p300"
INK_TILE_MIN=100000 INK_ATT_TILE=0 INK_DUMP=$base/p300 "$S" "$cD" "$bin" "$M" "$cD" "$W/prompts/p300.tokens" 1 > /dev/null 2> "$base/p300.err" &
INK_DUMP=$base/s5 "$S" "$cA" "$bin" "$M" "$cA" "$W/ref-dumps/smoke5.tokens" 1 > /dev/null 2> "$base/s5.err" &
INK_ATT_TILE=0 INK_DEC_ATTN=0 INK_MULTI=0 INK_SAVE_GEN=$base/haiku.gen "$S" "$cB" "$bin" "$M" "$cB" "$W/prompts/haiku.tokens" 64 > "$base/haiku.ids" 2> "$base/haiku.err" &
INK_ATT_TILE=0 "$S" "$cC" "$bin" "$M" "$cC" "$W/prompts/code.tokens" 128 > "$base/code.ids" 2> "$base/code.err" &
INK_UBATCH=8 INK_ATT_TILE=0 INK_DEC_ATTN=0 INK_SAVE_GEN=$base/long16.gen "$S" "$cE" "$bin" "$M" "$cE" "$W/prompts/long.tokens" 16 4200 > "$base/long16.ids" 2> "$base/long16.err" &
wait
grep -h "^error" "$base"/*.err && exit 1
echo "baseline made in $base with $bin"
