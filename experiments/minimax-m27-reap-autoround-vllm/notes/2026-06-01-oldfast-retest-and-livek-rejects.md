# 2026-06-01 Old-Fast Retest and Live-K Rejects

Goal: answer whether the archived `89.49922316987691` output tok/s REAP path
can be recovered on the current live vLLM source, and record the rejected
attempts made while trying to get back above the non-REAP lane.

## Current Answer

No quality-valid 89 tok/s runtime is available from the current live source.

The archived `89.49922316987691` result remains a historical quality-gated run,
but retesting the same cache lineage now splits into two bad options:

- stale fast AOT path: `88.x` output tok/s, but async quality emits token id `0`
  / NUL output
- quality-repaired path: valid async output, but decode falls back to about
  `83.3-83.5` output tok/s

The current same-checkout non-REAP comparison is also only about `83.05` output
tok/s, so the current REAP path is not materially behind the current non-REAP
path. It is behind the older stale/AOT record.

## Confirmed Quality-Valid Current Best

Fresh quality-safe REAP:

- settings: `FULL_FORWARD_CUSTOM_OP=0`, `QK_NORM_RESTORE_WEIGHT=0`,
  qk-helper on, attention-delay on, `pidfd` CCL IPC
- quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-fullforward0-restore0-qksafe-20260601T1828.json`
- benchmark:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T223035Z.json`
- result: `18.39128096101922 s`, `111.35711559954889` total tok/s,
  `83.517837` output tok/s

Same-checkout non-REAP control:

- quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-nonreap-promoted-env-20260601T2311.json`
- benchmark:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode-nonreap/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T231613Z.json`
- result: `18.49487430899171 s`, `110.73338297867303` total tok/s,
  `83.050037` output tok/s

## Old-Fast Retest

Copied the old promoted cache root before retesting:

`/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-autoround-no-logits-ws-20260531-retest-20260602T000854Z`

Old settings with current source:

- `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP=1`
- `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT=1`
- qk-helper on
- attention-delay off
- no logits WS
- `pidfd` CCL IPC

Quality passed after vLLM refused the old binary and rebuilt:

- quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/quality-smoke-20260602T000919Z.json`
- generated tokens: `384`
- distinct generated token ids: `161`
- no NUL/control output

But throughput collapsed:

- benchmark:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode-oldfast-retest/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T001254Z.json`
- result: `24.749995906022377 s`, `82.74748843500468` total tok/s,
  `62.060616` output tok/s

The new retest graph key was `fd410802e8`; the old fast key was `f728d2c0cf`.
Cache key metadata showed the same compiler/config/env hashes and a different
source code hash, so settings alone cannot recover the old speed.

## Graph Comparison

Old `f728d2c0cf` graph shape:

- traces per-layer gate weights into the graph
- calls `torch._C._nn.linear(... gate.weight ...)`
- then calls generic `torch.ops.vllm.moe_forward(...)`
- `minimax_m2_moe_forward=0`

New `fd410802e8` graph shape from the old-settings rebuild:

- replaces per-layer gate weights with
  `block_sparse_moe_encoded_layer_name`
- calls `torch.ops.vllm.minimax_m2_moe_forward(...)`
- `minimax_m2_moe_forward=62`

This explains the `62` tok/s old-settings retest, but it does not fully explain
the current `83.x` quality-safe path, because the fresh restore-off path still
inlines generic MoE. The broader speed loss is tied to stale fast AOT behavior
versus the quality-safe clean-weight/QK path, not only to MoE inlining.

## Rejected Experiments

`FULL_FORWARD_CUSTOM_OP=1`, restore off, qk-helper on:

- quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-fullforward1-restore0-qksafe-20260601T235839Z.json`
- result: quality passed, `384` generated tokens, `183` distinct ids
- benchmark:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode-fullforward1-restore0/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T000428Z.json`
- speed: `59.114708` output tok/s
- decision: reject

Clean-buffer registered-buffer experiment:

- quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-cleanbuffer-restore1-qk0-20260601T232217Z.json`
- result: failed with token id `0` / NUL output
- decision: reject

Global live-K weight selector:

- cache:
  `/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-livek-restore1-qk0-fullforward0-20260601T232850Z`
- result: hung during bring-up for roughly two hours and was killed
- decision: reject

Layer-61-only live-K selector, qk-helper off:

- quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-livek61-noopgraph-triton2025-restore1-qk0-fullforward0-20260601T234356Z.json`
- benchmark:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode-livek61/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T234746Z.json`
- speed: `57.43` output tok/s
- decision: reject

Layer-61-only live-K selector against preserved `f728`, qk-helper on:

- quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-f728-livek61-qk1-restore1-20260601T235223Z.json`
- benchmark:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode-f728-livek61/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T235450Z.json`
- speed: `60.43` output tok/s
- decision: reject

## Source State

The rejected live-K selector was removed from the active vLLM source after the
failed screens. `linear_attn.py` still has the broader existing Q/K restore and
trace work from this lab lane, but no `LIVE_K` selector remains in its active
diff. Syntax check passed:

```bash
python3 -m py_compile vllm/model_executor/layers/mamba/linear_attn.py
```

The rejected live-K selector patch is archived for reference only:

`patches/vllm-minimax-qk-live-k-layer-selector-20260601.patch`

## Next Useful Work

Do not spend more time on simple env toggles for this issue. The next sizeable
speed improvement likely requires source-level repair:

- make Q/K RMS clean-weight restore graph-safe without forcing the slow path
- avoid stale owner clean-weight attributes in captured graphs
- profile the correct `83.x` path versus stale `88.x` path at the op boundary
- recover the old fast graph schedule with valid Q/K weights, or replace it
  with a real MiniMax MoE/QK fusion that removes per-token work
- expand the runtime hash audit to include `linear_attn.py`, `minimax_m2.py`,
  and custom op registration files so old AOT/source drift is caught before
  benchmarking
