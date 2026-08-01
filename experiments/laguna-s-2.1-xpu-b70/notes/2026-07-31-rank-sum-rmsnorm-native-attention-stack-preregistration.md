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

All four workers rejected the candidate during `LagunaModel` construction.
This was initially attributed to the fail-closed symbol check running before
decoder-layer construction imported `vllm_xpu_kernels._C`. The later v2 audit
below disproves that ordering explanation: XPU platform initialization imports
`_C` before `LagunaModel.__init__`. The observation that an isolated process
can register the operator by explicitly importing the SHA-locked module was
real, but it did not establish the worker import order.

This was a false-negative evidence check, not a missing operator or device
failure. Cleanup was clean (`stop_status=0`, `worker_status=0`,
`idle_status=0`). vLLM commit `15d9b2d40` moves only the symbol/evidence check
after decoder-layer construction; the configuration checks, arithmetic,
dispatch, and native module are unchanged. Because no request or score existed,
one corrected smoke remains authorized. Its first substantive result stands;
no retry of a measured result is authorized.

## Corrected-smoke pre-health failure and v2 wiring candidate

The corrected smoke stopped before health at:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-ranksum-attn-smoke-corrected-20260801T070500Z
```

It did not load weights, capture or replay a graph, execute a model collective,
serve a request, or produce a score. All four workers rejected model
construction with the same fail-closed error, and teardown was clean:
`original_status=2`, `stop_status=0`, `worker_status=0`, `idle_status=0`.
The pre- and failure-post-idle records both pass.

The first invocation immediately before this artifact also stopped before
server launch because its command transcribed the grouped-GEMM checksum
incorrectly. The on-disk DSO and runtime lock both carry
`c4845ed7704a9afcf59e12f9d51e288f293f2e39966e283e2a7e322fed68b839`;
that invocation is not runtime evidence.

Direct source inspection identified a different wiring defect in the corrected
smoke. The candidate native operator is compiled by `_C.abi3.so` and registered
under `torch.ops._C`, but the vLLM guard, live consumer, and focused test all
used `torch.ops._xpu_C`. The test had hidden the error by installing its fake
operator in that same wrong namespace. A clean-process registration check now
proves:

```text
native_namespace True
wrong_namespace False
```

vLLM commit `19c44a739` changes only those three namespace references and the
test fake. Independent audit then confirmed that XPU platform initialization
already imports `_C` before model construction; commit `bfd3f21d7` therefore
restores the native-op guard to the early fail-closed contract block and leaves
the post-layer message as activation evidence only. The same audit caught that
this returned-Tensor operator lacked a FakeTensor implementation required by
the compiled model path. Commit `1ddb7d6bb` conditionally registers the
`_C` fake and returns an empty tensor matching the mutated residual's shape,
dtype, and device. A direct FakeTensor dispatch check passes at
`[12,3072]` BF16. The focused suite remains `3 passed`, Ruff and `compileall`
pass, and selector-off behavior is unchanged.
This is recorded as a **new v2 wiring candidate**, not a retry or
reinterpretation of an endpoint result. Since
neither failed artifact reached health or a request, one fresh non-scored v2
smoke is authorized after a new runtime lock and independent source audit. The
original gates and stop rules apply without relaxation: the first v2 smoke that
reaches model execution stands, and no scored leg is authorized unless it
passes exactness, topology, cache-zero, marker, and teardown gates.
