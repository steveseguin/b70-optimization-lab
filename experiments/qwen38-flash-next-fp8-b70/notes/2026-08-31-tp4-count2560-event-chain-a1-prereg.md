# Qwen3.8 Flash-Next TP4 clone-elision/event-chain A1 preregistration

Date: 2026-08-31
Status: frozen before GPU execution

## Question

The accepted eager TP4 MTP0 target lane performs 97 BF16 `[1,2560]`
reductions per generated token. The current XPU communicator clones each input
and submits an ordinary in-place XCCL reduction. A DeepSeek eager component
gate previously showed that a finite same-queue event chain can avoid several
milliseconds of host-side submission cost. Does the same default-off mechanism
jointly with clone elision provide a repeatable, exact, and large enough win for
this Qwen lane to justify one later full-model endpoint test?

This is a component test, not a model-throughput result. It does not load the
checkpoint, modify the accepted runtime, change a protected speed claim, or
authorize promotion.

## Frozen implementation

- oneCCL base `9636514e6f9b885cfeecca141811433e2cb8affb`, built in an
  isolated NVMe tree with the one-file default-off patch
  `patches/qwen38-flash-next-fp8-b70/oneccl/0001-Add-Qwen-count2560-event-chain.patch`;
- oneCCL SHA-256
  `164091ac6aced05bfc658ae1e1cd722153f099714e9cee6f437c62bdd3731c1c`;
- XPU-kernel head `e421889999bc1e5a5f11044d14548b9afdba644d`, preserved as
  `patches/qwen38-flash-next-fp8-b70/vllm-xpu-kernels/0008-Add-Qwen-TP4-event-chain-bridge.patch`;
- staged `_xpu_C.abi3.so` SHA-256
  `776a080846bfe26c92f10ecb80982f45137802cf10af4a7d66b9c0d6af1cd339`;
- the ordinary control and direct candidate both load that same candidate
  oneCCL and XPU extension. The timed candidate deliberately replaces both the
  production out-of-place clone and ordinary submission with the guarded
  direct event chain. This is a combined candidate, not attribution to either
  sub-mechanism alone;
- the exact source deltas and isolated native-build identities are bound by the
  [build receipt](../data/20260831-tp4-count2560-event-chain-a1-build-receipt.json).

The bridge accepts only TP4, BF16 SUM, exact count 2560, Arc, aligned distinct
buffers, and the recorded in-order queue/context/device. A normal reduction
outside the timed window primes the communicator. The feature is inert unless
`B70_ONECCL_ENABLE_Q38_COUNT2560_EVENT_CHAIN=1` and the new XPU operation is
explicitly called.

## Frozen workload and gates

Each fresh four-rank process performs 8 warmup cycles and 40 paired measured
cycles, alternating AB/BA order. A cycle follows production order: each of 97
reductions is immediately followed by its dependent HC consumer. Ordinal 0 has
no HC consumer; ordinal 2 is the sole plain `hc_combine` at the PLE boundary;
the other 95 use unchanged `hc_combine_norm`.

Every one of the 40 measured epochs uses a mutually distinct integer-valued
BF16 corpus whose exact four-rank SUM is independently computed. Control and
candidate must each equal that analytic oracle, every collective element must
match between them, and all 191 tensors returned by the 96 consumer invocations
must be bitwise equal on every rank. Final hashes must also agree across ranks
and both fresh processes. An untimed Kineto receipt on every rank must show the
intended `Rt64_128_PCIE` protocol and must not show the neutral `Rt64_PCIE`
path.

Each replica independently must satisfy all of:

- median saving at least 4.0 ms;
- p90 saving at least 3.0 ms;
- median saving at least 10%;
- at least 32 of 40 paired epochs faster;
- median saving at least 3.0 ms in each AB/BA order stratum.

The CLI cannot alter those values. Output, rank sidecars, and protocol traces
are no-clobber. Exact source, stage, extension, oneCCL, kernel-bundle, Python,
and torchrun hashes are fail-closed. A timeout, signal, or abnormal exit aborts
the campaign before replica 2 and must leave no surviving gate or torchrun
process.

## Frozen interpretation

- Both replicas pass: the candidate may receive one separately preregistered
  full-endpoint A/B. It is not yet a speed claim.
- Any correctness failure: reject it.
- Either replica misses any performance gate: close it without a full model
  load.
- Do not lower a threshold, add replicas, reboot, or load the checkpoint to
  rescue a miss.

Independent review found and corrected the initial gate's consumer ordering,
PLE ordinal, mutable-threshold, unpaired-statistics, hash-binding, no-clobber,
static-corpus, missing-oracle, protocol-receipt, native-source preservation,
and abnormal-exit defects. A final review of this corrected packet is required
before execution.
