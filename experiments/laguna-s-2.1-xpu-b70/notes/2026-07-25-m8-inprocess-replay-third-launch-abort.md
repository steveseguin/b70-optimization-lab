# Laguna M8 in-process replay: third launch abort

Date: 2026-07-25 America/Toronto

Status: **q1 contract abort during model construction; no weights completed
loading and no generation**.

Sealed root:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-inprocess-replay-166760ed7-8cf58ed0f-20260725T000143Z
```

The environment and IPC preflights passed and q1 reached worker-side model
construction. The Laguna exact-stack guard then rejected
`VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=1` because q1 intentionally has no
DFlash depth-7 speculative configuration:

```text
speculation is not DFlash depth 7
```

This exposed a protocol error: the q1 target teacher had been assigned the
optimized DFlash selector stack and DFlash's synchronous scheduling contract.
The canonical q1 teacher instead uses eager target-only execution, its original
async scheduler, and no experimental M8 fusion/occupancy selectors. The four
workers exited gracefully, the post-worker report was empty, and strict
post-idle proof passed. No output token or arm record was produced; eager and
graph were never attempted.

The sealed root is an abort artifact only and must not be reused.

Disposition: freeze arm-specific identities. q1 uses async scheduling with
fused W1/route-W2, route interleave, shared elementwise, and QKNorm+RoPE all
disabled. Eager and graph DFlash retain synchronous scheduling and all four
approved selectors. The analyzer must require these differences while still
requiring identical greedy token IDs, text hash, and finish reason.
