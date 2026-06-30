# 2026-06-30 Per-Layer Post-Norm Residual Fusion

Status: **valid strict128 screen, small/inconclusive, not promoted**.

## Question

After `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1` produced the current
valid record, test the analogous per-layer embedding post-norm + residual add:

- source flag: `LLAMA_GEMMA4_FUSED_PER_LAYER_POST_NORM_RESIDUAL=1`;
- code path: `build_norm(cur, per_layer_post_norm)` + `ggml_add(pe_in, cur)`
  guarded into `ggml_rms_norm_scale_add(..., per_layer_post_norm, pe_in, eps)`;
- default-off, so the promoted recipe is unchanged unless the flag is enabled.

## Patch Artifacts

- before source snapshot:
  `../../../../patches/gemma4-26b-a4b-q8-b70/20260630-before-perlayer-postnorm-fusion-source.patch`;
- after source snapshot:
  `../../../../patches/gemma4-26b-a4b-q8-b70/20260630-after-perlayer-postnorm-fusion-source.patch`;
- after diffstat:
  `../../../../patches/gemma4-26b-a4b-q8-b70/20260630-after-perlayer-postnorm-fusion-source.diffstat`.

The llama.cpp checkout already includes the broader Gemma optimization stack, so
the source snapshots are intentionally larger than this one hunk. The specific
new flag/hunk is visible around `src/models/gemma4.cpp` as
`LLAMA_GEMMA4_FUSED_PER_LAYER_POST_NORM_RESIDUAL` and callback
`per_layer_post_norm_residual_fused`.

Harness updates:

- `repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh` passes the new
  env flag;
- `scripts/run-gemma4-26b-first-baseline.sh` records it in launcher identity;
- `scripts/build_gemma4_realistic_localmaxxing_payload.py` includes it in
  metadata if a future result is submitted;
- `scripts/run-gemma4-26b-llamacpp-replica.sh` prints it in the launch summary.

## Validation Screen

Four parallel strict128 cold-suite lanes were run on the current FA-on 32K/VMM
selected-down VDR2 record stack:

```bash
GPU_INDEX=0 PORT=18480 FLASH_ATTN=on CTX_SIZE=32768 GGML_SYCL_ENABLE_VMM=1 \
MAX_TOKENS=128 CANARY_REPEATS=128 \
LLAMA_GEMMA4_FUSED_PER_LAYER_POST_NORM_RESIDUAL=0 \
LABEL=gemma4-q8-gpu0-perlayer-control-strict128-20260630T0353Z \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh

GPU_INDEX=1 PORT=18481 ... LLAMA_GEMMA4_FUSED_PER_LAYER_POST_NORM_RESIDUAL=1 \
LABEL=gemma4-q8-gpu1-perlayer-on-strict128-20260630T0353Z ...

GPU_INDEX=2 PORT=18482 ... LLAMA_GEMMA4_FUSED_PER_LAYER_POST_NORM_RESIDUAL=0 \
LABEL=gemma4-q8-gpu2-perlayer-control-strict128-20260630T0353Z ...

GPU_INDEX=3 PORT=18483 ... LLAMA_GEMMA4_FUSED_PER_LAYER_POST_NORM_RESIDUAL=1 \
LABEL=gemma4-q8-gpu3-perlayer-on-strict128-20260630T0353Z ...
```

All four lanes passed:

- fixed realistic cold final gate;
- `cached_tokens=0`;
- canary `512/512` rows.

## Results

| Lane | Flag | Median tok/s 1-100 after TTFT | p10 | Mean | Full after TTFT | Wall full | TTFT ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GPU0 control | 0 | `117.45355849560057` | `107.99407890180149` | `117.85827203807656` | `114.23574995793811` | `97.7560536839284` | `179.56126458011568` |
| GPU1 per-layer fused | 1 | `119.96280008214512` | `107.86715599627954` | `120.51834830789102` | `118.35610856824567` | `100.6503131050275` | `179.6548599959351` |
| GPU2 control | 0 | `114.16528277401136` | `107.96423335898542` | `116.77341380008745` | `114.07761698035732` | `98.20063656741414` | `178.5097459796816` |
| GPU3 per-layer fused | 1 | `113.66197714370783` | `107.50687232029964` | `116.59915820780692` | `114.73167377154282` | `96.55790933177764` | `179.85481000505388` |

Aggregate:

- controls average primary: `115.80942063480597 tok/s`;
- flag-on average primary: `116.81238861292647 tok/s`;
- apparent average delta: `+1.0029679781204948 tok/s` / `+0.8660504237243849%`;
- controls average full-output after TTFT: `114.15668346914771 tok/s`;
- flag-on average full-output after TTFT: `116.54389116989424 tok/s`.

## Decision

Do **not** promote, full512-confirm, or submit to LocalMaxxing as a short-record
lane.

The run is valid, but the effect is small and GPU-pair-dependent: GPU1 flag-on
beat GPU0 control, while GPU3 flag-on slightly lost to GPU2 control. The best
flag-on strict128 result (`119.963`) is still below the current promoted
full512 headline (`123.67689864739785`). Treat this as an inconclusive small
full-output/service hint, not a reliable short-decode record path.

Keep the source flag default-off and preserve the patch/results for future
service-lane or postnorm-fusion consolidation work.

## Next Action

Stop testing sibling post-norm fusions for the short record unless new profile
evidence shows they sit on a hot boundary. The higher-value short-decode target
remains verifier cost inside the existing target decode boundary:

- accept-prefix / row-adaptive verifier output that preserves the bonus path and
  exact target verification;
- verifier MoE boundary/kernel reduction beyond selected-down VDR2;
- backend sampled-output extraction boundary only if it removes real graph work
  rather than host bookkeeping.
