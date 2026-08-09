# Qwen3.6 27B Q8 GGUF research intake

This is the living, sourced idea queue for the one-B70-per-process Q8_0 lane.
It supports the adaptive strategy in
[`experiments/qwen36-27b-q8-gguf-b70/STRATEGY.md`](../../experiments/qwen36-27b-q8-gguf-b70/STRATEGY.md).
It is not an execution checklist and does not authorize a GPU run.

## Queue rules

Use `inbox`, `shaped`, `ready`, `active`, `parked`, `rejected`, or `promoted`.
Every item needs:

- primary source or local evidence;
- mechanism and affected prompt/decode/context/concurrency regime;
- why it may transfer to B70/SYCL;
- mathematical or quality invariant;
- cheapest useful discriminator;
- evidence level: claim, source review, component, endpoint, or promoted;
- outcome links and a concrete revisit trigger when parked or rejected.

Do not copy raw performance claims into the local result ledger. Other
hardware/backend rates are leads only. Prefer updating an existing mechanism
entry over adding a duplicate patch-shaped idea.

## Mechanism watchlist

These are durable research families, not ranked tasks:

- Q8 layout, dequantization, GEMV/GEMM, and multi-row weight reuse;
- Gated DeltaNet projection packing, state layout, recurrence, and direct
  cache writeback;
- exact chunk-parallel GDN prefill and complete-boundary fusion;
- full-attention, FlashAttention, and KV traffic toward 32K;
- launch, allocation, copy, host-sync, and graph-boundary removal;
- scheduler, batching, concurrency, turnover, and workload fairness;
- compiler, oneAPI, Unified Runtime, IGC, xe, and upstream llama.cpp changes;
- GDN-aware checkpoint/replay/speculation only under stronger quality gates.

## Initial primary-source registry

- [official Qwen3.6 27B configuration](https://huggingface.co/Qwen/Qwen3.6-27B/blob/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9/config.json)
- [llama.cpp](https://github.com/ggml-org/llama.cpp) and its
  [SYCL backend guide](https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/SYCL.md)
- [Q8_0 SYCL reorder PR](https://github.com/ggml-org/llama.cpp/pull/21527)
- [SGLang Qwen3.5/Qwen3-Next optimization tracker](https://github.com/sgl-project/sglang/issues/18590)
- [packed GDN decode](https://github.com/sgl-project/sglang/pull/20627),
  [fused projection transforms](https://github.com/sgl-project/sglang/pull/21019),
  and [GDN state-layout work](https://github.com/sgl-project/sglang/pull/20283)
- [direct recurrent-cache writeback](https://github.com/ggml-org/llama.cpp/pull/23940)
- [fused GDN KKT work](https://github.com/sgl-project/sglang/pull/21411)
  and an [end-to-end-negative layout experiment](https://github.com/sgl-project/sglang/pull/31191)
- [fused GDN prefill prologue](https://github.com/sgl-project/sglang/pull/30797)
  and [fused state I/O](https://github.com/vllm-project/vllm/pull/50372)
- [vLLM hybrid-context-parallel RFC](https://github.com/vllm-project/vllm/issues/37995)
- [ReplaySSM](https://dao-lab.ai/blog/2026/replayssm/) and its
  [open vLLM integration](https://github.com/vllm-project/vllm/pull/48792)
- [DeltaNet hardware-efficient parallelization](https://arxiv.org/abs/2406.06484)
- [FlashAttention-2](https://arxiv.org/abs/2307.08691)
- [MLPerf Inference rules](https://github.com/mlcommons/inference_policies/blob/master/inference_rules.adoc)

For each source, retain a last-reviewed date or commit in the next scouting
note and review only deltas. Track merged, open, and abandoned work; an
end-to-end negative caused by layout conversion or integration overhead is a
valuable result.

## Current intake

Last external scan: 2026-08-08. These are leads, not claimed local wins or a
fixed execution order.

| Status | Mechanism lead | Why it remains relevant | Evidence needed next |
|---|---|---|---|
| `shaped` | Coalesced Q8 layout and direct reordered-weight consumption | The selected model carries a large resident weight set, and merged Arc work reports a large layout-only gain without changing Q8 bits. | Reconcile current local treatment with upstream deltas, then require treatment-entry and complete-endpoint evidence. |
| `shaped` | Packed/fused GDN projection, recurrence, state layout, and direct state writeback | Forty-eight recurrent layers make state traffic and small-operation overhead durable targets in both prompt and decode phases. | Profile the full recurrent boundary by phase and context before selecting a transferable implementation. |
| `shaped` | Exact chunk-parallel GDN prompt processing | Long prompts need an exact formulation suited to matrix hardware; upstream work also shows layout conversions can erase a faster kernel. | Bound the whole-boundary opportunity and include every layout/copy cost in the discriminator. |
| `shaped` | Launch, allocation, copy, and synchronization removal | Short prompt and decode paths contain many small recurrent operations where orchestration cost may matter. | Count complete-cycle overhead and prove that removal survives the service endpoint. |
| `shaped` | Full-attention and KV-cache path toward 32K | Sixteen full-attention layers remain context-sensitive even when GDN state is fixed-size. | Maintain context-stratified profiles and validate exact attention, latency, and memory behavior near 32K. |
| `parked` | Replay/checkpoint-based state traffic reduction and GDN-aware speculation | It may become valuable with concurrency, but upstream evidence suggests different economics from batch-one target execution. | Reopen after ordinary c2 behavior and batch/context crossover evidence exist; retain exact state/output gates. |

At each cycle boundary, the external scout, internal historian, bottleneck
analyst, and integrity reviewer should update or challenge these entries.
Detailed candidates and source deltas belong in dated scouting notes linked
from the relevant row so this page remains small and current.

## Review trigger

Revisit this queue after a meaningful profile change, upstream/runtime update,
new promoted result, repeated failure, or research stall. Rejected ideas are
reopened only when their named blocker or validation weakness changes.
