# Qwen3.8 AutoRound INT4 native-MTP draft top-K rerank candidate

Date: 2026-08-18

Status: **source-only candidate; not built or measured**

## Why this is the next bounded arm

The strict Qwen3.8 native-MTP baseline currently measures about `91.93 tok/s`
on all 25 prompts and `86.72 tok/s` on the historical selection-12 subset.
The regular DDTree branch-width search is closed: extra target verifier rows cost
more than their acceptance gain. This arm instead tries to improve native-MTP
proposal acceptance without changing verifier width.

The existing draft output head computes the full local vocabulary with fast
INT4 weights. The candidate takes each tensor-parallel rank's local top `K`
INT4 candidates, fetches only those rows from the retained original draft-head
weights, recomputes their dot products in FP32, and makes the best rescored row
the local greedy winner. The ordinary cross-rank logits path still chooses the
global draft token. The target model and target verifier are untouched and
continue to own every visible token.

This is a higher-fidelity proposer, not an exact full-vocabulary output head.
It is also not DFlash. It can improve speed only if increased acceptance is
larger than the top-K/index-select/rescore cost.

## Exact source identity

- vLLM base: `44fc8fde09fc311d3099dab10366b672d9142ea4`
- patch: [`vllm-qwen38-draft-int4-topk-rerank-candidate-20260818.patch`](../patches/vllm-qwen38-draft-int4-topk-rerank-candidate-20260818.patch)
- one-context patch artifact SHA-256:
  `7d17e7dbd4b160bf016a2e3d789618ed911139ac5fd0c16d6ac356a6600bbf9a`
- resulting `git diff --binary` SHA-256 (the fail-closed run identity):
  `c4902f8eee3314d3e9953879388bbbe2e11761d026fba20c40cae2b2a141fc57`
- XPU-kernels base remains clean:
  `2dd55f380df753a10a88fcd9e96192561066e713`

Apply the patch to a clean candidate checkout at the exact vLLM base. The
validation runner remains fail-closed: an exact-mode run must explicitly set
the expected dirty-diff checksum rather than bypass source verification.

```bash
git -C /path/to/vllm checkout 44fc8fde09fc311d3099dab10366b672d9142ea4
git -C /path/to/vllm apply \
  /path/to/b70-optimization-lab/experiments/qwen38-27b-b70/patches/vllm-qwen38-draft-int4-topk-rerank-candidate-20260818.patch

export VALIDATION_EXPECT_VLLM_DIFF_SHA256=c4902f8eee3314d3e9953879388bbbe2e11761d026fba20c40cae2b2a141fc57
export VALIDATION_DRAFT_LM_HEAD_INT4_RERANK_TOPK=4
```

The server log must contain `rerank_topk=4`, and `identity.env` must record
both the rerank width and expected vLLM diff checksum.

## Gates

1. Build and import the candidate from the checksum-matched source tree.
2. Run a bounded smoke and a two-prompt timing/acceptance screen at `K=2`,
   `K=4`, and `K=8`, using fresh AOT/cache roots for each source identity.
   Start with `K=4`.
3. Stop if the additional proposal work materially lengthens the decode step
   without enough accepted-token gain. At unchanged step time, moving the
   all-25 baseline from `91.93` to `>100 tok/s` needs roughly `8.8%` more
   visible tokens per step (about `2.97 -> 3.23` in the rough current model).
4. Any promising width must run cache-zero cold 25-prompt A/B arms, report both
   all-25 and selection-12, pass `25/25` self-determinism, and pass the retained
   Qwen3.8 target-only quality oracle. A changed acceptance pattern does not
   waive state or output exactness gates.
5. Do not submit LocalMaxxing or publish a performance claim before the full
   strict gate is complete.

Widths above eight are deliberately out of scope unless candidate-coverage
evidence shows the target-preferred draft token is routinely outside local
top eight; otherwise they add selected-row traffic and reduction work without
a justified acceptance opportunity.
