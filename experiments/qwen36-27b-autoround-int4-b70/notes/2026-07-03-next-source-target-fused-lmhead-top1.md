# 2026-07-03: next source target is true fused LM-head top-1

## Current State

Current valid record:

- `53.522 tok/s` conservative LocalMaxxing-approved row;
- current healthy-GPU reconfirmation: `52.836`, `53.048`, `52.865 tok/s` on
  GPUs 1-3;
- DFlash and EAGLE3 external drafters are closed no-win/unstable locally;
- source timing shows full BF16 LM-head/logits dominates the internal MTP3 path.

Representative timing from the promoted recipe:

```text
spec_decode.greedy_sample.compute_logits: 1740 calls, avg ~4.452 ms
gpu_model_runner.compute_logits:          580 calls, avg ~4.424 ms
gpu_model_runner.rejection_sampler:       568 calls, avg ~0.441 ms
proposer model forward:                   ~0.65-0.83 ms
```

The model's `lm_head.weight` is BF16 and huge (`248320 x 5120`). The AutoRound
INT4 quantization does not cover `lm_head`, so a major remaining cost is full
BF16 vocab projection and logits materialization.

## Call-Graph Anchors

Draft path:

- `GPUModelRunner.propose_draft_token_ids()` -> MTP drafter in
  `/home/steve/src/vllm/vllm/v1/worker/gpu_model_runner.py`;
- `SpecDecodeBaseProposer.propose()` serially runs one MTP forward and one
  greedy sample per draft token in
  `/home/steve/src/vllm/vllm/v1/spec_decode/llm_base_proposer.py`;
- `_greedy_sample()` calls either `model.get_top_tokens()` or
  `model.compute_logits()` + `argmax`;
- Qwen MTP wrappers expose `compute_logits()` in
  `/home/steve/src/vllm/vllm/model_executor/models/qwen3_5_mtp.py` and
  `/home/steve/src/vllm/vllm/model_executor/models/qwen3_next_mtp.py`;
- `LogitsProcessor._get_logits()` calls
  `lm_head.quant_method.apply(...)` in
  `/home/steve/src/vllm/vllm/model_executor/layers/logits_processor.py`.

Target verification path:

- `GPUModelRunner` selects verifier rows and calls `_compute_logits()`;
- `RejectionSampler` slices target and bonus logits and performs greedy
  verification;
- target Qwen models have `get_top_tokens()`, but today that still calls
  `lm_head.quant_method.apply(...)` and then reduces the full logits.

## Important No-Win Lessons

Do **not** repeat these patches as-is:

- exact target argmax-only verification: passed strict gate but reached only
  `52.543 tok/s` because `get_top_tokens()` still paid the full LM-head matmul;
- draft `use_local_argmax_reduction`: active path, but crossover was flat
  (`control 53.0196` vs `candidate 52.9727 tok/s`) for the same reason;
- GDN row-copy tuning: current promoted trace had zero physical row-copy records
  and timing points at LM-head/logits instead.

## Next Implementable Target

Build a **true exact fused LM-head top-1** path for greedy-only speculation:

1. Add a default-off XPU path for `LogitsProcessor.get_top_tokens()` that
   computes top-1 token IDs without materializing the full `[batch, vocab]`
   logits tensor.
2. Preserve exact greedy semantics:
   - padding mask / `org_vocab_size`;
   - `scale`;
   - `soft_cap`;
   - NaN sanitation policy when enabled;
   - deterministic tie behavior matching existing `torch.max` / `argmax` well
     enough for strict hash gates;
   - fallback when logits processors, penalties, bad words, allowed-token masks,
     logprobs, or non-greedy sampling are active.
3. Once true top-1 exists, re-enable it for:
   - Qwen MTP drafter `_greedy_sample()` path;
   - target argmax-only rejection path for greedy verification and target-owned
     bonus semantics.

Expected shape of benefit:

- MTP3 pays three draft LM-head/top-1 operations per spec step plus one target
  verifier logits operation;
- serial MTP dependency prevents batching draft steps exactly;
- the practical win must make each top-1 operation cheaper, not merely reduce
  communication or sampler plumbing.

## Risk

This is source-level XPU kernel work, not a flag sweep. It can silently change
tokens if the reduction does not exactly match the existing greedy path. Every
candidate must run:

1. quick diagnostic/probe first;
2. strict Qwen realistic suite with token IDs and `cached_tokens=0`;
3. quality suite against the current baseline;
4. same-window/crossover on GPUs 1-3 if the delta is under about `1-2%`.

GPU0 has recently device-lost under speculative decode; avoid using it for
precision comparisons until it passes a fresh control again.
