# Qwen3.8 Flash-Next FP8 HC M1 grouped-GEMM preregistration

Date: 2026-08-30/31
Status: frozen before component execution

## Question and boundary

A28 places the two attention HyperConnection projection families at about
`3.41 ms/target token`, the largest stable dense sub-bucket. The direct
`torch.mv` screen was slower and is closed. This bounded screen asks whether
the existing Xe2 BF16 grouped-GEMM implementation, used with one expert and a
prepacked `[1,K,N]` weight, can outperform `F.linear` without changing any
consumed output byte.

This is a one-B70, hot-weight component screen. It performs no reboot, server,
full checkpoint load, PLE mapping, or endpoint request. It cannot establish an
endpoint improvement. `F.linear` allocates its result while the grouped arm
reuses its required output tensor, and repeated calls keep one weight hot. A
positive result may only authorize a later round-robin component screen over
many layer weights.

The sampled weights are attention HC layer 0 and layer 47 only. The MLP HC
family and final no-combine down shape `(1,320,10240)` are outside this first
screen. Down projection compares only the 324 outputs consumed by production;
the 12 alignment-padding outputs are recorded but cannot reject an otherwise
exact path. Up projection compares all outputs.

## Exact model identity

- model: `Qwen/Qwen3.8-Flash-Next-FP8`;
- revision: `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- index SHA-256:
  `0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6`;
- config SHA-256:
  `99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d`;
- layer-0 shard SHA-256:
  `774f0ceeadb40d165f2b3ff397d5f3840e6ca8fcb8f3d39d8acb4fea9e52c941`;
- layer-47 shard SHA-256:
  `2d06ec9c1726f42bfc9ce0bbb47129917d8ab373c88eed4e758fb6940c92ad4a`.

## Component runtime and source identity

The previously frozen serving `_xpu_C` did not register grouped GEMM and is
unchanged. A new component-only pair was built and installed to:

`/mnt/usb-models/qwen38-build/hc-grouped-stage-eeee7d6-sycl8/vllm_xpu_kernels`

Its `SHA256SUMS` digest is
`71e263f19ccc1313bbdc21604b4de5171891454fb7e8e35877af083505522951` and
contains exactly:

- `_xpu_C.abi3.so`:
  `07cba22dbfef80914784767a556320df87215b2ebc1226716da9d775a3c66dc3`;
- `libgrouped_gemm_xe_2.so`:
  `4493c3030b1a53b756953c15e390b740023ee68f16ca8783cb0a5213600f1ac8`.

Both are regular files with exact `$ORIGIN` RUNPATH. The extension has only the
matched Xe2 grouped library as a custom DSO dependency; the companion resolves
inside this stage. The frozen loader path resolves `libsycl.so.8` to the same
venv runtime used by the accepted serving lane,
`/home/steve/.venvs/vllm-xpu/lib/libsycl.so.8`, SHA-256
`0336997fdfed9b2e6385e9f1cea2395eb5e130d3e5e9c943df5b0c10c1b5e57f`.
SYCL 9 is rejected.

The final tracked kernel source is clean at
`eeee7d671abfa964626baa18da2174bb92cac80a`. The new three-commit source patch
is `patches/qwen38-flash-next-fp8-b70/vllm-xpu-kernels/0007-fix-grouped-gemm-build-contracts.patch`,
SHA-256
`4126ebd2057173128fa5332646cc256d7f5daaa625ec86c18241fbc63e71a194`.
It restores the lab wrapper/header/dispatcher API agreement, passes the missing
4-bit compile-time weight kind, and declares the retained local MoE prologue.
These are build-consistency fixes exposed before execution, not performance
claims.

Build identity:

The retained build-directory name contains `359466a`, the source head at the
start of the build. The final successful retry used and is bound to clean head
`eeee7d6`; the cache, compile-command, build-log, installed-library, and patch
digests below are the authority, not that historical directory label.

- oneAPI compiler `2025.3.3.20260319`;
- Python `3.12.13`, Torch `2.11.0+xpu`;
- Xe2 AOT target `bmg-g21-a0`, Xe-default off;
- MoE and XPU-specific kernels on; basic, FA2, GDN, MQA, and allocator off;
- cached SYCL-TLA commit `cd763790ad2f74d7294435ecf77682bac0062c3a`;
- cached oneDNN commit `80afa71049cd69a3df32adcccb623b12cd7baa22`;
- CMake cache SHA-256
  `d8e723f46211ddb43cdf5ca4809f88d63d6af5c20e0cd4fdb71dcefb3c679b5a`;
- compile commands SHA-256
  `d244a708081dde5a319b744fcadce612a1ec688646d55b2dbfdf1c43683f2198`;
- initial/fix/retry build-log SHA-256 values:
  `a0eacf192e88d52fb78d4c3c498a50bb80512e1cf1a06ad74015ba6806b8c672`,
  `5b7ea96dee676852af04991938b3741a744a21267a33c9e17166695a26536f48`,
  and `00af59a8a240fcf1f15349e424199d1c9f85dcccbdbdf45eedcea6fdb65f1337`.

Registration-only validation passed with the exact 11-argument local schema;
no tensor or model was loaded by that check. This component stage does not
replace or modify the certified deployment stage.

## Frozen harness and interpretation

- arm benchmark SHA-256:
  `68460a1064435e1251405d88037c92d2816e69ff097f167c5b378e03c5b83952`;
- pair driver SHA-256:
  `b41000828aad5abaca064be2406f366f84e2cd3f7d87607be6df1e0a3df7f5f3`;
- seed `20260830`;
- fresh-process control/candidate/control for every pair;
- 100 warmups, 21 XPU-event batches of 100 calls, and 100 exact hashes per
  arm;
- exactly one visible Arc Pro B70, no active vLLM/server process, pair-wide and
  per-arm locks, exclusive evidence creation, and no overwrite;
- every arm must preserve tool, stage, model, shard, input, weight, device,
  shape, dtype, layout, repeat-count, and loader identity;
- nonfinite/nonpositive timing, nonfinite output, within-arm variability, or
  consumed-output mismatch fails closed;
- follow-up eligibility requires exact consumed output, at least 5% latency
  reduction using `(1 - candidate/control) * 100`, and at most 3% drift between
  the two controls.

Even an eligible result remains `hot_weight_component_screen_only`, authorizes
no endpoint claim, changes no protected result, and does not displace the
prepared A29 M1 MoE endpoint candidate.

## Exact commands

The output root must not already exist:

`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/hc-m1-grouped-eeee7d6-seed20260830`

Run the following driver once for each `(layer,projection)` pair, with
`LAYER/PROJECTION` equal to `0/down`, `0/up`, `47/down`, and `47/up`:

```bash
/home/steve/.venvs/vllm-xpu/bin/python \
  experiments/qwen38-flash-next-fp8-b70/tools/run-hc-m1-grouped-gemm-pair.py \
  --runtime-stage /mnt/usb-models/qwen38-build/hc-grouped-stage-eeee7d6-sycl8/vllm_xpu_kernels \
  --model /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8 \
  --model-revision bcd9f01ddc9cff2316eb84281bebcd5b058bddce \
  --layer LAYER --projection PROJECTION --seed 20260830 \
  --output /mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/hc-m1-grouped-eeee7d6-seed20260830/layer-LAYER-PROJECTION.json
```
