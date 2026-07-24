# Laguna M=8 gather/finalize Stage-0 source freeze

Date: 2026-07-24 America/Toronto

Status: **Stage-0 pass; source and CPU-built binary frozen; no XPU
execution yet.**

This implements the default-off post-W2 candidate preregistered in
`2026-07-24-routed-gather-finalize-fusion-preregistration.md`. It keeps the
incumbent route-parallel W2 operation unchanged and replaces only:

```text
MoeGather -> laguna_m8_scale_add
```

with one strict target-verifier M=8 kernel. No endpoint, model load,
generation, benchmark, payload, network access, submission, recovery action,
or reboot occurred during this stage.

## Frozen source identities

- vLLM start:
  `503f7784cf9d1704109b1e4650427fb4f417d604`
- vLLM implementation:
  `5519c08c168838b7e0a418499603b907f127cbf9`
- XPU-kernels start:
  `c59aaadbbfd350c2b5f4ad663e247c2811ae3181`
- XPU-kernels implementation:
  `2020d1921de1af35356fce85a8a2f7703215612c`
- XPU-kernels diagnostic freeze:
  `4772f727590c51b72add79350b913d098cf67872`

Both source worktrees were clean immediately after their focused commits.
The approved public record remains unchanged at vLLM
`8936aac144929190c1e53f8b8624ca397ce16f5b`, XPU kernels
`b6076ce1249ffee0e30bee528f4cd15c3bffb234`, LocalMaxxing
`cmrx6p5dv001bo4017hb7sixz`, and `33.89498511171744 tok/s`.

## Implemented exact contract

The native `_moe_C::laguna_m8_moe_gather_finalize` specialization accepts
only contiguous, aligned XPU tensors with these exact identities:

- BF16 output `[8,3072]`;
- BF16 canonical W2 rows `[80,3072]`;
- FP32 top-k weights `[8,10]`;
- BF16 shared output `[8,3072]`; and
- exactly 64 local experts.

It has no route-map input. For token `t` and slot `k`, it reads only canonical
row `t * 10 + k`; unchanged route-parallel W2 zero-fills remote rows in those
original slots. It performs the fixed slot-0..9 FP32 sum and then explicitly
materializes:

```text
routed_bf16 = BF16(accum_fp32)
scaled_bf16 = BF16(float(routed_bf16) * 2.5)
final_bf16  = BF16(float(shared_bf16) + float(scaled_bf16))
```

The 3,072-wide tail uses two ceiling passes of 256 work-items times eight
elements, with a bounds guard covering exactly columns 0 through 3,071.
Output/input overlap, device, dtype, shape, contiguity, alignment, and local
expert count all fail before the native launch.

The Python integration uses a dedicated two-tensor custom op and a dedicated
API through `RoutedExperts`, WNA16 Marlin, the modular kernel, XPU experts,
and `XpuFusedMoe`. Only an explicit non-null shared output requests the native
candidate, and every layer requires a literal `True` combined-output result.
The runner consumes the shared output exactly once, skips the later
scale/add/shared combine only after that successful result, and retains the
unchanged fixed-rank final reduction.

Runtime guards require the exact target marker, Intel XPU, eager execution,
WNA16 Marlin, TP1/EP4/DP1/SP1 inside the pure-EP MoE configuration, PCP1,
no sequence parallelism, no DBO, no naive dispatch/combine, no pre-reduced
output, no skipped final reduction, routed scale 2.5, no routed transform,
NO_OVERLAP shared execution, and contiguous XPU BF16 `[8,3072]` inputs.
Construction additionally freezes the full record selector/model identity and
missing native symbol. M1-M7, draft, prefill, and generic M8 calls provide no
shared-output signal and retain the incumbent path.

The generic `XpuFusedMoe.apply`, `_apply_ref`, shared-MoE custom-op ABI,
`MoERunner._apply_quant_method`, `_maybe_combine`, `_forward_impl`, and modular
`_fused_experts` methods are AST-identical to their starting versions. The
existing fused-W1 and route-parallel-W2 call nodes and arguments are also
AST-identical to the starting XPU-kernels source.

Before device-packet construction, the native source gained a separate
diagnostic-only companion:

```text
_moe_C::laguna_m8_moe_gather_finalize_diagnostic
```

It instantiates the same inline arithmetic helper and returns the routed,
scaled, and final BF16 boundaries required by the preregistered component
gate. The production schema and call path are unchanged. Its template
instantiation enables three debug stores; the production `<false>`
instantiation compiles those stores out. Strict device, dtype, shape,
contiguity, alignment, and alias guards apply to both entry points.

## Corrections made before source freeze

Static review caught and corrected every issue before a native build or device
action:

1. the first fixed kernel covered only 2,048 of 3,072 columns;
2. the first interface exposed a device route map whose values could not be
   fail-closed without another launch/synchronization;
3. the first pure-EP runtime guard incorrectly expected MoE TP4 instead of
   TP1/EP4;
4. the first runner draft consumed the destructive `SharedExperts.output`
   property twice and also changed the global shared-MoE custom-op ABI;
5. the first kernel selector trapped M1-M7, and a later form would also have
   trapped generic M8 prefill;
6. the first reduction/order validator ran before lazy modular-kernel
   initialization; and
7. the final audit requested an explicit runtime DBO guard.

The frozen source has the corrected ceiling loop, no route-map input,
dedicated two-tensor ABI, one-time shared ownership, `shared_output is not
None` dispatch discriminator, post-initialization runtime validation, strict
WNA16 capability marker, and DBO rejection.

## CPU/static evidence

Final local commands passed:

- Ruff over every changed Python source and test;
- Python AST parsing and `git diff --check` in both worktrees;
- oneAPI 2025.3 `clang-format --dry-run --Werror` over all changed C++ files;
- original XPU-kernels static/value-oracle suite: **13 passed**;
- diagnostic-hardened XPU-kernels static/value-oracle suite: **16 passed**;
- focused vLLM gather/finalize suite: **22 passed**; and
- expanded vLLM integration set with the existing shared-elementwise and
  shared-down tests: **52 passed, 1 explicitly skipped device test**.

The CPU value oracle uses independent `index_select` and reshape-based
canonical addressing models. It checks the ten separate FP32 operations and
all three BF16 stores bitwise, full `[80,3072]` geometry, all 80 canonical
rows, mixed and all-remote zero rows, input immutability, a fixture where slot
reordering changes output, fixtures where either BF16 boundary collapse
changes output, finite BF16 edge values, FP32 zero/subnormal/near-one weights,
and nonfinite classification.

Three independent read-only audits passed after correction:

- native arithmetic, geometry, guards, and remote-row compatibility;
- vLLM ownership, dedicated ABI, WNA16/pure-EP/runtime guards, and no silent
  fallback; and
- cross-repository test/oracle sufficiency and unchanged W1/W2 calls.

Two additional read-only audits passed after adding the diagnostic companion:
one checked native safety and the unchanged production specialization, and one
checked source/test isolation plus unchanged generic, W1, and W2 paths.

## CPU build freeze

The diagnostic source was built with
`/opt/intel/oneapi/compiler/2025.3/bin/icpx`. Build, installed, and archived
candidate bytes matched. The immutable internal-NVMe artifacts are:

- root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/binaries/gather-finalize-4772f72-20260724T075721Z`;
- candidate `_moe_C.abi3.so` SHA-256:
  `6a6794249421aceb51f14980a3e2c0b0a9d7b492abf2f8d25b129b86f099bc5b`;
- incumbent `_moe_C.abi3.so` SHA-256:
  `0057b266d567731a9f9f592cefd9103bbf027ebb83c876d26c17ffb09994a3a0`;
  and
- build-log SHA-256:
  `6428c5afca768d117fca382d890c792ae4c51d111e567307b7ce4473951a2130`.

The ELF contains both production `<false>` and diagnostic `<true>` schemas
and device symbols. Its 16 compiler warnings are the four pre-existing
TopKGating spill warnings repeated for the four architecture targets; neither
gather/finalize instantiation has a compiler-reported spill. An independent
ELF audit passed. The candidate binary has not been imported and no device was
enumerated or allocated.

## Next authority boundary

This note does not authorize a device action. The next step is to prepare and
audit a separate component packet. It must freeze the CPU-built installed
native-library hash/path, both implementation commits, compiler/runtime/driver
and boot identities, physical card mapping, scripts, fixtures, expected
schemas, and explicit one-campaign limits before the first XPU process.

Only that later packet may authorize the four-card component campaign. An
endpoint remains forbidden unless all four cards pass exactness, launch,
timing, occupancy, traffic, spill, and post-timing replay gates.
