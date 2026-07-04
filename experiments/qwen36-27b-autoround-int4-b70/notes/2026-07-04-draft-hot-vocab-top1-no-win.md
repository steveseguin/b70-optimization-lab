# Qwen27 Draft Hot-Vocab Top-1 Screen: No Win

Date: 2026-07-04

## Classification

Closed negative diagnostic. Do not promote or submit to LocalMaxxing.

## Question

The current valid Qwen27 `webhie/Qwen3.6-27B-int4-AutoRound` record-family
recipe spends a large fraction of decode time in repeated LM-head/logits work.
The target verifier must stay exact, but the draft proposer can be approximate
because target verification rejects wrong draft tokens. The test was whether a
small calibration-derived hot vocabulary for draft top-1 could remove enough
draft LM-head cost to beat the dense runtime INT8 LM-head recipe.

## Patch

Patch snapshot:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-xpu-draft-hot-vocab-top1-20260704.patch
```

Implementation shape:

- added a prepared hot-vocab INT8 LM-head buffer to
  `vllm/model_executor/layers/vocab_parallel_embedding.py`;
- added `LogitsProcessor.get_hot_vocab_top_tokens()`;
- added `Qwen3_5MTP.get_hot_vocab_top_tokens()`;
- added default-off proposer gate `VLLM_XPU_DRAFT_HOT_VOCAB_TOP1=1` in
  `vllm/v1/spec_decode/llm_base_proposer.py`;
- target verifier logits are unchanged and still exact/dense for the declared
  target model;
- the path is TP1-only and fails closed if hot-vocab buffers are not prepared.

## Hot Vocab Artifacts

Hot token lists were built from the non-final diagnostic calibration trace, not
from the final promotion suite:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-calibration-verifytrace-20260704A-verify-trace.jsonl
experiments/qwen36-27b-autoround-int4-b70/calibration-suite-v1.json
```

Generated hot-vocab files:

```text
experiments/qwen36-27b-autoround-int4-b70/hot-vocab/qwen27-calibration-hotvocab-top512-20260704.json
experiments/qwen36-27b-autoround-int4-b70/hot-vocab/qwen27-calibration-hotvocab-top1024-20260704.json
experiments/qwen36-27b-autoround-int4-b70/hot-vocab/qwen27-calibration-hotvocab-top2048-20260704.json
```

The `top2048` file produced `1779` usable IDs after filtering against the real
vocab, because the calibration trace did not contain 2048 unique valid IDs.

## Same-Window Strict Screen

All four lanes ran at the same timestamp window on one B70 each, using the
fixed Qwen realistic suite, chat mode, token-id timing, `cached_tokens=0` gate,
MTP3/cg8, runtime INT8 LM-head BF16 scales, and `max_model_len=2048`.

Compact summary:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-hotvocab-top1-screen-20260704-summary.json
```

Rows:

| Lane | Strict gate | Median tok/s 1-100 after TTFT | Delta vs control | Output hashes vs control |
| --- | ---: | ---: | ---: | ---: |
| dense control | pass | 65.63129544184056 | baseline | 12/12 |
| hot512 | pass | 50.12634376975731 | -23.62% | 11/12 |
| hot1024 | pass | 52.6139424510439 | -19.83% | 11/12 |
| hot2048 / 1779 usable | pass | 56.41775052143366 | -14.04% | 11/12 |

Result JSONs:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-control-hotvocab-window-20260704-20260704T083418Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-hotvocab512-20260704-20260704T083418Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-hotvocab1024-20260704-20260704T083418Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-hotvocab2048-20260704-20260704T083418Z.json
```

Run dirs:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-bf16scale-control-hotvocab-window-20260704-20260704T083418Z
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-bf16scale-hotvocab512-20260704-20260704T083418Z
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-bf16scale-hotvocab1024-20260704-20260704T083418Z
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-bf16scale-hotvocab2048-20260704-20260704T083418Z
```

## Interpretation

The dense control reproduced the record family at `65.63 tok/s`, so the
candidate losses are not variance. The hot-vocab path really executed: server
logs show prepared hot-vocab buffers and the proposer warning for each
candidate. The losses are large enough that no repeat/crossover is warranted.

Likely failure mode: the subset draft proposer loses too much acceptance. The
smaller GEMM does not compensate for worse draft quality, and even the `1779`
usable-ID list is still far below dense-draft performance.

Because output hashes differed from the dense control on one prompt, this also
does not establish exact deterministic equivalence. Target verification should
keep accepted tokens safe, but this is not a promotion-quality result and does
not deserve the full quality ladder.

## Decision

Close this lane as no-win. Do not continue simple hot-vocab/subset draft top-1
work.

The useful lesson is that the next credible path should not reduce draft
quality by restricting the vocabulary. Continue focusing on:

- reducing full LM-head cost without changing argmax semantics;
- improving accepted tokens per verifier step with a better target-matched
  drafter;
- native verifier-row/LM-head integration that avoids dense logits without a
  low-coverage subset approximation.
