# Native GDN Output RMSNormGated Spike: No Endpoint Win

Date: 2026-07-05

## Question

Can a Qwen3Next-specific native XPU op for the GDN output norm
`RMSNormGated(core_attn_out, z)` reduce target-forward cost enough to improve
the current webhie BF16-scale INT8-LM-head MTP3/cg8 record family?

This is a low-risk target because it does not alter speculation policy,
accepted-token semantics, caching, or model quantization.

## Patch

Preserved patches:

- XPU kernel/source:
  `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-kernels-gdn-output-norm-native-no-win-20260705.patch`
- vLLM default-off integration:
  `patches/qwen36-27b-autoround-int4-b70/vllm-gdn-output-norm-native-integration-no-win-20260705.patch`

Patch summary:

- Added `_xpu_C.gdn_rms_norm_gated_xpu` and `_xpu_C.gdn_rms_norm_gated_xpu_out`.
- Added fake registrations so Dynamo can compile through the custom op.
- Wired XPU GDN output norm behind default-off
  `VLLM_XPU_GDN_NATIVE_OUTPUT_NORM=1`.

## Direct Microbench

Shape: rows `1/2/4/8/16/32`, hidden `5120`, BF16 `x,z`, FP32 weight, B70/XPU.

The native out variant measured roughly `0.0069-0.0075 ms` versus a raw eager
PyTorch reference around `0.131-0.134 ms`, so the kernel itself is fast and the
math is BF16-close (`~0.03` max absolute error for silu-gated output on random
values).

Important caveat: the real endpoint path is compiled/captured, not the raw
eager PyTorch expression, so the direct microbench only justified an endpoint
screen; it did not prove a serving win.

## Endpoint Candidate

Label:
`qwen27-webhie-bf16scale-native-gdn-outputnorm-20260705T195618Z`

Config:

- current webhie BF16-scale INT8-LM-head MTP3/cg8 recipe;
- strict fresh Qwen realistic suite, each prompt once, `cached_tokens=0`;
- `VLLM_XPU_GDN_NATIVE_OUTPUT_NORM=1`;
- quality repeat32, long context skipped for the fast source screen.

Artifacts:

- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-native-gdn-outputnorm-20260705T195618Z-candidate-summary-20260705T195618Z.json`
- strict bench:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-native-gdn-outputnorm-20260705T195618Z-realistic128-chat-tokenids-qwensuite-20260705T195618Z.json`
- quality:
  `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-webhie-bf16scale-native-gdn-outputnorm-20260705T195618Z-repeat32-ctx1024-20260705T195618Z.json`
- server log:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-webhie-bf16scale-native-gdn-outputnorm-20260705T195618Z-20260705T195618Z/server.stdout.log`

Result:

- strict fresh gate passed;
- `cached_tokens=0` on all 12 prompts;
- quality passed and matched baseline (`pass_all=true`,
  `baseline_match_all=true`);
- median `65.48800613760292 tok/s`, p10 `59.86540598941055`, mean
  `64.98760425850242`, TTFT median `620.17 ms`.

This is only `+0.32%` versus the promoted `65.27648650325429 tok/s` record, so
it is inside the known variance band and cannot be treated as a headline win.

## Same-Window Four-GPU Check

To avoid mistaking variance for progress, a same-window strict support screen
ran two controls and two native-output-norm candidates:

| Run | GPU | Median tok/s | p10 | Mean | Gate |
| --- | --- | ---: | ---: | ---: | --- |
| control | 0 | `64.92748443974531` | `54.353400` | `63.198283` | pass |
| native output norm | 1 | `64.47892091733031` | `57.713926` | `63.776173` | pass |
| control | 2 | `65.6703702712424` | `57.873900` | `64.828773` | pass |
| native output norm | 3 | `64.6587557366867` | `57.537056` | `64.091117` | pass |

Average controls: `65.29892735549386 tok/s`.

Average native: `64.5688383270085 tok/s`.

Delta: `-0.7300890284853523 tok/s`, `-1.118%`.

## Conclusion

Closed no-win. The standalone kernel is fast and quality-safe, but the endpoint
does not improve; the likely reason is that output norm is already a small
compiled/captured part of the target forward, and replacing it with an external
custom op adds integration overhead without reducing the dominant target/MTP
forward buckets.

Do not submit to LocalMaxxing and do not keep this path enabled in the active
runtime. Only revisit if a future trace shows `qwen3_next.gdn.output_norm` as a
large standalone region after another source change.
