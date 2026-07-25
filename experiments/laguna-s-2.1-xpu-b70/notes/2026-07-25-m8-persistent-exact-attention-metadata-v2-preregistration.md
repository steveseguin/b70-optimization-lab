# Laguna M8 persistent exact-attention metadata v2 preregistration

Date: 2026-07-25

## Superseded v1 design

The first prebuilt metadata candidate was rejected by the Breakable Graph
static-input guard because transaction-owned tensors received new storage
addresses between capture and replay. The sealed abort and root are documented
in:

```text
2026-07-25-m8-prebuilt-attention-metadata-static-identity-abort.md
```

The v1 root is terminal and will not be retried or reused. This registration
authorizes a distinct implementation and a fresh campaign root.

## Frozen v2 candidate

Retain the default-off selector:

```text
VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA=1
```

The `FlashAttentionMetadataBuilder` may now own fixed-address XPU buffers for
the exact speculative-attention query offsets, growing KV lengths, and expanded
block table. This is the only persistent cross-transaction storage authorized
by v2.

The buffers must:

- be private to one metadata builder, device, dtype, and process;
- hold at most the `q=2..8` verifier metadata and the existing block-table
  column width;
- be allocated before their first eligible model forward and then retain their
  storage addresses;
- expose active views whose data pointer, storage offset, shape, stride, dtype,
  and device are stable for repeated calls with the same `q` descriptor;
- refresh every transaction-dependent value on the current stream before the
  model forward;
- refresh the block-table snapshot after `update_block_table()` and never
  retain a prior KV group's contents;
- reject dtype, device, shape, column-width, or ownership drift instead of
  reallocating after activation.

For `q=8`, capture and every replay must therefore see identical tensor
signatures while observing current sequence lengths and block-table values.
Smaller exact widths may use stable active views of the same storage. Metadata
for an ineligible transaction remains absent.

The query offsets and integer KV-length offsets are constants. They may be
precomputed once. The current KV base and block-table contents must be copied
or written into their fixed outputs once per transaction. Integer results must
equal the incumbent expressions elementwise for every `q` in `2..8`.

## Unchanged model contract

The candidate still leaves the FA2 call eager. It does not capture or replace
FA2 and does not change:

- attention arithmetic or kernel selection;
- per-layer Q/K/V scale views;
- KV-cache writes or block assignment;
- model weights, quantization, MoE/GEMM kernels, collectives, logits, sampler,
  draft depth, acceptance, prompt, or completion length.

The rejected full-attention subgraph selector must remain zero in every arm.
The candidate selector remains zero for q1 and eager and one only for the graph
arm. The exact Laguna M8 Breakable-graph runtime guard remains mandatory.

## Static and unit gates

Before device execution:

1. preserve v1 as a default-off committed checkpoint and make v2 a focused
   descendant;
2. keep the kernel tree unchanged and clean;
3. prove elementwise equality to the incumbent expressions for every
   `q=2..8`;
4. prove same-width repeated builds retain data pointer, storage offset, shape,
   stride, dtype, and device while sequence length and block-table values
   change;
5. prove `q=8 -> q=2 -> q=8` does not corrupt or reallocate the M8 views;
6. prove `update_block_table()` refreshes the current builder's private
   storage;
7. prove missing, inconsistent, or post-activation shape/dtype/device drift
   fails closed;
8. prove selector-off behavior remains the incumbent path;
9. pass focused Laguna Breakable-graph tests, lint, formatting, syntax, and
   whitespace checks;
10. pin the exact new vLLM commit and candidate environment in the main gate.

## One-shot diagnostic

Use a new internal-NVMe root and the frozen 272-token protocol:

1. canonical q1 teacher;
2. eager DFlash7 control;
3. Breakable-graph DFlash7 persistent-metadata candidate.

Each arm receives one fresh process, one cold prompt, and exactly one
272-token generation. There is no warm-up request, retry, cache/history reuse,
prefix reuse, or result-conditioned selection. The old v1 controls are not
reused. Every new arm must report cached tokens zero, finish by length, and
match the frozen q1 token and text hashes bitwise.

The graph profiler must retain 31 complete M8 replay samples on all four ranks
with the frozen 146-graph, 145-eager-boundary topology and segment-order hash.
All source, worker, idle, mount, model, and binary identity gates remain
fail-closed.

This run is diagnostic-only. It may advance only if exactness passes and both
whole-replay and attention-related host work improve materially without merely
moving cost outside the measured boundary.

## Promotion

A diagnostic pass authorizes only a separately preregistered, uninstrumented
cold formal crossover against the approved `92.16352215694299 tok/s` record.
No diagnostic output is submittable. Only an exact, cache-zero, matching-
identity formal improvement may be sent to LocalMaxxing.
