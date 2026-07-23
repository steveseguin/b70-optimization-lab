# Laguna routed-W1 N128 implementation and smoke

Date: 2026-07-23 America/Toronto

Status: implementation and revised int32 smoke pass; formal four-card component
gate not yet started.

## Frozen preregistration

The experiment boundary and gates were committed before implementation:

- main commit `e70b1303a` (`laguna: preregister routed W1 N128 screen`);
- control W1 N tile 64;
- only candidate W1 N tile 128;
- N32 forbidden without a separate later preregistration;
- W2, gather, arithmetic order, and endpoint stack frozen.

## Source implementation

Kernel repository:

`/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc`

Commits:

- `c834848` (`xpu: select exact Laguna M8 W1 N tile`);
- `c59aaad` (`xpu: tighten Laguna W1 N128 contract`).

The implementation:

- appends a required `w1_n_tile` integer to the native op schema;
- accepts only literal 64 or 128 in the Python selector;
- selects the existing N128 template only for M=8;
- keeps M=1 through M=7 on literal N64;
- requires exact batched MoE, fused-W1/route-W2, and route interleave in
  production Python;
- requires N128 to be W1-only M=8 route interleave with an int32 `[256]` EP4
  expert map in native code;
- leaves the W2 launcher and route-parallel W2 call on N64; and
- has no schema default, so stale callers fail rather than silently taking
  N64.

Focused parser, effective-tail-dispatch, and schema tests passed:

```text
15 passed, 220 deselected
```

The coupled ABI build used oneAPI 2025.3. The first build rebuilt and installed
both native libraries; the follow-up native-contract change rebuilt and
installed the grouped-GEMM library. Logs:

- `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/builds/w1-n128-build-20260723T035000-0400.log`;
- `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/builds/w1-n128-ep4-map-rebuild-20260723T043000-0400.log`.

Installed binary SHA-256:

- `_xpu_C.abi3.so`:
  `f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8`;
- `libgrouped_gemm_xe_2.so`:
  `fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96`.

The prior binary pair was preserved under:

`/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/builds/pre-w1-n128-20260723T040500-0400/`

## Harness hardening

The new formal harness is
`tools/gate_laguna_w1_n128.py`. It:

- runs one declared physical card per process and requires
  `ZE_AFFINITY_MASK == --rank`;
- uses the production int32 TopkId template;
- runs 64 changing full-W13/scales/hidden/routes epochs before and after
  timing;
- compares raw local W1, activation, unchanged N64 W2, and final gathered
  output;
- proves input immutability, N128 repeat determinism, and remote scratch
  behavior;
- rejects invalid tiles, N128 tails, disabled route interleave, non-W1-only
  N128, and a missing EP4 map;
- uses allocation-free exact-shape M=8 views inside timed calls;
- runs the frozen 31 A-B-B-A blocks, 64 cycles per arm, and 47 layer calls per
  cycle; and
- marks counter-only output as unevaluated rather than claiming a pass.

The historical `tools/gate_laguna_fused_m8.py` now passes explicit literal N64
to remain runnable with the required ABI. The four-card aggregator
`tools/analyze_laguna_w1_n128_gate.py` additionally requires declared ranks 0
through 3, four distinct `xpu-smi` physical UUIDs and PCI BDFs, matching
binaries and fixture artifact, all per-card gates, and at least 2% mean
relative W1 improvement.

## Smoke history

The first smoke stopped before a kernel launch because the venv namespace
resolved an older unrelated kernel worktree. Preserved evidence:

`/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-smoke-card0-20260723T041500-0400/`

The second smoke passed but used int64 TopkId, so it is deliberately
ineligible:

`/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-smoke2-card0-20260723T042000-0400/`

The revised card-0 smoke used the exact source roots, installed binary hashes,
int32 TopkId, and the EP4 native guard. It passed:

- 2/2 changing pre-timing epochs;
- 2/2 bit-identical post replay epochs;
- raw W1, activation, N64 W2, and final output equality;
- unchanged inputs and remote scratch;
- M=1..7 N64 equality and N128 rejection; and
- all four explicit invalid-contract rejections plus missing-map rejection.

Evidence:

`/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-smoke3-int32-card0-20260723T044500-0400/result.json`

No smoke throughput or timing is eligible for promotion.

## Real timing fixtures

A review found no directly serialized endpoint route tensors. The approved
router gate can, however, reconstruct exact route output from three retained
47-layer M=8 hidden-state trace sets plus the exact checkpoint router weights
and correction biases.

`tools/extract_laguna_w1_timing_fixtures.py` rebuilt all 141 fixtures and
required raw equality between the incumbent and approved exact router op before
saving anything. Each fixture contains:

- real BF16 hidden states `[8,3072]`;
- exact FP32 top-k weights `[8,10]`;
- production int32 top-k IDs `[8,10]`; and
- int32 source rows `[8,10]`.

Artifact:

`/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/data/w1-real-m8-timing-fixtures-20260723.pt`

Hashes:

- artifact:
  `478a23508e635c91fa62ff0a4b737016266bc308e8fe60111e81abad3d47c1f6`;
- aggregate tensors:
  `2830da5e5e7ee2f4118b8d6c5618be6d36bb9a567c17df230bb87e20890734af`;
- production sources:
  `bd1d6ef31f8ee359f04c6af1ccc55e39d79b21fc1592ae2377734e64f2512a47`.

The actual local-route shares span `24.07%` through `26.06%` across the three
sets and four EP ranks. The formal harness requires this exact hashed artifact;
fixture creation, validation, and transfer remain outside timed arms.

A card-0 loader/counter smoke reproduced every artifact hash and physical
device identity. It is explicitly marked `passed: null` and
`counter_gate_evaluated: false`; it is not counter or timing evidence:

`/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-real-fixture-load-smoke-card0-20260723T045500-0400/result.json`

Manifest and extraction log:

- `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/data/w1-real-m8-timing-fixtures-20260723.manifest.json`;
- `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/data/w1-real-m8-timing-fixtures-20260723.extract.log`.

## Next gate

Run formal card 0 first. A failed exactness or timing threshold stops the lane
without spending three more card runs. If card 0 passes, run cards 1 through 3
with the same binaries and fixture artifact, aggregate the four results, and
only then collect matched N64/N128 counters. No endpoint is authorized until
the counter gate is also preserved and classified.
