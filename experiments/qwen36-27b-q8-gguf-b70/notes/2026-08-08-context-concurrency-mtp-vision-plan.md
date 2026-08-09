# Qwen3.6 27B Q8 context, concurrency, MTP, and vision plan

Date: 2026-08-08

## Decision

The selected optimization baseline is the target-only Unsloth
`Qwen3.6-27B-Q8_0.gguf` already pinned and validated in this lane. The desired
deployment shape is four independent one-GPU processes, one per B70. Text-only
optimization comes first. Vision is a later bonus. MTP is optional and should
be judged only after long-context and ordinary server-slot concurrency are
measured.

This changes the future capacity target, not the completed baseline result:
32K F16 KV remains the validated reference, while 100K or more is now a stretch
goal under a distinct Q8-KV identity.

## Slot semantics

In the pinned llama.cpp runtime, `-c` is the total context/KV budget shared by
all `-np` server slots. Each slot receives the padded total divided by the slot
count. Therefore:

- one 32K slot is `-c 32768 -np 1`;
- two 32K slots are `-c 65536 -np 2`;
- `-c 32768 -np 2` provides only 16K per slot.

Use total-context values divisible by `256 * np`; otherwise the runtime's
per-sequence padding can change the effective allocation. Qwen3.6 27B declares
a native 262,144-token training context, so the planned 128K-per-slot ceiling
does not exceed the model's declared limit.

Four processes at `np=1` already provide four cluster-wide concurrent requests.
Using `np=2` on all four cards would provide eight, but is a separate memory,
quality, and aggregate-throughput identity.

## Measured anchor and modeled envelope

The validated `-c 32768 -np 1` F16-KV run retained a 2,048 MiB KV allocation,
a 149.62 MiB recurrent-state allocation, and 4,077 MiB reported free after
load. The architecture and retained allocation give exact cache slopes for
this runtime:

- F16 K+V: 64 KiB per total context token;
- Q8_0 K+V: 34 KiB per total context token.

Recurrent state scales with the slot count: `np=2` adds approximately
149.62 MiB versus `np=1`. The following free-memory estimates are anchored to
the measured 32K run and account for KV and recurrent-state deltas. They do not
include every possible allocator/workspace change, so they are planning values,
not fit results. Here, 100K means 102,400 tokens per slot.

| Per-slot context | F16, one slot | F16, two slots | Q8_0, one slot | Q8_0, two slots |
|---|---:|---:|---:|---:|
| 32K | 4,077 MiB, validated | 1,879 MiB, predicted viable | 5,037 MiB, predicted viable | 3,799 MiB, predicted viable |
| 64K | 2,029 MiB, predicted viable | -2,217 MiB, no-go | 3,949 MiB, predicted viable | 1,623 MiB, borderline |
| 100K | -275 MiB, no-go | -6,825 MiB, no-go | 2,725 MiB, predicted viable | -825 MiB, no-go |
| 128K | -2,067 MiB, no-go | -10,409 MiB, no-go | 1,773 MiB, likely viable | -2,729 MiB, no-go |

No predicted row is a validation result. A server merely reaching readiness is
also insufficient: each slot must be filled near its declared limit and decode
a suffix without truncation, layer offload, selector drift, device faults, or
silent context reduction.

Q8 KV can legitimately alter logits. Its gate is deterministic self-replay plus
retrieval and quality evaluation against the F16 reference corpus, not mandatory
token-for-token equality with F16 KV.

## Validation order

1. Retain the DNN-off, OPT-on, F16-KV 32K result as the correctness baseline and
   complete the standard full-512 performance packet before promotion.
2. Prove that four independent `np=1`, 4K services can be resident together,
   fully offloaded, deterministic against one common oracle, and cleanly torn
   down. Do not treat simultaneous rates as isolated single-card scores.
3. Establish Q8-KV behavior at one slot/32K, including the expected 1,088 MiB KV
   allocation, self-replay, retrieval, and quality gates.
4. Validate F16 one-slot/64K and simultaneous two-slot/32K. For two slots, fill
   both concurrently; two sequential requests do not prove the allocation or
   scheduler behavior.
5. Climb Q8 one-slot capacity through 64K, 100K, then 128K. Stop at the first
   failed fit, quality, or device-health gate.
6. Test Q8 two-slot/32K, then the borderline two-slot/64K shape. Do not attempt
   the modeled no-go rows.
7. Compare the resulting workload choices: four cluster-wide 100K/128K c1
   requests, or up to eight shorter requests using c2. Choose by aggregate
   throughput and latency, not slot count alone.

Step 2 passed in run
`qwen36-27b-q8_0-four-replica-smoke-20260809T011029Z`: four fully offloaded
replicas generated concurrently, matched the sealed baseline output, and
returned cleanly to idle. The remaining rows and slot shapes are untested.

## MTP and vision boundaries

The future artifacts are identity-pinned in
`optional-artifacts-manifest.json`, but neither is downloaded or validated.

The publisher-compatible vision choice is the F16 projector from the same
Unsloth target repository and revision. Its file is 927,607,360 bytes
(0.864 GiB). Test it only after text optimization; image tokens and projector
buffers require a fresh context/fit envelope.

The safe MTP starting point is Unsloth's integrated Q8_0 artifact. It is
451,320,736 bytes (0.420 GiB) larger than the target-only model before draft KV
and runtime buffers. The publisher's current recipe warns that `-np > 1` and a
vision projector are not supported with MTP. Honor that stricter boundary:
start at `np=1`, no projector, and require exact target correctness, retained
acceptance counters, memory identity, and a real speed win.

MTP and slots solve different problems. Slots improve aggregate concurrency;
MTP attempts to improve decode latency/throughput for a request. If Q8 KV gives
enough per-card concurrency at the desired context, ordinary slots are simpler.
If 100K or 128K forces one slot per card, MTP may still be valuable—but only if
its extra model/cache footprint fits and its acceptance produces a measured,
correctness-qualified gain.

The current runtime's DNN selector is not an optional feature in this lane: it
failed deterministic greedy replay. Keep DNN disabled unless a newer runtime
passes the existing exact gate.
