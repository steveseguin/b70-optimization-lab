# Qwen3.8 Flash-Next grouped full-serving stage A2 finalizer preregistration

Date: 2026-08-31
Status: frozen before assembly-only execution

## Purpose

A1 compiled the full GDN+grouped runtime successfully but stopped before stage
assembly because its post-build CMake assertions did not describe the activated
venv. A2 performs no configure, compile, model load, endpoint request, GPU
operation, or speed measurement. It validates the immutable A1 build closure,
copies the accepted 18-file stage, replaces exactly the three matched native
outputs, isolates them with `$ORIGIN`, and emits a new external manifest.

## Exact A1 input closure

- A1 driver SHA-256: `b5c29a50c3e6e3b737312fcb2392df9e5b252ef38cd038674c1bf11d4c3bd336`;
- build log SHA-256: `6bcaad7fc092af76468c82ba881a62f3e7e0a9da15b186a7a032e7e99b6871c3`;
- both pipeline exit receipts: `0`;
- CMake cache SHA-256: `94f11621328ba1cc2e46c81c0f6ce15e2bce24695c861375e600b80ac394a698`;
- compile database SHA-256: `04090a0c4a969cd83eedcc2db77c4a108ca241af2cb1cd44c29b54f9e3be5818`;
- `_xpu_C.abi3.so`: `8d6d41a2259b4d4eda53edd9524d113d9190ae1b093a150fd79aa72a5c28dd76`;
- GDN library: `249cd714ca6976346b40a31d260c66149c48e1fe5e7c15df9277db6b155f2ed0`;
- grouped library: `ef81dd90441346671220e55f57e8b1f682394d24aeb70c79c444003e8b40ed64`.

The cache must bind the venv-packaged CMake
`2cb2b2ed8a79eb5612bd611d010c882bf467feb51ad69dac288a245519080408`,
the venv Ninja
`696f9628a79d9ce50314cf9556d7cd1a1d1ec52b8fd52828f6f9db1719565b67`,
the exact pinned oneDNN `PATH`, all original Release/Xe2/B70/SYCL-TLA/GDN/MoE
selectors, and the exact 711-step success receipt. The source heads remain
vLLM `797769b34` and kernels `eeee7d6`; accepted stage manifest SHA-256 remains
`9fa443fdb7a6d0042cf04f859cc6fd6a7bdc09943e16cafb4ea084573c892d2b`.

## Exclusive outputs and gates

- stage: `/mnt/fast-ai/qwen38-build/runtime-serving-hcgrouped-eeee7d6-a2`;
- evidence: `/mnt/fast-ai/qwen38-build/runtime-serving-hcgrouped-eeee7d6-a2-evidence`.

Both must be absent. A1's stage must also remain absent. The finalizer
authenticates both storage roots, rejects active build/model work, verifies
source and A1 artifact closure before and after assembly, and never changes the
accepted stage. It requires exactly 18 output files, byte identity for all 15
untreated files, both native dependencies, `$ORIGIN`, candidate-local GDN and
grouped resolution, and the exact venv SYCL runtime. Validation-only mode is
read-only and creates neither output.

Finalizer SHA-256:
`d23491b666d83e7f57008239cf17d54f11e77674ec25164c8ea560750cfe1e76`.

## Authority boundary

A pass creates only a qualification candidate. It does not authorize an
endpoint, performance, quality, promotion, or causality claim. The separate A2
qualification packet must bind the finalized manifest and binaries and pass
before an A30 endpoint can be frozen.
