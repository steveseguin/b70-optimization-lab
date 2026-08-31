# Qwen3.8 Flash-Next FP8 HC grouped-GEMM alternating preregistration

Date: 2026-08-31
Status: frozen before component execution

## Question and boundary

Five exact up-projection brackets showed the grouped candidate 62.76--74.34%
faster, but two brackets exceeded the preregistered cross-process control-drift
cap. This discriminator asks whether the effect survives paired, alternating
measurement inside one XPU process, where every cycle shares the same loaded
real weight, input, runtime, and device state.

This remains a one-B70 hot-weight component test. It performs no reboot,
server, full checkpoint load, source integration, or endpoint request. Even a
pass authorizes only a broader 48-layer round-robin component screen.

## Frozen design

- model/revision, layer-0/layer-47 up-weight hashes, input seed, component
  stage, manifest, loader closure, and SYCL 8 identity are inherited exactly
  from the prior frozen screens;
- alternating tool SHA-256:
  `53f3991db81942bdca4a7562a385554e109c9c207d9086a8a946bd514c081d9c`;
- four-file aggregate checker SHA-256:
  `9f5de295127c17abecfaf4592ca3c4f7314e4981e31f815b88ae153b23b594d6`;
- frozen core SHA-256:
  `8b0486685e4167a3d9b4970d40635dd75b031792ef27ade71e27a5ae285af3b0`;
- frozen pair-driver SHA-256:
  `650efd1e807845f9125150a7390b5c7cf6222d18a136e68d7d2c83f17d8008e7`;
- two fresh processes for each sampled layer;
- per process: 100 alternating warmups, 31 paired cycles of 100 calls, and 100
  additional alternating exact-output repeats;
- cycle order alternates linear/grouped then grouped/linear;
- the full 10,240-element BF16 output must match exactly in every cycle and
  repeat, with one output hash overall and equality to the production authority
  frozen before the first grouped call;
- each file binds its exact repeat/path plus boot ID, PID, process-start ticks,
  and a 256-bit invocation nonce; the aggregate requires four distinct process
  identities and matching frozen authorities across repeats;
- every process requires median paired reduction at least 50%, every-cycle
  reduction at least 20%, and at most 10 percentage points difference between
  the two order-specific median reductions;
- the family gate passes only if all four processes pass.

Each individual result permanently sets
`round_robin_component_screen_authorized=false`. Only the separately frozen
aggregate checker may set it true after binding and independently recomputing
the exact four expected files, identities, cycle reductions, order bias, and
process decisions.

The thresholds are intentionally far below the observed 62.76--74.34% median
effect but far above timing noise. No threshold may be changed after execution.

## Exact invocation

The output roots below must not exist:

- `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/hc-m1-grouped-up-alternating-r1-seed20260830`;
- `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/hc-m1-grouped-up-alternating-r2-seed20260830`.

The aggregate output must also be absent:

`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/hc-m1-grouped-up-alternating-summary-seed20260830.json`

For each `REPEAT` in `r1 r2` and `LAYER` in `0 47`, use the exact loader path
and run:

```bash
export ONEAPI_DEVICE_SELECTOR=level_zero:0
export PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1
export LD_LIBRARY_PATH=/mnt/usb-models/qwen38-build/hc-grouped-stage-eeee7d6-sycl8/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:/opt/intel/oneapi/compiler/2025.3/lib:/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib
/home/steve/.venvs/vllm-xpu/bin/python \
  experiments/qwen38-flash-next-fp8-b70/tools/benchmark-hc-m1-grouped-gemm-alternating.py \
  --runtime-stage /mnt/usb-models/qwen38-build/hc-grouped-stage-eeee7d6-sycl8/vllm_xpu_kernels \
  --model /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8 \
  --model-revision bcd9f01ddc9cff2316eb84281bebcd5b058bddce \
  --repeat REPEAT --layer LAYER --seed 20260830 \
  --output /mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/hc-m1-grouped-up-alternating-REPEAT-seed20260830/layer-LAYER-up.json
```

After all four processes finish, run exactly:

```bash
python3 \
  experiments/qwen38-flash-next-fp8-b70/tools/summarize-hc-m1-grouped-gemm-alternating.py
```
