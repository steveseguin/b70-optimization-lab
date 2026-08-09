# Canonical per-vector Q8 c2 control

Date: 2026-08-09

Status: source built and independently reviewed; no GPU result yet.

## Objective

Test whether the repeatable, workload-sensitive slot-1 forced-tail behavior in
the Qwen3.6 27B Q8 c2 packets is caused by the two Q8 matrix paths that change
with the M=2 layout. This is a causal correctness control, not a proposed
performance optimization and not a natural-serving quality fix.

The incumbent uses different arithmetic paths for the two observed layouts:

- flattened `[K,2,1,1]` Q8 projections use reordered multi-column MMVQ;
- recurrent `[K,1,2,1]` `ssm_out` projections use reordered DMMV once the
  weights have been bootstrapped.

The default-off control sends both layouts through two invocations of the
existing reordered single-column MMVQ path. It changes dispatch only; it adds
no arithmetic kernel.

## Source identity

- base: `15586e2d7165570fb3aa7c26e0d442e289ef69de`;
- experiment commit: `109eee6fc36fcd073996c4c1eac7e22aa4c711da`;
- changed source: `ggml/src/ggml-sycl/ggml-sycl.cpp` only;
- tracked-diff SHA-256:
  `4876278ce431e6f3417b6a5c87ddc63585a000148582ddea02b77e99591a722e`;
- source-file SHA-256:
  `ffcbe9c01b239407d68fdfea6cb982116d7ba4f22132ee671dc22cee09ef811f`;
- patch: [`../../../patches/qwen36-27b-q8-gguf-b70/0001-sycl-add-canonical-per-vector-Q8-c2-control.patch`](../../../patches/qwen36-27b-q8-gguf-b70/0001-sycl-add-canonical-per-vector-Q8-c2-control.patch),
  SHA-256
  `afb4ebe4c0421cfbb1294121cb3d69849ba7b3a740211c6736fc656a62d6d693`.

The Release/F16/GRAPH/DNN IntelLLVM 2026.0 build completed. The candidate
`libggml-sycl.so.0.18.1` is 86,890,624 bytes with SHA-256
`f0a9e736dde321f72fceb14db6fb1410a9ad090380a3cf8ed7c591e949c94305`.

## Fail-closed selector and route proof

The selector is `GGML_SYCL_Q8_0_C2_CANONICAL_MMVQ=0|1` and defaults off.
Enabled operation requires `OPT=1`, runtime graph off, and
`PRIORITIZE_DMMV=0`. Recognized Q8_0/F32 flat or recurrent M=2 layouts abort
instead of silently falling back if tensor layout, contiguity, buffer,
reordering, quantizer, or two-call invariants are violated.

Candidate model evidence must retain both per-layout first-hit markers and a
final summary satisfying:

- flat and recurrent dispatch counts are both positive;
- each flat dispatch suppresses the multi-column route;
- each recurrent dispatch suppresses DMMV;
- every controlled dispatch sees reordered weights ready;
- exactly two single-column MMVQ calls occur per controlled dispatch;
- no violation marker or nonzero violation count occurs.

## Causally narrow runtime bundle

The candidate runtime manifest is
[`../runtime-manifest-canonical-q8-c2.json`](../runtime-manifest-canonical-q8-c2.json).
The hybrid bundle keeps the validated baseline `llama-server` and all seven
other baseline origin DSOs byte-for-byte. Only `libggml-sycl.so.0.18.1`
differs. The launcher must apply and attest the manifest's origin-first loader
policy because the original ELF RUNPATHs point at their build worktrees.

Bundle:
`/mnt/fast-ai/runtime/llama.cpp-15586e2d-q8-c2-canonical-109eee6f-hybrid`

USB archive:
`/mnt/usb-models/models/runtime-builds/llama.cpp-15586e2d-q8-c2-canonical-109eee6f-hybrid.tar.zst`

Archive SHA-256:
`ad41739b584535526ed818f23b74b13d9f2b6942c3b8c36f2b98994e67eb4eec`

## Required gates

1. Offline manifest, loader, selector, parser, and lifecycle checks.
2. A component GPU gate at the real Q8 `ssm_out` weight shape
   `[6144,5120]`, using distinct A/B inputs, both M=2 layouts, both bootstrap
   orders, and bitwise comparison with separate M=1 calls.
3. A sealed candidate-runtime-matched c1 oracle for every c2 prompt.
4. A two-wave four-GPU baseline/candidate crossover that swaps treatment on
   the same cards and proves candidate route activation.
5. Full candidate c2 token equality to its matched c1 oracle. The historical
   B71 and A96 first splits are baseline landmarks only; later forced-tail
   hashes are not success metrics.

Any mismatch before the separately measured natural-answer boundary is a
quality regression. A synchronized natural-stop c2 pair remains a separate
serving-relevance gate. No speed, quality, or causal claim is valid until the
staged GPU evidence is sealed.
