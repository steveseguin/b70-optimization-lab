# Bounded registered-reference tie sort

Research candidate; canonical installation is owned separately by the coordinator.
The goal is to recover the CPU reference's complete 512-expert permutation on
ties without a per-layer host round trip. A selected-tie-only RouteFast2 integration
is a later step. Changing the ordinary non-tie route or the probabilities is not
part of this candidate.

`reference_sort.hpp` matches the registered GCC 13 libstdc++ comparison-only sort
with 18 fixed stack frames (216 bytes) and caller-provided indices (2048 bytes for
512 experts). It implements median pivoting, partition, final insertion, and heap
fallback, without recursion, allocation, or exceptions. Equivalent scores have
the reference's unstable permutation; they are not sorted by expert ID.

## Completed CPU gate

Both optimized and ASan+UBSan builds passed the same gate:

- 30,302 complete-permutation comparisons against actual `std::sort`;
- 2,000 additional explicit depth-0/1/2 comparisons against libstdc++ internals;
- 148 real-vector cases, including 48 raw native router rows, their 48 production
  host probability replays, 48 captured CPU probability rows, and four saved
  native/ggml replay vectors whose top ten also match the saved real ggml IDs;
- all sizes 0–512, duplicate-heavy randomized distributions, monotone and
  median-pivot adversaries, all-equal, signed-zero, subnormal and neighboring-ULP
  cases; 2,489 natural heap fallbacks, maximum 17 pending stack frames;
- output canaries and six invalid-input refusals; sanitizer stderr empty.

See `cpu-gate.json` for commands, source/compiler hashes, results, and artifact
paths. This establishes the tested CPU compatibility; it does not prove model
quality generally or establish a speed improvement. The source fixture relies
on GCC 13 internal helper names specifically to cover forced heap fallback.

## Completed device gate (launched by coordinator)

Offline AOT compilation for `intel_gpu_bmg_g31` succeeded with oneAPI 2026.0.
`device-build.json` records the exact compile command and binary/input hashes.
The candidate author did not launch this executable or open a GPU. The coordinator
subsequently ran it once on physical card `0000:27:00.0`: all 262,144 indices
matched, with zero invalid rows/canary errors and bitwise unchanged input. Unit
exit status was zero; passive postflight found no holders or changed kernel
journal hash. See `device-result.json`. An earlier passive admission refusal,
before any device launch, is retained in that record.

The probe has 512 independent work items, each with a private 512-index array and
18-frame sort stack. It allocates exactly **2,103,296 explicit device bytes**:
1,048,576 bytes input, 1,052,672 bytes output including canaries, 2,048 bytes status.
Compiler-generated private storage/spills and runtime allocations are additional;
this number is not peak device memory usage. It checks all 262,144 output indices
against host `std::sort`, two canaries per row, status, and bitwise unchanged input.

`prepare_probe.py` prepared a 1,048,576-byte input batch with 48 native production
host probability replays, 48 actual CPU probabilities, four saved tie vectors and
412 deterministic structural/random cases. `input-manifest.json` binds each row,
the authenticated original receipts, and the pinned real ggml replay binary. The
native probability rows are host replays from captured native router scores,
not new GPU probability captures. Synthetic cases include signed zero and
subnormal keys; not all synthetic keys are normalized probabilities.

The coordinator used the following probe invocation (complete bounded unit,
environment and command are in `device-result.json`):

```sh
env FilterBdfPath=0000:27:00.0 OWNRT_REFERENCE_SORT_PROBE=1 \
  /dev/shm/sc117-reference-tie-sort-device-20261028-r1/probe \
  /dev/shm/sc117-reference-tie-sort-device-20261028-r1/inputs/input.f32 \
  /dev/shm/sc117-reference-tie-sort-device-20261028-r1/device-card27-r1
```

The executable requires a fresh output directory and verifies the selected
device's physical PCI address before allocating. The coordinator supplies the
normal oneAPI runtime environment and monitoring. There is no retry loop or model
load. Failure must not trigger automatic retries or host/device resets.

## Remaining decisions

The private-array probe establishes the tested device semantics only. Before runtime use,
measure the actual selected-tie RouteFast2 path; private storage could be costly.
An explicit caller-provided frame buffer and local-memory indices are possible
later if needed. The current helper's frames remain private; no SLM performance
claim or integration is present. The registered reference's tie policy is specific
to this libstdc++ build, as explained in `PROVENANCE.txt`. The proposed integration,
including a cheaper exact selected-tie detector, is in `integration-design.md`.

## Actual RouteFast2 overlay gate

`prepare_route_overlay.py` creates a pinned, default-off source overlay. It
preserves the original `RouteFast2` class exactly, adds `RouteReferenceTie2`, and
selects it only with `OWNRT_REFERENCE_ROUTE_TIE_SORT=1`. Unsupported enabled route
treatments refuse early. The bounded local-workspace helper passed another
12,512 ASan+UBSan comparisons with index and frame canaries.

The coordinator ran `route_probe.cpp` once on card27. The probe includes the
complete pinned adapter source and checks both MERGE modes, two/four output
geometries and 64-row batches (48 authenticated native rows plus 16 adversaries).
All 512 native probability words per row and all selected weight words stayed
exact; selected IDs matched `std::sort` of the captured native probabilities.
There were 276 changed slots across the four matrix cells, zero mismatches,
and passing inactive/error, nonfinite and distinct-raw/equal-probability refusal
checks. Capture instrumentation was independently neutral for both versions.
Explicit device allocation was 282,704 bytes; the unit exited zero with clean
passive postflight.

`route-result.json` binds the actual gate to all three proposed installed source
paths and their hashes. `route-overlay/` preserves the exact patch, input manifest,
compile/link identity and failed unlaunched first capture compile. That first
instrumentation exceeded the 1024-byte kernel capture guard; the passing version
uses the existing unused scratch binding for its probability output. The passing
probe matches production's precise per-source compile and bare final device link.

The candidate author did not modify canonical runtime or launch a GPU. The
coordinator owns installation and the matched model gate. No runtime throughput
claim follows from either isolated correctness probe.
