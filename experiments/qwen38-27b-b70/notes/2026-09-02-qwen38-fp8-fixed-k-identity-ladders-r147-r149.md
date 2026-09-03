# Qwen3.8 FP8 TP2 fixed-K image: identity ladders R147, R147c, R148, R149

Date: 2026-09-02 evening, boot `2c230b44` (clean; earlier R147 attempt on boot
`9e05adaf` was stopped by an `e3:00.0` copy-engine fault at mtp1-b, see the
[partial note](2026-09-02-qwen38-fp8-mtp1-fixed-k-regenerated-oracle-r147-partial.md)).

Status: **both profiles on the row-invariant R139 image are determinism-
qualified for single requests at every tested prompt length and for output
identity through c16. c32 and c64 still miss on a per-sequence source that is
not the W8A16 GEMM, not the batch budget, and not the FP16 vocabulary head.
No public text changed yet; the publication call is the user's.**

## What passed (image R139, `sha256:901ae9e0...`)

| gate | MTP0 | MTP1 (R62 draft-INT4 treatment) |
| --- | --- | --- |
| same-image c1 repeatability, strict 12-prompt natural-512 suite | 3 fresh servers, 12/12 pairwise | 2 fresh servers, 12/12 |
| MTP1 equals same-image MTP0 | oracle | 12/12 on both servers |
| 100/168/200/224/250/300-token prompts, 5 repeats each | one token stream and one logprob array at every length | same |
| c1-c64 identity ladder (R63 config, 128 tokens, ignore_eos) | exact through c16; 30/32, 58/64 | exact through c16; 30/32, 58/64 |
| strict decode, class-balanced median | `33.337`, `33.314`, `33.289 tok/s` | `54.313`, `54.942 tok/s`, center **`54.627`** |
| canaries before/after, cache zero, FP16 verifier marker | pass | pass, marker on both ranks |

The R62/R119 headline (`54.424603`) fails the 168-250-token repeat probe and
first misses the ladder at c2. This image passes both through c16 at the same
MTP1 speed; MTP0 costs about 1.2% versus the natural kernel.

## What did not fix c32/c64

| arm | single variable | c32 | c64 | verdict |
| --- | --- | --- | --- | --- |
| R148 MTP1 | `max_num_batched_tokens` 512 to 2048 | 29/32 | 55/64 | budget cleared |
| R148 MTP0 | same | 30/32 | 55/64 | budget cleared; 32 head rows stay inside the head's exact class and still miss |
| R149 MTP1 | FP16 lm_head in <=32-row chunks (operator-proven exact, marker active, c1 oracles 64/64 unchanged) | 29/32 | 55/64 | head cleared as the token-flipping source |

Mismatches are the usual near-tie prompts (`cache-c000` token 96,
`benchmark-c019` token 60, `evidence-c007` token 13, and so on) and the set
varies between servers, as in R63. The boundary sits between 16 and 32
concurrent sequences on both profiles regardless of head rows (32 vs 64), so
the source is a kernel batched per sequence: the GDN conv/recurrent state
update or the attention decode path.

## Next (census before bisection)

Operator census of `gdn_attention_core_xpu` and its conv/state kernels, and of
the FA decode call, at 1..64 sequences on one card: per-sequence output must
equal the single-sequence output, permutation-invariant, repeat-exact. Whatever
fails is the target; no more endpoint ladders until then. The R149 head chunk
stays available as an exact building block for any configuration that pushes
more than 32 rows through the head.

Evidence: `data/2026-09-02-qwen38-fp8-*r147*`, `*r147c*`, `*r148*`, `*r149*`
result JSON; artifact roots under `/mnt/fast-ai/bench-results/qwen38-fp8-*-20260902-r14*`.
