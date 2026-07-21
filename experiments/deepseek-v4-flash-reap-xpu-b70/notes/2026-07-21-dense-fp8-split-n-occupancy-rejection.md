# Dense FP8 split-N occupancy rejection — 2026-07-21

## Result first

**FAIL: the exact, scheduling-only candidate saved a conservative
`-0.0470 ms/token` across 43 shared-down calls at M=1, versus the required
`+0.30 ms/token`. Do not schedule a TP4 endpoint run for this candidate.**

The candidate changed the oneDNN fixed-shape JIT workgroup from `wg8x4` to
`wg4x1`. With the unchanged 32-column subgroup output tile, that increased
independent output-N workgroups from 16 to 32. It did not change the checkpoint
weight layout, prepack anything, change FP8 arithmetic, reorder K accumulation,
or change BF16 rounding/stores. The selector
`VLLM_XPU_V4_SHARED_DOWN_FP8_SPLIT_N=4` is default-off and the incumbent path is
unchanged when it is unset.

| Shape / physical XPU | Exact changed X | Exact fixed-address replay | Control -> candidate | Logical GB/s before -> after | Saved across 43 calls |
|---|---:|---:|---:|---:|---:|
| M=1, XPU 2 | 40/40 | 70/70 | 22.258 -> 23.351 us | 94.62 -> 90.19 | **-0.0470 ms** |
| M=1, XPU 3 | 40/40 | 70/70 | 19.618 -> 18.398 us | 107.35 -> 114.47 | **+0.0525 ms** |
| M=8, XPU 2 | 40/40 | 70/70 | 20.128 -> 17.721 us | 107.66 -> 122.29 | **+0.1035 ms** |
| M=8, XPU 3 | 40/40 | 70/70 | 21.603 -> 20.094 us | 100.31 -> 107.85 | **+0.0649 ms** |

M=1 totals are 80/80 changed-input eager comparisons and 140/140 graph
replays. M=8 independently repeats those totals. Every comparison was A-B-A
bitwise BF16 with zero mismatches, so the work decomposition is exact for the
tested widths. The M=8 results explicitly confirm that the kernel and selector
transfer to the spec-verify cycle. They are too small to offset the mixed M=1
result or justify promotion into the 80.82 tok/s recipe.

The component harness measures logical bytes directly. Relative to the prior
in-model 150.3 GB/s baseline, the M=1 time ratios imply only 143.26 GB/s on XPU
2 and 160.26 GB/s on XPU 3—not the targeted 300–400 GB/s.

## EU telemetry

Read-only `xpu-smi` sampling used 15 samples per card per mode while the
production-like rotating-weight shared-down load ran concurrently on physical
XPU 2 and 3. The first unprivileged counters returned `N/A`; the authoritative
files are `baseline-root-eu.csv` and `candidate-root-eu.csv`. No device setting
was changed.

| Physical XPU | EU active before -> after | EU stall before -> after | EU idle before -> after | Sustained logical GB/s before -> after |
|---|---:|---:|---:|---:|
| 2 | 7.200% -> 1.533% | 2.800% -> 4.333% | 90.000% -> 94.133% | 60.58 -> 56.94 |
| 3 | 5.933% -> 1.667% | 2.333% -> 4.867% | 91.733% -> 93.467% | 59.11 -> 60.24 |
| Both-card mean | 6.567% -> 1.600% | 2.567% -> 4.600% | 90.867% -> 93.800% | — |

The narrower cooperative workgroup created more independent output-N groups
but did not improve residency. It instead reduced EU activity and increased
stall/idle time, consistent with losing useful cooperative load behavior. This
is a scheduling negative, not a repeat of the rejected tile-major layout
prepack: coalescing and the weight layout were preserved.

## Implementation and build

The vLLM XPU wrapper salts only the matching primitive cache entry for native
FP8 `M=1..8,N=4096,K=512`, allowing control and candidate graphs in one process.
The oneDNN generator interprets this external shape as
`m_=4096,n_=1..8,k_=512` and changes only `strategy_.wg[LoopM/LoopN]`.

- XPU wrapper commit: `faacc34d9bda2edbbea227eabca922908d94f0b3`
- nested oneDNN commit: `983a67ad47537c7abb7a9e42d4bdd739e4624a24`
- final `_xpu_C.abi3.so` SHA-256:
  `a01a402d3ac6415e2e678a974545c961b827e3b4024382a9c45bd6e91b3c1185`
- patch snapshots:
  `patches/deepseek-v4-flash-xpu-b70/20260721-dense-fp8-split-n-vllm-xpu.patch`
  and
  `patches/deepseek-v4-flash-xpu-b70/20260721-dense-fp8-split-n-onednn.patch`

Only the changed oneDNN generator object, `libdnnl.a`, the wrapper's
`onednn_matmul.cpp.o`, and final extension target were explicitly requested:

```bash
ninja -C /home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/build/temp \
  /home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/.deps/onednn-build/src/gpu/intel/gemm/jit/CMakeFiles/dnnl_gpu_intel_gemm_jit.dir/gen_kernel.cpp.o \
  libdnnl.a CMakeFiles/_xpu_C.dir/csrc/xpu/onednn/onednn_matmul.cpp.o \
  _xpu_C.abi3.so
sha256sum /home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/build/temp/_xpu_C.abi3.so
```

Representative assigned-card gate form (run once with physical card 2 and once
with 3, and with width 1 and 8):

```bash
ZE_AFFINITY_MASK=2 python3 \
  experiments/deepseek-v4-flash-reap-xpu-b70/scripts/bench-dense-fp8-split-n-occupancy.py \
  --card 2 --width 1 --split-n 4 --eager-epochs 40 --graph-replays 70 \
  --out /mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dense-fp8-split-n-two-card-gate-20260721T133642Z/card2-m1-n4.json
```

The final binary smoke on XPU 2 remained exact at 4/4 eager and 4/4 graph; its
20.738 -> 25.739 us timing was another negative (`-0.2150 ms` across 43 calls).
The full gate used the same generated device code with a temporary host-only
JIT diagnostic print; removing that print produced the final SHA above and did
not alter the device kernel.

## Artifacts and safety

- Structured summary:
  `experiments/deepseek-v4-flash-reap-xpu-b70/data/dense-fp8-split-n-occupancy-20260721.json`
- Selected full gate:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dense-fp8-split-n-two-card-gate-20260721T133642Z`
- EU telemetry:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dense-fp8-split-n-telemetry-20260721T133727Z`
- Final-binary smoke:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dense-fp8-split-n-finalbinary-smoke-20260721T134349Z.json`
- Real split 1/2/4 prescreen:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dense-fp8-split-n-real-prescreen-20260721T133607Z`

Only XPU 2 and XPU 3 were used. XPU 1's EAGLE training process was not touched;
XPU 0 was not used. There was no device loss, no TP4 endpoint, no LocalMaxxing
submission, and no quality or pack change. K remained 512 for this component
(the program's K160 condition was not altered).

Because shared-down failed the explicit `>=0.30 ms/token` gate, the conditional
dense WQ_B W8A16 and shared gate/up W8A16 variants were not implemented or run.
The default-off code and negative artifacts are retained for future scheduler
work, but this exact candidate is **not worth a TP4 endpoint run**.
