# Audit: MTP3 draft INT4 top-K rerank candidate

Date: 2026-08-18
Reviewer: second-host agent (read-only; execution belongs to the measuring
host)
Candidate: `experiments/qwen38-27b-b70/patches/vllm-qwen38-draft-int4-topk-rerank-candidate-20260818.patch`
Applied worktree: `/home/steve/src/vllm-q38-draft-int4-topk-rerank`,
diff SHA256 `c4902f8eee3314d3e9953879388bbbe2e11761d026fba20c40cae2b2a141fc57`
(matches the previously recorded candidate identity).

## Mechanism

In `vocab_parallel_embedding.py`'s experimental INT4 draft lm_head path
(active only when `VLLM_XPU_DRAFT_LM_HEAD_INT4_RERANK_TOPK > 1`):

1. fast full-vocabulary INT4 GEMM produces draft logits;
2. `torch.topk` takes K candidate IDs (start with K=2);
3. candidates are rescored exactly with the retained original fp16
   `layer.weight` in float32;
4. the exact winner is written back at `top_int4_logit + 1.0` and the other
   candidates at `-inf`, so the downstream greedy argmax emits the exact
   winner.

## Verified properties

- `out_shape` is in scope (line 330); no NameError.
- The INT4 prep registers quantized buffers but never deletes
  `layer.weight`; the fp16 original stays resident (both copies coexist;
  fine at 32 GiB per card).
- Tie-break is deterministic: exact-score ties resolve to the lowest local
  vocab ID via a sentinel-min, independent of `torch.topk` ordering.
- The target verifier is untouched; every visible token remains
  target-verified, so this is within the no-shortcut policy (unlike DFlash).
- Opt-in only: `rerank_topk <= 1` preserves existing behavior bit-for-bit.

## Residual risks to screen before any strict-25

1. **Candidate-set ties.** `torch.topk` on equal INT4 logits does not
   promise a stable tie order; a tie at the K boundary could change the
   candidate *set* across runs. The exact rescore then cannot repair a
   missing candidate. Screen: repeat the previously divergent holdout
   prompt and one control prompt across two cold runs and require identical
   token IDs before running the full suite.
2. **Acceptance must actually improve.** Rerank is worth its overhead only
   if position-1 acceptance (typical 0.65) rises measurably; record
   `avg_draft_acceptance` alongside tok/s.
3. Keep K=2 for the first screen; K=4/8 only if K=2 shows a clean win.

## Status

Patch is sound and ready to screen, but the screen needs a vLLM server, so
it is measuring-host work. This 15 GiB host cannot run it (see
2026-08-18-autoround-int4-smoke-host-staging-collapse-contained-unsafe.md).
