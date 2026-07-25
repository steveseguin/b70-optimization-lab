# Laguna M8 prebuilt attention metadata: static-identity abort

Date: 2026-07-25

## Disposition

The first prebuilt exact-attention metadata candidate failed closed before
completing the graph generation. It produced no candidate output, timing
profile, analyzer result, benchmark result, or submission evidence.

The sealed internal-NVMe root is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-prebuilt-attn-metadata-d227c31fb-6ba825e15-20260725T011206Z
```

Frozen identities:

- main gate `d227c31fb9b9844122ccc350874b2870654c162b`;
- vLLM candidate `6ba825e152a9d5e0f5f67bd4c7fee315f2f2ad5d`;
- kernels `4772f727590c51b72add79350b913d098cf67872`.

## Completed controls

The q1 and eager arms each completed exactly one fresh 272-token generation.
Both reported cached tokens zero, finish reason `length`, and the frozen
bitwise hashes:

```text
token ee44dfe987c199b248cfe8f752f5fa8600a34291815894c5fb6502ffd5187cee
text  d41518e5781b3adafb966c1b9a91e46d4d23b1a1ef40d8992ccde9a55920e55f
```

Those controls do not authorize a retry or substitute for the missing graph
candidate output.

## Failure

The graph arm loaded both models and completed its initial PIECEWISE graph
capture. Its first later M8 replay failed on all ranks with:

```text
RuntimeError: Static tensor identity changed before breakable graph replay for
BatchDescriptor(num_tokens=8, num_reqs=None, uniform=False, has_lora=False,
num_active_loras=0)
```

The failure occurred in
`BreakableCUDAGraphWrapper._collect_tensor_signatures()` /
`BreakableCUDAGraphWrapper._replay()` before the model replay was allowed to
continue.

The v1 candidate attached newly allocated pseudo query offsets, growing KV
lengths, and expanded block-table storage to each transaction's
`FlashAttentionMetadata`. Breakable Graph recursively includes dataclass
tensors in its static signature using data pointer, storage offset, shape,
stride, dtype, and device. The tensors had correct values but new storage
addresses on the next transaction, so the guard rejected them exactly as
designed.

This is not an FA2 arithmetic, output-quality, SYCL scratch-memory,
collective-order, worker-cleanup, or device-loss failure.

## Hygiene

All q1, eager, and graph pre/post worker reports are empty. The graph post-idle
snapshot passed after the failure. The runner sealed the root read-only and it
will not be reused.

## Decision

The v1 implementation is retained as a default-off negative checkpoint. A
revised candidate requires a new preregistration because the v1 registration
explicitly forbade persistent cross-transaction storage.

The necessary design is builder-owned, fixed-address storage with transaction
values refreshed on the current stream before each eligible forward. Returned
active views must preserve the same data pointer, storage offset, shape,
stride, dtype, and device for the M8 descriptor across capture and replay.
That design must still leave FA2 eager and preserve the incumbent integer
metadata values exactly.
