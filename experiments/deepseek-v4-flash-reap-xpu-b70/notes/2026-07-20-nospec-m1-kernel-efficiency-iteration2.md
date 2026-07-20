# Nonspeculative M=1 kernel efficiency iteration 2

Date: 2026-07-20

## Numbers first

The exact retained bundle saves only **`0.026013 ms/token`** on the slowest
candidate card (`0.001310 ms/token` as the conservative minimum across all
cards), so it **FAILS** the required `0.50 ms/token` integration gate. No model
was loaded, no nonspeculative B-A-B was run, and no LocalMaxxing action was
made.

| Target | Selected candidate | Profile GB/s before -> normalized after | Slowest-card microgate GB/s before -> after | Saved ms/token | Eager exact | Graph exact | Keep |
|---|---|---:|---:|---:|---:|---:|---|
| Routed MXFP4 N64 | prefetch `6 -> 3`, retain A hints | `288.7 -> 290.5` | `410.75 -> 413.31` | **`+0.026013`** | `160/160` | `160/160` | yes, default-off |
| Shared-down W8A8 512->4096 | contiguous `[K,N]` prepack | `150.3 -> 137.9` | `103.80 -> 95.23` | `-0.078162` | `160/160` | `160/160` | no: slower |
| WQ_B W8A16 1024->8192 | contiguous `[K,N]` prepack | `389.2 -> 284.9` | `425.55 -> 311.51` | `-0.310294` | `53/160` | `68/160` | no: inexact and slower |
| Shared gate/up W8A16 4096->1024 | padded-64 `[K,N]` prepack | `361.0 -> 294.2` | `220.82 -> 179.95` | `-0.185505` | `135/160` | `136/160` | no: inexact and slower |

The first GB/s pair keeps the July 20 profile's logical-byte basis. Candidate
values are normalized by the paired microgate time ratio. The second pair is
the direct four-card microgate's logical weight-byte rate. These bases are
reported separately because the published `288.7 GB/s` routed row is an
in-model floor-residual family estimate, while the focused gate counts actual
local GEMM1/GEMM2 bytes. No hardware DRAM counter claim is made.

The retained bundle consists only of MXFP4 distance 3. Therefore its combined
changed-input eager and fixed-address graph exact gate is the selected
component's `160/160` eager plus `160/160` graph result. The three dense
components were removed before combination under the individually exact and
non-regressing rule.

## MXFP4 prefetch screen

The source adds default-off
`VLLM_XPU_MXFP4_M1_PREFETCH_MODE={d2,d3,d4,d2-noa,d3-noa,d4-noa}`. Unset is
the byte-for-byte incumbent distance-6 path. The selector is restricted to the
M1 N64 direct launcher and rejects combination with the closed GRF128 lane.
The tile remains M8xN64xK32 with four SG16 subgroups and GRF256. Actual A/B
loads, scale order, BF16 scaling, DPAS sequence, FP32 accumulation and BF16
store are unchanged. The `noa` modes remove only redundant cache hints from
the 64 N workgroups, never the required A load.

All six variants passed the card-0 bitwise screen. Their three-local-route
projections across 43 routed layers were:

| Mode | Saved ms/token |
|---|---:|
| `d2` | `-0.053795` |
| `d3` | `+0.008443` |
| `d4` | `-0.142863` |
| `d2-noa` | `-0.610443` |
| `d3-noa` | `-0.773104` |
| `d4-noa` | `-0.809587` |

Removing A hints is decisively counterproductive. The full `d3` four-card
confirmation is:

| Card | Eager | Graph | Control us/layer | Candidate us/layer | GB/s before -> after | Saved ms/token |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | `40/40` | `40/40` | `96.329950` | `96.299475` | `416.36 -> 416.49` | `+0.001310` |
| 1 | `40/40` | `40/40` | `97.474480` | `97.002605` | `411.47 -> 413.47` | `+0.020291` |
| 2 | `40/40` | `40/40` | `97.534375` | `96.775780` | `411.22 -> 414.44` | `+0.032620` |
| 3 | `40/40` | `40/40` | `97.645055` | `97.040105` | `410.75 -> 413.31` | **`+0.026013`** |

Card 3 is the slowest absolute candidate. Card 0 supplies the fail-closed
minimum improvement. Distance 3 is kept only as a default-off exact component;
its gain is far too small to fund a service load.

This selector does **not** transfer to the M=8 target-verify cycle: that path
uses the generic N128 launcher and never enters the changed M1/N64 dispatch.

## Dense oneDNN prepack screen

The current backend already caches fixed-shape oneDNN primitives and JIT
kernels, and block scales are already transposed once at load. The new
default-off flags therefore test a real remaining layout lever rather than
duplicating existing caching:

- `VLLM_XPU_V4_SHARED_DOWN_FP8_PREPACK`;
- `VLLM_XPU_V4_WQB_W8A16_PREPACK`;
- `VLLM_XPU_V4_SHARED_GATE_UP_W8A16_PREPACK`.

Each accepts `contiguous` or `padded64`. Both materialize the immutable FP8
weight bytes once at load into a stable `[K,N]` address; padded64 adds a
64-byte row pad. Quantization, scales, dtypes and output dtype are unchanged.
Both layouts were run on all four cards with 40 changing eager inputs and 40
changed fixed-address graph replays per shape.

Shared-down remained bitwise exact for both layouts but regressed on every
card. The best conservative candidate was contiguous, whose candidate-slowest
card fell from `103.80` to `95.23 GB/s`, projecting `-0.078162 ms/token`.

The two W8A16 projections were neither exact nor fast. Changing LDB/layout
caused oneDNN to select a different JIT strategy and therefore a different
FP32 accumulation grouping. WQ_B contiguous passed only `53/160` eager and
`68/160` graph epochs and lost `0.310294 ms/token` on its slowest candidate
card. Shared gate/up's least-bad padded64 mode passed `135/160` eager and
`136/160` graph epochs and lost `0.185505 ms/token`. The alternate layouts
also failed. This closes opaque/plain prepack tuning for these shapes on the
current pinned oneDNN.

The dense layouts are M-invariant and would structurally transfer to the same
M=8 projections, with separately cached M=8 primitives. They are rejected,
however, so no candidate dense component transfers into the speculative
record recipe.

## Identity, build and artifacts

- model and quantization stayed fixed at K160 revision
  `7c360e1cd4a5168099dbc54d16d929bf6df04990`; the model was not loaded;
- XPU source: `c9f20d2238cdd98b510d809e7e70f1be1319e459`;
- vLLM source: `bbb633a90cef5167ea7f11846db5c185c5243931`;
- only `grouped_gemm_xe2.cpp.o` and `libgrouped_gemm_xe_2.so` were rebuilt;
- grouped library SHA-256:
  `c225f5d2a98a1a7af435cb8c3782b5601e33fd361ac74a0967d4be3c59350bbe`;
- unchanged `_xpu_C.abi3.so` SHA-256:
  `c0597c1db9d1e684462adce681101957e7a969baab3c0c71fb748ca7fd8c24e9`;
- vLLM layout code is Python/load-time only and required no native rebuild;
- structured summary:
  `../data/nospec-m1-kernel-efficiency-iteration2-20260720.json`;
- MXFP4 harness:
  `../scripts/bench-m1-mxfp4-grf-efficiency.py`;
- dense harness:
  `../scripts/bench-m1-dense-prepack-efficiency.py`;
- XPU patch:
  `../../../patches/deepseek-v4-flash-xpu-b70/20260720-m1-mxfp4-prefetch-distance.patch`;
- vLLM patch:
  `../../../patches/deepseek-v4-flash-xpu-b70/20260720-dense-fp8-fixed-shape-prepack.patch`;
- raw dense contiguous:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m1-dense-prepack-contiguous-20260720T1700Z`;
- raw dense padded64:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m1-dense-prepack-padded64-20260720T1705Z`;
- raw MXFP4 sweep:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m1-mxfp4-prefetch-card0-screen-20260720T1730Z`;
- raw MXFP4 four-card gate:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m1-mxfp4-prefetch-d3-four-card-20260720T1740Z`.

No frozen held-out pack or captured decoder corpus was opened or modified.
GRF128, N32/N128 M1 tile policy, MHC arithmetic fusion, MoE routing/gather and
attention remained outside this iteration. One active generation and
LocalMaxxing state were untouched.

## Ranked shortlist for iteration 3: exact launch-fusion lane

1. **Canonical MHC load/staging plus consumer transaction.** Start from the
   unchanged SG16/BLOCK_N12 arithmetic and its `2.630 ms/token` above-ideal
   ceiling. Co-own fixed addresses and graph-visible completion with the next
   consumer so a launch or round-trip is removed; do not change the reduction
   tree, precision, post/pre arithmetic, or revisit inexact MHC+RMS fusion.
2. **Persistent routed-MoE boundary using unchanged arithmetic kernels.** The
   non-GEMM route/activation/gather scope retains about `1.833 ms/token` above
   logical-traffic ideal. A viable design must remove multiple device launches
   and metadata round-trips as one fixed transaction, not retry deletion-only
   gather, compact-route, paired GEMM1, unique-route emitter, or recomputed
   SwiGLU variants already closed below the gate.
3. **Canonical MHC load-width/staging-only microsearch.** Screen cache-line and
   block-2D staging changes inside the existing exact SG16/BLOCK_N12 kernel,
   with a fresh four-card ceiling of at least `0.50 ms/token`. Keep the exact
   reduction/store order; BLOCK_N24 and alternate reduction/fusion paths stay
   closed.

Every iteration-3 candidate must again be default-off, bitwise on changing
eager and fixed-address graph inputs across all cards, non-regressing in
isolation, and admitted to service only after the retained bundle clears
`0.50 ms/token` conservatively.
