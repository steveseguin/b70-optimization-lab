# Qwen3.8 Flash-Next FP8 HC M1 grouped-GEMM N352 preregistration

Date: 2026-08-31
Status: frozen before successor component execution

## Boundary and correction

This is the exact successor to the
[N336 preflight negative](2026-08-31-hc-m1-grouped-gemm-n336-preflight-negative.md).
It inherits the model, revision, two checkpoint shards, one-B70 boundary,
component stage, loader closure, kernel source/build identity, seed, repeats,
fresh-process control/candidate/control order, no-clobber rules, and frozen
interpretation from the original
[preregistration](2026-08-30-hc-m1-grouped-gemm-prereg.md) at repository commit
`9fffe5f37bc86234b0d6786a33b7fa8366271b53`.

The only candidate arithmetic-shape correction is down-projection padding: the
same ordered 324 real BF16 output rows are followed by 28 zero rows, producing
`[N,K]=[352,10240]`. The Xe2 grouped interface requires `N % 32 == 0`; the
harness now checks `N` and `K` before the first timed grouped call. The linear
controls remain at the production `[N,K]=[336,10240]` shape with 12 zero rows.
Exact parity is judged only on the first 324 production-consumed outputs, and
the known layer-0/down production authority hash is frozen in the driver. The
up shape is unchanged at `[N,K]=[10240,320]` for both providers and already
satisfies the same alignment.

## Frozen identity and gates

- runtime stage:
  `/mnt/usb-models/qwen38-build/hc-grouped-stage-eeee7d6-sycl8/vllm_xpu_kernels`;
- runtime manifest SHA-256:
  `71e263f19ccc1313bbdc21604b4de5171891454fb7e8e35877af083505522951`;
- arm benchmark SHA-256:
  `8b0486685e4167a3d9b4970d40635dd75b031792ef27ade71e27a5ae285af3b0`;
- pair driver SHA-256:
  `650efd1e807845f9125150a7390b5c7cf6222d18a136e68d7d2c83f17d8008e7`;
- seed `20260830`;
- 100 warmups, 21 XPU-event batches of 100 calls, and 100 exact hashes per arm;
- follow-up eligibility still requires exact consumed output, at least 5%
  candidate latency reduction, and no more than 3% control drift;
- any eligible result remains `hot_weight_component_screen_only` and cannot
  authorize an endpoint claim or alter protected Qwen results.

The old evidence root is immutable. The successor root must not already exist:

`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/hc-m1-grouped-eeee7d6-n352-seed20260830`

For `LAYER/PROJECTION` equal to `0/down`, `0/up`, `47/down`, and `47/up`, run:

```bash
/home/steve/.venvs/vllm-xpu/bin/python \
  experiments/qwen38-flash-next-fp8-b70/tools/run-hc-m1-grouped-gemm-pair.py \
  --runtime-stage /mnt/usb-models/qwen38-build/hc-grouped-stage-eeee7d6-sycl8/vllm_xpu_kernels \
  --model /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8 \
  --model-revision bcd9f01ddc9cff2316eb84281bebcd5b058bddce \
  --layer LAYER --projection PROJECTION --seed 20260830 \
  --output /mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/hc-m1-grouped-eeee7d6-n352-seed20260830/layer-LAYER-PROJECTION.json
```
