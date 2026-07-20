# Nonspeculative M=1 per-kernel efficiency and GRF128 closure

Date: 2026-07-20

## Numbers first

The first exact-safe device-kernel efficiency screen is **correct but rejected**.
Changing only the M=1 N64 routed-MXFP4 kernel's register allocation from 256
GRFs to 128 GRFs preserves every tested bit but approximately doubles the
complete routed-MoE boundary. On the slowest candidate card, the three-local
route changes from `107.315365` to `205.146615 us/layer`, a projected
**`-4.206744 ms/token` saving** across 43 routed layers. This fails the required
`+0.30 ms/token` gate. No model was loaded and no nonspeculative B-A-B or
LocalMaxxing submission was run.

All four B70s pass `40/40` changing-input eager schedules and `40/40`
fixed-address graph replays, for `160/160` eager and `160/160` graph cases in
aggregate. GEMM1, clamped activation, GEMM2 and final weighted output are all
bitwise identical, and the A-B-A baseline replay is stable.

## Ranked achieved-bandwidth profile

`527 GB/s/card` is the measured peak. Bytes are decimal logical bytes, not a
hardware DRAM-counter result. `Above ideal` is `measured - bytes/527 GB/s`.
The phase-correct eager trace supplies in-model device times because the valid
PIECEWISE graph is opaque internally; the graph-on `22.881408 ms/token` result
remains endpoint authority.

| Rank | Kernel or family | Bytes/token | Measured ms | GB/s | Peak | Above ideal ms | Evidence |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | MHC fused post/pre x85 | 149.035 MB | 2.912528 | 51.2 | 9.7% | 2.629729 | in-model time; source logical bytes |
| 2 | MoE route, activation, direct gather/scatter | ~4.800 MB | 1.842000 | ~2.6 | 0.5% | 1.832892 | current isolated component gates; source logical bytes |
| 3 | Routed MXFP4 expert GEMMs x86 | 1,006.087 MB | 3.485000 | 288.7 | 54.8% | 1.575916 | in-model time; floor-residual weight bytes |
| 4 | Attention QK/LSE x43 | ~12.813 MB | 1.158989 | 11.1 | 2.1% | 1.134675 | in-model short-context time; source logical bytes |
| 5 | Dense shared-down FP8 512->4096 x43 | 90.183 MB | 0.600219 | 150.3 | 28.5% | 0.429094 | in-model shape attribution |
| 6 | Attention PV x43 | ~15.197 MB | 0.300611 | 50.6 | 9.6% | 0.271775 | in-model short-context time; source logical bytes |
| 7 | Dense WQ_B W8A16 1024->8192 x43 | 360.732 MB | 0.926973 | 389.2 | 73.8% | 0.242472 | in-model shape attribution |
| 8 | Dense shared gate/up W8A16 4096->1024 x43 | 180.366 MB | 0.499576 | 361.0 | 68.5% | 0.157325 | in-model shape attribution |
| 9 | Dense WO_B W8A16 2048->4096 x43 | 360.732 MB | 0.831336 | 433.9 | 82.3% | 0.146835 | in-model shape attribution |
| 10 | Dense fused WQA/WKV W8A16 4096->1536 x43 | 270.550 MB | 0.640782 | 422.2 | 80.1% | 0.127405 | in-model shape attribution |
| 11 | Dense BF16 router 4096->160 x43 | 56.361 MB | 0.213129 | 264.4 | 50.2% | 0.106183 | in-model shape attribution |
| 12 | Dense BF16 wo_a BMM x43 | 721.420 MB | 1.406823 | 512.8 | 97.3% | 0.037904 | in-model shape attribution |
| 13 | Dense BF16 4096->1024 x20 | 167.772 MB | 0.348016 | 482.1 | 91.5% | 0.029663 | in-model shape attribution |
| 14 | Dense BF16 4096->2048 x21 | 352.322 MB | 0.690203 | 510.5 | 96.9% | 0.021661 | in-model shape attribution |
| 15 | LM head BF16 4096->32320 x1 | 264.765 MB | 0.446506 | 593.0 | 112.5% | 0.000000 | cache/timestamp-limited; no recoverable claim |

Dense projections total `2.825203 GB` in `6.603564 ms`, or `427.83 GB/s`,
with `1.242648 ms/token` above the peak-bandwidth ideal. Defining routed bytes
as the established `7.270 ms` weight floor minus dense bytes yields the
`1.006087 GB` routed row. Dense plus routed slack reconciles to the established
`2.819 ms/token` weight-kernel slack.

The byte caveats matter. No saved artifact has valid hardware DRAM counters.
Dense bytes come from traced tensor shapes and weight/scale widths. Routed
bytes are the deliberate roofline residual. MHC, attention and non-GEMM MoE
bytes are source-derived logical traffic. The attention trace covers seven
decode steps at mean attended length 24, so its bandwidth is a short-context
efficiency proxy rather than a long-context claim.

## Target selection and exact-safe change

MHC and the non-GEMM MoE boundary rank above MXFP4 arithmetically, but their
large exact/inexact fusion, workgroup and deletion lanes are already closed.
MHC `BLOCK_N=24` recovered only `0.081 ms/85`; direct-gather deletion is bounded
at `0.151-0.168 ms/token`; neither can satisfy this iteration alone. The open
high-time target is therefore routed MXFP4 at `288.7 GB/s`, `54.8%` of peak,
with a theoretical `1.575916 ms/token` gap. Raising it to a realistic 65-70%
of peak would recover roughly `0.55-0.76 ms/token`.

The candidate templates the existing M1 launcher on GRF size and adds the
default-off `VLLM_XPU_MXFP4_M1_GRF128=1` selector. Nothing else changes:
M8xN64xK32 tile, four SG16 subgroups, prefetch distance, block-2D loads, scale
application, DPAS sequence, FP32 accumulation and BF16 output rounding are
identical. This is an occupancy/register-allocation experiment, not a new
arithmetic path and not a repeat of the closed N32/N128 tile policies.

The incremental build starts from XPU `313156737`, the public speculative
record tree, because it retains a configured grouped-GEMM build. Its M1 N64
direct launcher and mainloop are unchanged from nonspec XPU `6522849b`; later
M2/M8 additions remain default-off in this M1 gate. Baseline and candidate are
two captures from this same binary, differing only in the GRF selector.

Only the grouped-GEMM object and `libgrouped_gemm_xe_2.so` were rebuilt. The
candidate library SHA-256 is
`205a1ab058f61ac6994f4f3a4dfe45b70d12cb5a379f8977c65b44de319ded5c`.
The unchanged `_xpu_C.abi3.so` SHA-256 is
`c0597c1db9d1e684462adce681101957e7a969baab3c0c71fb748ca7fd8c24e9`.

## Four-card exact and timing gate

| Card | Eager exact | Graph exact | GRF256 us/layer | GRF128 us/layer | Projected saved ms/token | Gate |
|---:|---:|---:|---:|---:|---:|---|
| 0 | 40/40 | 40/40 | 105.301825 | 202.760935 | -4.190742 | FAIL |
| 1 | 40/40 | 40/40 | 106.804950 | 205.077345 | -4.225713 | FAIL |
| 2 | 40/40 | 40/40 | 106.675780 | 205.029945 | -4.229229 | FAIL |
| 3 | 40/40 | 40/40 | 107.315365 | 205.146615 | -4.206744 | FAIL |

Timing uses nine alternating 200-replay samples after 40 warmups, with the
representative three-local route. The candidate's worst absolute time is card
3, so its `-4.206744 ms/token` result is the requested slowest-card number.
The minimum saving on any card is `-4.229229 ms/token` on card 2. Both are far
below the `+0.30 ms/token` admission threshold.

This selector is M1-direct-launcher-only. The M=8 target verifier uses the
generic M8/N128 grouped path, so **the change does not transfer to the 80.82
tok/s speculative record**. No claim is made from the shared underlying
mainloop because the changed launcher property is not used there.

## Artifacts and next iteration

- structured summary: `../data/nospec-m1-kernel-efficiency-iteration1-20260720.json`;
- exact/timing harness: `../scripts/bench-m1-mxfp4-grf-efficiency.py`;
- source patch: `../../../patches/deepseek-v4-flash-xpu-b70/20260720-m1-mxfp4-grf128-occupancy.patch`;
- XPU source commit: `790479dc6538c927ccc75e4f1087c107b42c87bb`;
- raw four-card gate:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m1-mxfp4-grf128-efficiency-gate-20260720T154042Z-b`;
- profile trace:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/record-lane-eager-tuned-profile-20260715T0730Z`;
- PIECEWISE endpoint authority:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/nospec-m1-roofline-profile-20260719T140812Z`.

Ranked shortlist for iteration 2:

1. MXFP4 N64 mainloop prefetch-distance `6 -> 2/3/4` screen, retaining the
   DPAS and scale order; isolate B/scale prefetch first and test whether the
   duplicated A prefetch is counterproductive.
2. Shared-down W8A8 oneDNN fixed-shape primitive/prepack/JIT specialization;
   its `0.429 ms/token` nominal gap clears the screen threshold, but do not
   revive the slower/inexact custom ESIMD DPAS path.
3. Combined exact same-dtype oneDNN layout/JIT tuning for fused WQA/WKV plus
   shared gate/up, whose individual gaps are `0.127` and `0.157 ms/token` and
   sum to `0.285 ms/token` before implementation cost.
4. Split attention QK/LSE load/staging/vector efficiency without changing the
   promoted B4/QK16 arithmetic/geometry; require a fresh fixed-context bound
   and do not reuse the endpoint-negative M8 width-aware geometry.
5. Canonical MHC SG16/BLOCK_N12 load-width/staging only if a new upper bound
   clears `0.30 ms/token`; do not reopen prior reduction-tree or fusion paths.

No frozen held-out pack was opened or modified. No LocalMaxxing action was
made.
