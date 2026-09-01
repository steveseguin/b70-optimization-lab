# Qwen3.8 Flash-Next HC-SiLU A2 std::exp preregistration

Date: 2026-08-31
Status: built and statically frozen; one-card execution requires a fresh boot

## Question and sole treatment

A1 found one non-NaN BF16 bit mismatch in raw-input chunk
`0x4100–0x423f`. A2 asks whether matching the exact sigmoid arithmetic of the
installed Torch `2.11.0+xpu` reference closes that correctness gap while
retaining the A1 component speed opportunity.

A2 is A1 plus one layered patch. It adds `<cmath>` and replaces `sycl::exp`
with float `std::exp` in `one / (one + exp(-scaled))`. The installed Torch Git
identity is `70d99e998b4955e0049d13a98d77ae1b14db1f45`, with torch-xpu-ops pin
`de4f698b84142e660d5238e02e067182e39641ca`; its float sigmoid uses that same
expression. Scaling, multiplication, BF16 conversion, output allocation,
dispatch guards, queue choice, launch geometry, default-off selector, and
fallback behavior remain unchanged. No global precision, fast-math, or native
math flag was added.

The A1 and A2 native source hashes are respectively `1fb1af69...` and
`0ec0403c...`. A directory comparison found exactly one changed source file,
and reverse-applying patch `0010` passes. Independent source review found no
blocker.

## Frozen build and gate

The isolated component build uses oneAPI 2025.3.3 with both compiler discovery
roots pinned to `/opt/intel/oneapi/compiler/2025.3`. The installed DSO SHA-256
is `1d7cd1a21c7c2d8ecd0c0b0ef38b549adc133ab12683c0c33eb8d210e5d48e49`;
it requires only `libsycl.so.8` and has runpath `$ORIGIN`. The component-only
runtime is `/mnt/fast-ai/qwen38-build/runtime-q38-hc-silu-a2-stdexp`, with
manifest SHA-256 `be791a78...`. It cannot serve the full model.

The A2 gate first runs the exact 320-pattern failed region, requires exact
non-NaN bits and equal NaN classification, records raw input/reference/
candidate bits on any failure, checks the production stride and input
immutability, and requires 100 identical candidate calls. Only then does it
invoke the unchanged A1 ladder:

1. all 65,536 BF16 encodings across 205 production-stride calls;
2. selector-off and fallback parity, input immutability, and 100 repeats;
3. exactly five control kernels versus one named candidate kernel;
4. the unchanged 60-cycle `C-A-A-C` timing gate;
5. exact four-B70 compute/free-memory and bounded kernel-journal postflight.

The runner binds the A1 runner/gate/patch, A2 corrective patch, A2 gate,
component DSO/runtime manifest, unchanged vLLM dispatch source, compiler ABI,
evidence mount, locks, memory floors, and fresh-boot lifecycle. It hard-rejects
the A1-attempt boot `a37222ff-628d-4d0a-8a84-37e086ad90dc` and refuses to
overwrite its distinct A2 evidence root.

## Frozen interpretation

- Any mismatch, repeat, dispatch, profile, timing, teardown, four-card, or
  journal failure closes A2 as a component negative and stops the chain.
- A pass authorizes only the already-frozen same-boot CPU-affinity component;
  it does not authorize an endpoint or throughput claim by itself.
- Only if both components pass may A31 become that boot's sole full-model load.
- A31 remains a candidate requiring matched control and repeat before
  promotion even if its full battery passes.
- The protected TP4 MTP0 `5.515783 tok/s` and MTP4 `20.727176 tok/s` results
  remain unchanged under every outcome.

The complete machine-readable build receipt is
`data/20260831-q38-hc-silu-a2-stdexp-build-receipt.json`.
