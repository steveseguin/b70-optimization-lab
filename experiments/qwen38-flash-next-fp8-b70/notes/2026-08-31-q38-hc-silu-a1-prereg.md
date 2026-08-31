# Qwen3.8 Flash-Next HC-SiLU A1 component preregistration

Date: 2026-08-31
Status: built and statically frozen; accelerator execution requires a fresh,
attended boot

## Question

A28 attributes `0.591987 ms/token` and five device launches per call to the
Qwen4Exp HC-SiLU decomposition at the exact target-decode shape. It runs 97
times per generated token. A1 asks whether one exact-shape native XPU kernel
can preserve every BF16 result while materially reducing that component cost.
This is a bounded component question, not a model-throughput claim.

## Frozen treatment

- vLLM base `797769b34b6db5c934609b75dc04cc61ec66e5f9` plus patch
  `0034-Add-default-off-native-XPU-HC-SiLU-dispatch.patch`;
- kernel base `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4` plus patch
  `0009-Add-exact-Qwen4Exp-HC-SiLU-XPU-kernel.patch`;
- selector `VLLM_XPU_QWEN4_EXP_HC_SILU`, false by default;
- candidate dispatch only for XPU BF16 `[1,320]`, inner stride 1, and
  `hc_count=4`;
- one native pointwise submission, distinct contiguous output, no input
  mutation, no explicit queue barrier;
- every other shape, dtype, stride, or HC count retains the prior Torch path;
- enabling the exact selector without the native schema fails clearly rather
  than silently running the control.

The component-only DSO is
`/mnt/fast-ai/qwen38-build/runtime-q38-hc-silu-a1/vllm_xpu_kernels/_xpu_C.abi3.so`,
SHA-256
`f3e4735c4046b7e15f4e5d597c01b73e6647ff2a8f7b9a2d577518479379841a`.
It links only the accepted `libsycl.so.8` ABI. This runtime is deliberately
not full-model-capable; a passing component result would still require the
change to be rebuilt into the complete accepted runtime before any endpoint
arm.

## Prelaunch correction

The first successful compile was rejected without touching an accelerator.
CMake had followed `/opt/intel/oneapi/compiler/latest` for SYCL discovery even
though `icpx` was pinned to 2025.3, producing a DSO that required both
`libsycl.so.8` and `libsycl.so.9`. The accepted build sets both environment and
CMake `CMPLR_ROOT` to `/opt/intel/oneapi/compiler/2025.3`; `readelf` now shows
only `libsycl.so.8`. The rejected installed DSO hash
`700d47f7f8124f6df90e81dda2b6ac7c807fec52dedc1ad616ebafdf5db1737c`
is recorded only as a negative build identity and must never be run.

## Frozen gate

The runner is `tools/run-q38-hc-silu-a1.sh`; its canonical self hash is
`464a12832c9f423aab7a064340aa96feaefc39de19511e7ab853e84b99efdff1`.
It hard-rejects boot `c36480de-9150-4182-9888-08c85d2d9de4`, verifies the
source patches, snapshot files, component DSO, complete runtime manifest,
single-SYCL linkage, four-card topology, authenticated evidence drive,
memory/swap floors, idle model state, and atomic shared benchmark, GPU, full-load,
and component-chain locks before exposing one B70. The component state is
claimed before device discovery and remains fail-closed unless the entire gate
and exact four-card postflight pass.

The Python gate then requires:

1. All 65,536 BF16 input bit patterns in 205 exact `[1,320]` calls with the
   production `[336,1]` stride. Every non-NaN output bit must equal the Torch
   reference; NaN inputs/results require identical NaN classification. Any
   finite mismatch closes the candidate.
2. Selector-off parity, out-of-contract fallback parity, unchanged input, and
   one common candidate/reference output hash across 100 repeats.
3. Kineto evidence of exactly five control kernels and exactly one candidate
   kernel, named for HC-SiLU and with no barrier kernel.
4. Eight warmup windows per arm, then 60 `C-A-A-C` cycles of 97 calls/window,
   timed with XPU events and one host synchronization after each window. The
   candidate must save at least 30% at the aggregate median, have a
   nonnegative aggregate p90 saving, and have nonnegative paired saving at
   p10 (so at least 90% of paired windows do not regress).
5. Complete teardown, bounded exact ordered four-BDF rediscovery, a bounded
   four-card arithmetic/free-memory probe, and a bounded kernel-journal window
   with no reset, fault, timeout, device-loss, or hang signature.
6. Atomic no-clobber evidence and a hash manifest covering every postflight
   receipt.

## Frozen interpretation and lifecycle

- Any correctness, repeatability, dispatch, launch-count, or timing failure is
  a component negative. It authorizes no endpoint and changes no result.
- A pass authorizes only design of a default-off full-runtime endpoint arm.
  It does not prove or project endpoint tok/s.
- The protected target-only `5.515783 tok/s` and MTP4 `20.727176 tok/s`
  results remain unchanged under every outcome.
- No accelerator work and no reboot are authorized on the current boot.
- On the next attended fresh boot, run HC-SiLU A1 first. Only if it passes and
  the device postflight is clean may the already-frozen CPU-affinity component
  run; only if that also closes cleanly may A31 be the boot's sole full-model
  load. Any component fault stops that chain.

The complete build receipt is
`data/20260831-q38-hc-silu-a1-build-receipt.json`.
