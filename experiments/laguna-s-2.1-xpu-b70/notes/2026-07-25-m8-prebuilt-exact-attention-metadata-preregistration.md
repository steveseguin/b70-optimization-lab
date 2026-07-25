# Laguna M8 prebuilt exact-attention metadata preregistration

Date: 2026-07-25

## Motivation

The authoritative 272-token in-process replay decomposition recorded a median
`8.117824 ms` across 48 eager attention boundaries per M8 verifier replay. The
full-attention subgraph candidate was then rejected before generation because
Intel's current SYCL Graph implementation cannot capture the FA2 work-group
scratch-memory operation. That failure is sealed at:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-attention-subgraph-c8aa95538-6bd7c5875-20260725T004945Z
```

The next candidate does not capture, replace, or modify FA2.

The incumbent exact XPU speculative-attention path constructs the same three
metadata tensors inside every target attention layer:

- `arange(q + 1)` for one-token query rows;
- the `q` growing KV lengths derived from the transaction's sequence length;
- a contiguous `q`-row expansion of the transaction's single block-table row.

Laguna's homogeneous target layers share one `FlashAttentionMetadata` object
per attention group and transaction. The hypothesis is that constructing these
three tensors once in the metadata builder, instead of once in each of the 48
layer forwards, removes repeated host dispatch and allocation work without
changing any model arithmetic.

## Frozen candidate

Add the default-off selector:

```text
VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA=1
```

When enabled under the guarded Laguna M8 Breakable-graph identity, an eligible
single-sequence exact verifier transaction with `q` in `2..8` receives three
transaction-owned tensors built from the same inputs, dtypes, devices, and
literal PyTorch expressions as the incumbent forward path. Every target layer
then consumes those tensors. Per-layer Q/K/V descale views remain per-layer.

The candidate must:

- preserve the incumbent exact-verifier predicate;
- rebuild sequence-length-dependent metadata for every transaction;
- rebuild or invalidate the expanded block table when
  `update_block_table()` changes its source;
- reject an eligible exact-verifier forward if candidate metadata is absent,
  incomplete, or inconsistent with the transaction width;
- remain completely inert when the selector is absent or zero;
- require XPU, Laguna, DFlash depth 7, greedy draft, standard rejection,
  TP4/EP, one sequence, synchronous scheduling, PIECEWISE Breakable M8 graph,
  compilation disabled, and exact speculative attention enabled;
- leave full attention-subgraph capture disabled.

No persistent cross-transaction tensor cache is authorized in this candidate.
No attention kernel, arithmetic order, KV-cache operation, collective,
MoE/GEMM, logits, sampler, draft depth, acceptance rule, prompt, or output
length may change.

## Static and unit gates

Before device execution:

1. the vLLM worktree must be clean at a focused candidate commit descended from
   the approved record source;
2. the kernel worktree must remain clean at the approved kernel commit;
3. the main gate must pin both source commits and record the selector for every
   arm;
4. q1 and eager controls must set both attention-subgraph capture and the new
   selector to zero;
5. the graph candidate must set attention-subgraph capture to zero and only the
   new selector to one;
6. focused tests must prove exact equality with the incumbent expressions for
   every `q` in `2..8`, transaction refresh, block-table refresh, flag-off
   behavior, and fail-closed missing/inconsistent candidate metadata;
7. lint, syntax, and whitespace checks must pass.

## Diagnostic protocol

Use the frozen 272-token in-process replay protocol:

1. canonical q1 teacher, eager and non-speculative;
2. eager DFlash7 control;
3. Breakable-graph DFlash7 candidate.

Each arm gets exactly one fresh cold prompt and one 272-token generation.
There is no warm-up request, retry, cache/history reuse, prefix reuse, or
adaptive selection. Every arm must report cached tokens zero, finish by length,
and match the frozen q1 token and text hashes bitwise:

```text
token ee44dfe987c199b248cfe8f752f5fa8600a34291815894c5fb6502ffd5187cee
text  d41518e5781b3adafb966c1b9a91e46d4d23b1a1ef40d8992ccde9a55920e55f
```

The run must remain entirely on internal ext4 NVMe under `/mnt/fast-ai`.
Pre/post worker and strict-idle gates must pass. The profiler must retain 31
complete M8 replay samples on every rank with the frozen 146-graph,
145-eager-boundary topology and segment-order hash.

This diagnostic may compare attention and whole-replay timing against the
authoritative control decomposition, but it is not LocalMaxxing-submittable.

## Promotion rule

Only an exact, cache-zero diagnostic with a material reduction in attention
and whole-replay time may advance to a separately preregistered, uninstrumented
cold formal crossover against the approved `92.16352215694299 tok/s` record.
No diagnostic result may be submitted. A formal result may be submitted only
if it is an honest exact improvement under the complete matching benchmark
identity.
