# Laguna width-12 graph-safe attention: attempt 2 paged-decode diagnosis

Date: 2026-07-26 America/Toronto

Status: **no candidate measurement; exact launcher identified**.

Artifact:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m12-attngraph2-20260726T181346Z
```

This attempt passed the harness and wrapper preflights, started all four ranks,
and reached the first width-12 verifier step. It then failed on every rank with:

```text
RuntimeError: The sycl_ext_oneapi_work_group_scratch_memory feature is not yet
available for use with the SYCL Graph extension.
```

The previously rebuilt graph-safe chunk-prefill launcher was loaded, but it is
not the launcher used by Laguna's exact verifier. The runtime deliberately
represents `q=12` as twelve independent one-token sequences and invokes
FlashAttention with `max_seqlen_q=1`. The log confirms:

```text
Using XPU exact speculative attention: q=12 is represented as one batched
paged-decode launch.
```

Therefore the remaining unsupported scratch-memory property is in
`paged_decode.hpp`, not `chunk_prefill.hpp`. Both its main kernel and optional
split-reduction kernel still used `work_group_scratch_size`.

No throughput, correctness, or topology claim is attached to this attempt.
Cleanup passed with `stop_status=0`, `worker_status=0`, and `idle_status=0`.
The next candidate must first rebuild and component-test a paged-decode launcher
using handler-owned typed local accessors, then use a fresh artifact root.

## Follow-up repair gate

The paged-decode main and split-reduction launches were converted to typed
handler-owned local accessors and committed in the kernel worktree as:

```text
7e680978dc3a92175ea74fd59428eed55c03e019
```

The reduced-policy rebuild completed, and the deployed attention library is:

```text
libattn_kernels_xe_2.so
sha256=ad0eb26f3b0680fcd54a50de821e9c881524d50ad5361b872f88cb0b333b65ca
```

Two BF16 head-128 paged-decode component cases passed against the reference:
full attention and sliding-window attention. A direct XPU graph gate then used
the exact Laguna verifier shape—twelve one-token sequences, 18 query heads,
two KV heads, head size 128—and tested both full and sliding attention. Capture
and replay completed, replay changed when the fixed-address query changed, and
both initial and changed replay outputs were bitwise equal to eager output.

This validates the launcher component only. It does not classify the full
model candidate; that requires a fresh four-rank scored leg.
