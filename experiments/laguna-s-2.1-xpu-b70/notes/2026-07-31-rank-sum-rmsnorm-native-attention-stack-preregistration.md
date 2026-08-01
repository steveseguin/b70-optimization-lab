# Laguna deferred rank-sum/RMSNorm plus native-M12 attention stack

Date: 2026-07-31 America/Toronto

Status: **preregistered before integration or endpoint execution**.

## Premise

The promoted exact BF16-KV record is `125.4619731637751 tok/s`
conventionally, with target width 12, DFlash depth 11, target topology
`146/145`, and draft topology `14/13`. Reaching 130 at unchanged acceptance
requires reducing the measured average cycle by about `1.13 ms`.

Two independently exact components are available but neither justified a new
endpoint alone:

- literal TP4 rank-ordered BF16 sum fused with the following residual-add
  RMSNorm saves `0.00620310 ms` per boundary, or about `0.5965 ms` over the 96
  target boundaries, with `10/10` raw-output/residual checks exact;
- native M12 BF16 QKV/O matrix multiplication saved about `1.190 ms` in the
  streamed-weight component and its prior endpoint was 13/13 exact with a
  small `+0.2427%` single-leg signal, below the promotion floor.

This experiment combines them. It does not reopen native peer collectives:
the failed mailbox/atomic protocol, slower direct oneCCL replay hook, and
endpoint-negative IPC-event integration remain closed.

## Frozen treatment

Starting from the promoted vLLM and XPU-kernel source identities, add one
default-off exact-target selector that:

1. leaves all 96 fixed-address oneCCL all-gathers eager and in their audited
   order;
2. defers only the local rank-ordered sum after each gather;
3. returns a guarded rank-0 view solely as a shape/address carrier until the
   immediately following normalization site;
4. consumes the original four gathered rank buffers in one native operation
   that performs BF16 `rank0 + rank1 + rank2 + rank3`, preserving each BF16
   rounding boundary, then the incumbent residual add and RMSNorm arithmetic;
5. covers 48 post-attention, 47 next-layer input, and one final normalization
   boundary, with no pending gather allowed across any other consumer; and
6. enables the already validated native M12 BF16 QKV/O projection allowlist.

The target and draft weights, BF16 KV, width/depth, attention algorithm,
collective payloads and count, residual arithmetic, sampler/rejection rule,
prompts, cache policy, and score window remain unchanged. Selector-off source
behavior remains the promoted path.

## Gates and stop rules

1. Focused tests must prove selector-off inertness, exact-target-only
   selection, one-producer/one-consumer ownership, pending-state underflow and
   overflow rejection, and all 96 consumers accounted for.
2. On one B70, the integrated deferred path must match the literal incumbent
   in raw BF16 for changed gathered inputs, residuals, and weights at
   `M=12,H=3072`, including both normalized output and residual output. Native
   M12 projection parity remains covered by its existing 224-case and
   streamed-weight gates.
3. A bounded non-scored live smoke may run only after gates 1-2. It must prove
   changing requests, canonical-q1 prefix exactness, cache zero, target
   `146/145`, draft `14/13`, exactly 96 fused-consumer markers per target
   capture, and clean teardown. Any mismatch, stale pending state, topology
   drift, device error, or teardown failure closes the treatment; no retry or
   hardware recovery follows.
4. One formal cold 13-prompt endpoint is authorized only after the smoke. Its
   first valid score stands. It must be 13/13 token-and-text exact, cache-zero,
   one invocation per prompt, topology-valid on all four ranks, and cleanly
   idle before and after.
5. Promotion requires an improvement over `125.4619731637751 tok/s`
   conventional. Submission is allowed only for a verified new matching
   LocalMaxxing record. No warmup, retry, prompt omission, acceptance tuning,
   precision change, metric substitution, or reboot/reset is authorized.

The component extrapolations are scope estimates, not an endpoint claim.

## Pre-health symbol-check failure and correction

The first smoke invocation stopped before health, weight loading, graph
capture, collective execution, or any request at:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-ranksum-attn-smoke-20260801T064500Z
```

All four workers rejected the candidate during `LagunaModel` construction
because the fail-closed symbol check ran before decoder-layer construction had
imported `vllm_xpu_kernels._C`. A clean-process check against the SHA-locked
candidate proved the distinction directly: the operator namespace was absent
before importing that module and present immediately afterward. Runtime-lock
verification had already proved the candidate file and source identity.

This was a false-negative evidence check, not a missing operator or device
failure. Cleanup was clean (`stop_status=0`, `worker_status=0`,
`idle_status=0`). vLLM commit `15d9b2d40` moves only the symbol/evidence check
after decoder-layer construction; the configuration checks, arithmetic,
dispatch, and native module are unchanged. Because no request or score existed,
one corrected smoke remains authorized. Its first substantive result stands;
no retry of a measured result is authorized.
