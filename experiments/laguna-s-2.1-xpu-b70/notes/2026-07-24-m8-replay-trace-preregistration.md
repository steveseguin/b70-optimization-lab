# Laguna M8 replay-only PTI decomposition preregistration

Date: 2026-07-24 America/Toronto

Status: **preregistered; not yet run**.

This is a diagnostic component trace, never benchmark or LocalMaxxing
evidence. Its sole purpose is to split the exact graph record's remaining
`~40.59 ms` target cycle into retained device work, Level Zero host/API
cost, kernel queue/submission time, and graph-external orchestration.

## Frozen identity

- vLLM: `b1cca41292296342fd9f0f7a5621e8d26d7a910d`, whose only
  descendant change from the published record is an opt-in PTI temporal-control
  hook;
- XPU kernels: `4772f727590c51b72add79350b913d098cf67872`;
- PTI source: `a5bab309f4ffdd78bd127035c46f5f75371160f8`;
- unitrace SHA-256:
  `5aaca1f418a212a1d298cac27afb6c471bf1fcf47a1622e0c20d1a2cf43fc85a`;
- target and DFlash model roots remain below `/mnt/fast-ai`;
- exact selector stack is DFlash depth 7, M8 fused W1-route-W2,
  route-interleaved W2, shared elementwise, QKNorm/RoPE, and W1 N64.

## Protocol

Two fresh offline processes run sequentially: eager, then audited Breakable
graph. PTI starts paused before model initialization. Each arm constructs the
same frozen `LLM` configuration locally. The eager driver resumes PTI directly
before its generation. In the graph arm, the four workers leave PTI paused
through the lazy first-request capture, rendezvous at the first actual replay,
and rank zero resumes the shared PTI session. A second rendezvous prevents any
rank entering replay before tracing is live; this single diagnostic barrier is
identified overhead and not model work. The parent pauses PTI after generation.
There is no warmup generation, second prompt, prefix cache, response reuse, or
endpoint claim.

Both arms use the same prompt only so raw greedy token IDs can be compared.
Each must emit exactly 128 tokens with `cached_tokens == 0`; every token ID,
text hash, finish reason, and prompt identity must match. The trace is invalid
unless exactly four worker device-timing reports survive, either process fails,
workers remain alive, a model/artifact path resolves to USB storage, or a
device-idle check fails.

PTI records:

- aggregate Level Zero host API timing;
- device kernel/command timing with shapes;
- kernel queue, submission, and execution intervals;
- PID-bound output from all followed worker processes.

The trace intentionally does not enable raw tensor evidence because its
synchronous device-to-host copies would invalidate timing. Bitwise graph
correctness is already independently established by the sealed 52/52 formal
crossover; this paired run adds a fresh output-level exactness check and may
only guide the next separately gated optimization.

## Decision rule

- If graph-external host/API and submission cost is material, prefer a
  zero-arithmetic orchestration change: capture-built static-input access plan,
  prebound collective callbacks, or a native replay-plan executor.
- If the retained floor is dominated by the 97 collective boundaries, pursue
  only a graph-recordable fixed-address TP4 collective implementation with the
  exact incumbent gather and rank-ordered BF16 reduction semantics.
- If attention dominates, investigate narrowing the 48 attention breaks while
  leaving KV-transfer side effects eager.
- Do not retry direct XCCL graph capture, collective coalescing, compiler
  reassociation, or previously terminal arithmetic-fusion lanes unchanged.
