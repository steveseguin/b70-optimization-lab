# Laguna INT4 in-place dequant-MAD: static rejection

Date: 2026-07-31 America/Toronto

Status: **closed before GPU use**. The production library compiled, but the
matched BMG ISA gate showed that the in-place operand binding adds 32
instructions. No component test, model load, generation, scored leg,
throughput claim, or recovery action occurred.

## Candidate and identity

The preregistered candidate changed only `apply_scale_pair_mad` in the Xe2
INT4 grouped-GEMM mainloop. The same 32-element BF16 channel-pair object was
previously passed to inline assembly twice: a separate read-only source and a
write-only destination. The candidate named it once as a `+rw` operand and
used that declaration as both MAD source and destination.

- source base: `46a88e09d96fe06871c87a23de534fb47f1e039b`;
- negative candidate: `7df9806e9eb12fb8e880c7ba0c6b4a104ef73832`;
- branch: `experiment/laguna-mad-inplace-20260731`;
- compiler: oneAPI `icpx` 2025.3, the existing grouped-GEMM CMake/Ninja
  configuration;
- command: `ninja -C build/temp libgrouped_gemm_xe_2.so`;
- candidate DSO SHA-256:
  `9e7cb7a00bbdc4a4808dee5ec03ab7954d1129b3d64a6740e83aaa8ca08afe33`;
- candidate DSO size: `30,334,776` bytes.

The full build passed for PVC, BMG, BMG G21 A0 and BMG G31 A0. It took about
42 minutes and peaked near 122.8 GB RSS. The BMG linker printed its existing
generic `w4a16_policy` spill warning; the matched decode-policy probe below is
the candidate comparison authority.

## Matched IGC gate

The recovered probe instantiates the production `xe_gemm_4bits` template with
`w4a16_policy_m_8`, group size 32, the same 256-GRF BMG backend option, and
three selector variants. The exact same probe source and dependency headers
were compiled once against the frozen incumbent tree and once against the
candidate tree.

| Selector variant | Incumbent instructions | Candidate instructions | DPAS | BF16 MAD | BF16 mul | total mov |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `SCALE_VEC=0, DEQUANT_MAD=0` | 422 | 422 | 2 | 0 | 32 | 172 |
| `SCALE_VEC=1, DEQUANT_MAD=0` | 389 | 389 | 2 | 0 | 32 | 140 |
| `SCALE_VEC=1, DEQUANT_MAD=1` | **376** | **408** | 2 | 32 | 0 | 156 -> 188 |

A full mnemonic census of the MAD kernel localizes the complete delta:
everything is unchanged except `mov`, which rises from 156 to 188. Thus the
candidate adds exactly 32 moves while preserving the two DPAS and 32 MAD
instructions. The default and SCALE_VEC-only variants remain identical,
which also verifies that the source change is isolated to the requested
selector.

This fails two preregistered stop conditions: it removes fewer than eight
integer/data-movement instructions, and its total instruction count is not
lower than the first MAD path. The component exactness and endpoint stages
were therefore skipped.

## Why the premise failed

Assembly operand identity is not C++ object identity. Although the old source
and destination references alias the same fragment, presenting them as a
read-only source and a write-only destination lets IGC register-rename the MAD
result without creating an in-place dependency. Forcing one read-write operand
instead makes the compiler preserve and rematerialize the fragment across the
two MADs. On this kernel that costs one extra move per dequantized element.

The reusable rule is: do not infer less register plumbing from fewer inline
assembly operands. For Xe2 full-GRF operations, compare generated ISA first;
separate input/output operands can be cheaper than `+rw`, even when the C++
storage aliases.

## Artifacts

- preregistration:
  `experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-dequant-mad-inplace-preregistration.md`;
- structured result:
  `data/laguna-dequant-mad-inplace-negative-20260731.json`;
- durable probe source:
  `experiments/laguna-s-2.1-xpu-b70/tools/igc_int4_mainloop_probe.cpp`;
- durable probe runner:
  `experiments/laguna-s-2.1-xpu-b70/tools/run_igc_int4_mainloop_probe.sh`;
- incumbent IGC dumps:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-mad-inplace-incumbent2-20260731T0821Z`;
- candidate IGC dumps:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-mad-inplace-candidate2-20260731T0819Z`;
- preserved candidate DSO:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-mad-inplace-static-negative-20260731T0823Z/libgrouped_gemm_xe_2.so`;
- review patch SHA-256:
  `ef639c3cc2a05fa4db870301fa3f732cf4ae031c2b16509d658d46c6c886e632`;
- source bundle SHA-256:
  `735d958c6c5d47e49d5184bcb30cc166033b69f94c38b5081d5f42d727e0ade2`.

Two probe plumbing failures are not performance evidence: the first recovered
harness omitted the explicit policy include, and the frozen incumbent
worktree lacked its untracked CUTLASS dependency cache. The corrected runner
accepts a separate `LAGUNA_XPU_DEPS_TREE`, and only the fresh successful roots
listed above are used in the table.
