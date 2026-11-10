# DeepSeek V4.1 own engine: multi-token step and DSpark drafting, survey and plan (2026-11-09)

Purpose: one step that runs M tokens (M up to ~16) with each token's results bit-identical to the
one-token decode step. It serves two things: reading the prompt in blocks (today one token per step,
~60-69 tok/s with `OWN_TP=6`), and checking the official DSpark draft's 5 guesses in one pass
(target-verified speculative decoding; the output stays exactly the target's greedy answer).

Sources: two read-only code surveys (2026-11-09 22:30-22:50 EST) of our engine
(`engine/src/stage2/packet3/backend/backend_sycl_v41.hpp` = B, `kernels/sycl_v41.hpp` = K,
`planning/dsv41-fixtures/own_run_v41.cpp` = R) and of llama.cpp's DSpark implementation
(`/home/steve/src/llama.cpp-dsv41-20261108`, commit 7d7f02875; read for semantics only, credited here).
Line numbers are from the tree at that time.

## 1. The one-token TP step today (OWN_TP=6, defaults)

Split per card: query heads 8/8/16/8/8/16 (o_a groups 1,1,2,1,1,2), expert mid rows 384 each, model rows
848/848/864/848/848/864, vocab ~21.5K each, engram_kv rows ~4.26K each. q_a, kv, router, stream-mix rows,
norms, compressor and indexer are replicated: every card computes them in full.

Per layer, ~25 launches and 4 exchanges:

- phase 0: (engram at L1/L14) -> pre-norm + stream-mix dots -> q_a + kv pair -> both norms -> q_b (+ mix
  finish + kv rope) -> q rope -> publish (L2/8/14/20) -> index (L2/8/14/20/24/28/32/36)
- phase 1: window append -> score / softmax / output (+ inverse rope) -> o_a -> exchange 1
- phase 2: o_b -> exchange 2
- phase 3: stream post+pre -> FFN norm + dots -> router -> route + shared gate/up -> routed gate+up pair ->
  swiglu -> exchange 3
- phase 4: routed down, shared down, combine -> exchange 4
- phase 5: stream post+pre

Head per step: norm, ~90 MB of Q6_K output rows per card, argmax, host argmax over cards. Engram_kv adds
~43 MB per card per step. A Q8 layer reads ~52 MB per card (18 MB of it replicated).

Every weight-row kernel computes one row per 32-lane sub-group. Lane l covers K = l, l+32, ...;
`sum = sum + v*x` with contraction off; then a fixed tree (`sg_tree32` for dense rows, xor butterfly for
the routed kernels). The dequantized v does not depend on x, so M tokens can share one decode of the
weight block with M accumulators and the same op sequence: bit-identical by construction under
`-fp-model=precise -ffp-contract=off`.

## 2. What a block of M tokens changes

- **Window ring = window size (128).** Appending M rows first overwrites rows earlier block tokens still
  need (K WindowAppendP, B ring alloc). Fix: ring of 128 + M_max rows. The attention reads the window
  oldest-first (positions pos-127..pos) and only the order of valid entries matters for the sums, so a
  larger ring changes no bits. The ring/compressed boundary `win_rows = 128` and the +128 in the index
  lists (CidxFill, TopKSelP add, host index) move to the new ring size.
- **Ratio-2 compressor (layers 2-19).** kv_state/score_state hold 2 slots (pos % 2); an odd position pools
  with the preceding even one. In a block this is just sequential per token; for drafts, a rejected even
  token must not clobber the slot an accepted odd token needs (keep per-position slots or recompute).
- **Compressed rows and indexer views are per token.** Token m sees rows published by tokens <= m
  (ratio 1: every position; ratio 2: odd positions). Short path: CidxFill(len_m). Long path: scores per
  token (IndexerScoreA already has an m dimension), TopKSelP one work-group per token, M lists per index
  slot, the layer-20 candidate mask per token.
- **Routed experts** follow each token's ids: weights are shared only between tokens that chose the same
  expert. First form: 6M slots through the existing slot-indexed kernels (exact, L2 reuse only); later an
  expert-major form that keeps each (token, slot, row) on the same lane chain and tree.
- **Sizes**: Scratch, streams, attention weights, index lists, the exchange arena (offset formula already
  handles nslot; ~5.2 MB per card at M = 16) are single-token today. pos is a by-value functor member in
  WindowAppendP / PubAppendA / rope pointers: needs per-token arrays.
- **Head**: prompt reading needs it for the last token only (already skipped for earlier prompt tokens,
  `skip_head`, 2026-11-09). Draft checking needs M rows of logits / argmax.
- tlen and the ratio-2 state need rollback for rejected drafts; rows appended past tlen are harmless.

## 3. DSpark (official draft for V4.1 Flash 1017, Unsloth Q8_0 GGUF, arch `dflash`)

File: `/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf`
(7.98 GB). Tensors: Q8_0 attention / fc / shared expert; MXFP4 (ggml type 39) routed experts (128, top 3);
F32 router, stream mix, norms, sinks, conf_proj; BF16 markov_w1/w2 (rank 256). 3 blocks, block size 5,
target_layers [37, 38, 39], mask token 128799, sliding window 128 (+1), rms eps 1e-20.
Reference code: llama.cpp `src/models/dflash.cpp:1390-1617` (graph), `455-596` (markov + confidence),
`common/speculative.cpp:983-1526` (driver), `tools/server/server-context.cpp:3875-5085` (cycle).

- **Input from the target**: for L in 37, 38, 39 the input of layer L (= output of L-1 after its FFN
  stream post) averaged over the 4 streams with weight 1/4 (not the stream collapse), concatenated as
  15360 F32 per token. Needed for every prompt row and every verify row.
- **Injection** per committed target row: main_x = rms_norm(fc . feat) * enc.output_norm; each stage s
  writes K_s = rope_tail(rms_norm(wkv_s . main_x) * attn_kv_a_norm_s) into its own 128(+1)-window K cache
  at the target position. No stream mix on this path. K doubles as V.
- **Draft block**: tokens [anchor, MASK x4] at pos0..pos0+4, embedded with the target's token_embd, 4
  identical streams. 3 stages, each: single-pass stream mix (the collapse uses the pre-mix from the
  previous sublayer; layer 0 attention uses copy 0), MLA-style attention (q_a 1280, q_b 64 heads x 512,
  kv 512, 1 KV head, rope on dims 448..511 adjacent pairs, base 10000, no YaRN, sink in the denominator,
  output un-rotated, o_a 8 groups -> o_b), bidirectional inside the block, every row sees the same keys
  (128 injected context keys + the block's 5); MoE top-3 of 128 with sqrt(softplus) scores, bias for
  selection only, weights normalized then x1.5, swiglu clamp 10, plus shared expert.
- **Output**: h = collapse with the last FFN pre-mix; logits = target output.weight . (rms_norm(h) *
  output_norm); markov bias chain: prev = anchor; for i in 0..4: out_i = logits_i + markov_w2 .
  markov_w1[prev]; prev = argmax(out_i). Draft tokens d0..d4 = those argmaxes. Confidence head
  (sigmoid(conf_proj . [h_i ; e_i])) only shortens drafts when p_min > 0 (default 0: unused).
- **Cycle**: draft d0..d4 -> target verifies [anchor, d0..d4] at pos0..pos0+5 (6 rows of logits) ->
  accept while target argmax == d_j -> commit anchor + accepted, new anchor = the target's token at the
  first mismatch (or the bonus after 5) -> inject the committed rows' features -> roll back target and
  draft state past the committed position. 1-6 tokens per target pass.
- Earlier lab result with the older V4 Flash and its DSpark7 pack on vLLM (four-card host, July 2026):
  ~3.5 tokens per cycle on the public continuity suite, 80.8 tok/s
  (`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-19-dspark7-draft-acceptance-diagnostic.md`).
- Draft numerics only change the acceptance rate; what must be exact is the target's 6-row pass.
  llama.cpp quantizes activations for Q8_0/MXFP4 matmuls, so it is not a bitwise reference for us.

## 4. Order of work

1. Multi-token target step for prompt reading (no rollback): M-row variants of the weight-row kernels
   (same per-token op sequence), per-token small ops, ring 128 + M, per-token publish/index in order,
   routed experts as 6M slots. Gate: a prompt read in blocks must leave bit-identical state, checked by
   the decode trace and answer ids against the one-token reading of the same prompt.
2. Verify mode: 6 rows of logits, per-row argmax, rollback of tlen / ratio-2 state / ring position.
3. The DSpark draft in our engine (Q8_0 + MXFP4 + BF16 kernels, 3 stages, markov chain), fed by the
   target's layer-37/38/39 stream means.
4. Measure tokens per cycle on the realistic suite, then the speculative loop end to end.
