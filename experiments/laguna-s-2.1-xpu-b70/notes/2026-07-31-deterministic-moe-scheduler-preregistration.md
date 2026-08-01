# Laguna exact width-12 deterministic MoE scheduler

Date: 2026-07-31 America/Toronto

Status: **preregistered before implementation, build, or device execution.**

## Evidence and target

The promoted exact BF16-KV record is `125.4619731637751 tok/s`
conventionally.  Reaching 130 at unchanged acceptance requires about
`1.128465 ms` from the recorded `32.326922 ms` verifier cycle.

The exact current target executes one INT4 W13 and one INT4 W2 grouped GEMM in
each of 48 layers.  The current-source real-shape component costs about
`0.504707 ms/layer`, mechanically `24.226 ms/cycle`.  A `4.66%` exact
improvement in this scope can therefore cover the entire remaining gap.

The current `MoEGEMM` uses a persistent task scheduler.  Workgroups scan up to
64 expert row counts to locate their first tile; after every tile, local lane
zero performs a device-global atomic, the whole workgroup crosses a local
barrier, and the workgroup resumes expert scanning to locate its next tile.
This repeats in both GEMMs across all 48 layers.

## Frozen treatment

Add a separately named, default-off deterministic scheduler only for the exact
current target route:

- BF16 activations/scales and INT4 weights;
- `total_m=120`, group size 32, `w4a16_policy_m_8`;
- GRF128, scale-vector, transposed scales;
- no scale fold or dequant-MAD;
- ordinary non-tile-major weights.

Launch the maximum exact grid `total_m * ceil(N / N_tile)`.  A workgroup maps
its flat ID to one logical expert M tile and one N tile by scanning the same
`rows_per_expert` counts.  Invalid tail workgroups return.  Valid workgroups
call the unchanged `xe_gemm_4bits` body exactly once and then return, removing
the persistent atomic, barrier, and subsequent task-acquisition loop.

This is **not** the older route-direct experiment.  Rows remain grouped by
expert, duplicate expert rows retain their M tile and weight reuse, activation
and output layout remain unchanged, and every INT4 dequantization, BF16 scale,
DPAS K traversal, FP32 accumulation, BF16 store, and output ownership rule is
preserved.

Selector-off source behavior must remain unchanged.  Prefill, draft, other
widths, other policies, other scale layouts, and other dtypes must not reach
the new named kernel.

## Gates and stop rules

1. Implement in a fresh worktree from XPU-kernel record source
   `99886d783372e621941228250091dc8ebdc1595d`.
2. Source/static checks must prove a separately named kernel, fail-closed exact
   route predicate, unchanged arithmetic template arguments, 128 GRFs, and no
   spill/scratch traffic.  Stop before a full build if the arithmetic body or
   register contract changes unexpectedly.
3. Build with the record-compatible oneAPI 2025.3 ABI.  Compare selector off
   and on from the same DSO on a healthy idle B70 using the deterministic
   changed-input physical-transposed-scale corpus for real W13
   `M=120,N=2048,K=3072` and W2 `M=120,N=3072,K=1024` shapes.
4. Require raw-BF16 equality for every changed input.  Require at least `5%`
   improvement in summed stable W13+W2 median and no shape regression over
   `1%`.  This covers the `4.66%` mechanical need plus integration uncertainty.
5. A component pass authorizes focused integration smoke, not a score.  Smoke
   must retain target `146/145` and draft `14/13` on all four ranks, exact q1
   prefixes, normal non-flat acceptance, cache-zero, and clean teardown.
6. Only a passed smoke authorizes one cold fixed-suite result.  The first valid
   score stands; promotion requires 13/13 canonical-q1 exactness and a true
   improvement over `125.4619731637751 tok/s` conventionally.

No model, checkpoint revision, quantization, BF16 KV, width/depth, target
verification, prompt, teacher, cache, sampling, metric, retry, warmup
generation, or scoring-window change is allowed.  No reset, driver reload,
FLR, reboot, or privileged recovery is authorized by this experiment.

