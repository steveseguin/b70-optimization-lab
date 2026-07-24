# Laguna M=8 gather-sharded source, build, and IR checkpoint

Date: 2026-07-24 America/Toronto

Status: source/build/device-IR pass; Stage 0 remains incomplete pending the
fixture/corruption tooling and frozen Phase-A/Phase-B packets. No candidate
primitive, XPU tensor, model, endpoint, prompt, generation, network request,
payload, submission, or reboot occurred.

## Outcome

The preregistered standalone `MoeGather` occupancy retile is implemented as a
separate default-off kernel and compiled successfully from the approved record
base. CPU source/oracle checks pass, the final linked module is hash-sealed on
internal NVMe, and the candidate and incumbent retain the same visible
BF16-conversion and FP32 multiply/add structure in final linked SPIR-V.

This is not a correctness or performance result. The final image still permits
`NSZ` and reassociation on both paths, so only the later four-card raw-bit
component gate can establish exactness.

## Frozen source identity

- preregistration commit:
  `89364f5542a661f297b187f96006bd8979b11d0f`;
- preregistration SHA-256:
  `21e5298c0ae00b0c3ddd154911e4c280ac8ad76e2a47c90d3b2265cba7959330`;
- unchanged approved vLLM base:
  `8936aac144929190c1e53f8b8624ca397ce16f5b`;
- approved XPU-kernel base:
  `b6076ce1249ffee0e30bee528f4cd15c3bffb234`;
- candidate XPU-kernel commit:
  `7e6a74026a2a4370abcb7973d28bbc9d1ddd1be6`;
- candidate parent:
  `b6076ce1249ffee0e30bee528f4cd15c3bffb234`.

The candidate is therefore a direct child of the approved kernel record. Its
isolated worktree is
`/home/steve/src/laguna-xpu-kernels-gather-sharded-20260724`; the untouched
vLLM record worktree is
`/home/steve/src/laguna-vllm-gather-sharded-20260724`.

The native specialization fixes:

```text
tokens                 8
top-k                  10
hidden                 3072
shards/token           6
work-items/shard       64
elements/work-item     8
columns/shard          512
workgroups/launch      48
SIMD32 subgroups       96
```

It accepts no route-map argument and resolves only
`route = token * 10 + slot`. The generic gather remains byte-identical to the
record base and handles every noncandidate call. The ordinary separate
`laguna_m8_scale_add` remains unchanged.

## Pre-freeze identity correction

An independent audit caught one real dispatch-identity bug before this
checkpoint. The first draft required the synthetic component label
`DRAFT_FLASH_DEPTH=7`; the service launcher actually consumes
`LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS=7`. Commit `7e6a740` requires the latter
and removes the former. The mapping is named a frozen candidate environment,
not a complete service identity.

The later campaign packet must separately bind and validate the fields that
cannot be proved inside this Python wrapper: target/draft model paths and
revisions, tokenizer, matched INT4 draft, standard rejection, greedy sampling,
depth 7, BF16 KV cache, eager mode, disabled async scheduling and prefix
caching, TP4/EP4/DP1/PP1, one active request, block size 64, context 8192,
source commits, module origins, and binary hashes.

## CPU-only checks

The final candidate commit passed:

- 8/8 static source/base-preservation checks;
- 3/3 full-shape and edge-case CPU arithmetic oracles;
- Ruff;
- Python AST parsing;
- oneAPI 2025.3 `clang-format --dry-run --Werror`;
- `git diff --check`;
- direct-parent and clean-worktree checks; and
- two independent source reviews with no remaining build blocker.

The CPU oracle imported Torch only on CPU and asserted that
`torch.xpu.is_initialized()` remained false before and after the tests.

The separate final-SPIR-V inspector and its mutation suite pass 9/9. The
machine-readable report is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/binaries/
gather-sharded-7e6a740-20260724/device-ir-evidence.json
SHA-256 e6fefcaacc3253718c8a21ee6eae2544131fee613099ebf91cac9ddbdebd0505
```

## Build identity

The narrowest available project target, `_moe_C.abi3.so`, was configured and
built with one job on internal NVMe:

- compiler: Intel oneAPI DPC++/C++ 2025.3.3;
- build type: Release;
- Python: `/home/steve/.venvs/deepseek-v4-xpu/bin/python` 3.12.13;
- oneDNN source commit:
  `80afa71049cd69a3df32adcccb623b12cd7baa22`;
- local oneDNN override plus `FETCHCONTENT_FULLY_DISCONNECTED=ON`;
- empty `VLLM_XPU_AOT_DEVICES` and `VLLM_XPU_XE2_AOT_DEVICES`;
- `MOE_KERNELS_ENABLED=ON`; and
- TLA, basic, FA2, GDN, MQA, MHC, XPU-specific, allocator, XE2, and
  XE-default targets all off.

The final configure explicitly supplied
`CMPLR_ROOT=/opt/intel/oneapi/compiler/2025.3`. Two earlier configure-only
attempts are preserved: the versioned environment helper did not export the
CMake variable, so CMake printed `/include` paths. No compilation occurred
until the corrected `configure-final.log`.

The built and staged copies are byte-identical:

```text
file    _moe_C.abi3.so
size    11127920 bytes
sha256  3a16e85f7b6f324246f89e03d8aa89c37f0d6097c59d0a323ab2822dccd6d99f
```

The artifact root is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/binaries/
gather-sharded-7e6a740-20260724
```

The build log contains exactly nine MoE translation units and one link. The
module was not imported.

## Device-IR evidence

The exact device bitcode unbundled from the built `moe_gather.cpp.o` is
byte-identical to the same-flags save-temporary bitcode:

```text
d7bde207300e7a2a1fb630ad440f08d60f70fdaf8c6c0aea327f02aac7d4d71b
```

The linked `_moe_C` contains 21 concatenated SPIR-V modules in its
`OFFLOAD_DEVICE_CODE` section. The gather module begins at byte 4,250,272 and
has 232,424 nonpadding bytes. Its retained identities are:

```text
gather linked SPIR-V
114a2c823ce5ea838bd1ba5857ece2a97962aebadfda1e64a0c5553ab26413cc

spirv-dis --raw-id assembly
3cdfae4c9a49558f8c22fe01b9f22dc770f9d02d01da4257e35efcefc2d23687
```

The final assembly proves:

- candidate entry wrapper `%8686` calls named implementation `%23` once;
- incumbent BF16/top10/EPI8 wrapper `%8908` calls `%3607` once;
- both entry points declare `ContractionOff` and `SubgroupSize 32`;
- candidate `%136 OpFMul` feeds `%140 OpFAdd`, which loads and stores the same
  loop-carried FP32 accumulator element;
- incumbent `%3725 OpFMul` feeds `%3729 OpFAdd` with the same dependency;
- both use the same BF16-to-FP32 and FP32-to-BF16 helpers;
- neither implementation contains a fused multiply-add instruction;
- both arithmetic pairs carry the identical
  `NSZ|AllowRecip|AllowContract|AllowReassoc` decoration; and
- the candidate has two ten-bound loops (weight staging and slots), while the
  generic path has three (route-map staging, weight staging, and slots).
  Both have three eight-bound loops.

`ContractionOff` and the absence of an already-fused operation clear the
specific asymmetric-FMA concern. They do not prove final device bits because
the matching `AllowReassoc` and `NSZ` permissions remain and the two kernels
have different address/control structure. The later raw-`uint16` XPU
comparison is authoritative.

Two compiler-tool limitations are preserved rather than hidden:

1. `icpx -fsycl-device-only -S -emit-llvm` returned
   `IR output is not supported`; exact object bitcode was instead unbundled.
2. Intel `llvm-spirv --to-text` crashed on the whole concatenated linked
   section, and SPIRV-Tools validation rejected an Intel alias declaration.
   Splitting the exact gather module and using `spirv-dis` succeeded. These
   were static-tool failures, not candidate execution.

## Remaining authorization boundary

This checkpoint does not complete Stage 0 and authorizes no candidate-bearing
execution. Before any candidate primitive:

1. generate and independently reanalyze the fixed 256-pre/32-post fixture
   corpus, including all 65,536 BF16 encodings and the frozen FP32/route-mask
   classes;
2. complete CPU one-field corruption tests for every selector and runtime
   contract;
3. validate the new standalone operational idle parser against the installed
   `device_util_by_proc_list` schema;
4. freeze and commit both Phase-A timing/exactness and conditional Phase-B
   counter tools and packets together; and
5. bind those packets to the exact source, binary, fixture, card, and
   final-SPIR-V identities above.

The gather-finalize packet remains terminal and must not be modified, rerun,
or used as evidence for this lane.
