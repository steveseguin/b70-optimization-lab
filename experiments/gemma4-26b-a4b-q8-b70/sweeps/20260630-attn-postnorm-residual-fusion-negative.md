# 2026-06-30 Attention Post-Norm Residual Fusion Screen

Status: valid strict128 A/B, negative for the short headline metric. Preserve
the default-off patch as an experiment artifact; do not promote or full512
confirm for the current 1-100-token record lane.

## Question

After final post-FFN RMS norm + residual fusion produced the current valid
record, test the analogous attention post-norm shortcut:

`LLAMA_GEMMA4_FUSED_ATTN_POST_NORM_RESIDUAL=1`

The patch replaces:

```text
attn_post_norm = RMS(attn_output) * attn_post_norm_weight
attn_out = attn_post_norm + layer_input
```

with one `ggml_rms_norm_scale_add()` graph op. The source change is default-off
and is preserved in:

- `patches/gemma4-26b-a4b-q8-b70/20260630-before-attn-postnorm-fusion-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/20260630-attn-postnorm-residual-fusion-source.patch`

## Build Note

The first manual build outside oneAPI failed at final link with missing SYCL and
OpenMP symbols after deleting the existing `llama-server` binary. Rebuilding
under `/opt/intel/oneapi/setvars.sh --force` repaired the AOT BMG-G31
`build-sycl-b70-aot-bmg-g31-q8reorder-vdr2` binary. This was a build
environment issue, not a Gemma source compile error.

## Validated Screen

Stamp: `20260630T0341Z`.

All lanes passed:

- fixed realistic cold prompt suite;
- `realistic_final_gate.passed=true`;
- `cached_tokens=0` every request;
- canary `512/512`;
- `headline_eligible_for_gemma_q8=true`.

The harness was updated before this run so `launcher_identity` explicitly
records `llama_gemma4_fused_attn_post_norm_residual`.

| Lane | Flag | Summary | Median 1-100 | p10 | Mean | Full128 | Wall | TTFT ms |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GPU0 | control | `data/gemma4-q8-gpu0-attnpostnorm-control-strict128-20260630T0341Z/summary.json` | 123.377945 | 103.602067 | 119.917921 | 113.634982 | 94.748186 | 177.697845 |
| GPU1 | attention fusion | `data/gemma4-q8-gpu1-attnpostnorm-on-strict128-20260630T0341Z/summary.json` | 117.323277 | 107.765479 | 116.824131 | 118.078907 | 99.549343 | 178.318828 |
| GPU2 | control | `data/gemma4-q8-gpu2-attnpostnorm-control-strict128-20260630T0341Z/summary.json` | 115.345267 | 108.598279 | 116.405510 | 116.632578 | 100.018977 | 179.158378 |
| GPU3 | attention fusion | `data/gemma4-q8-gpu3-attnpostnorm-on-strict128-20260630T0341Z/summary.json` | 116.183904 | 108.455087 | 117.919072 | 117.491458 | 99.409051 | 177.666930 |

Primary metric averages:

- controls: `119.3616057307415 tok/s`;
- attention fusion: `116.75359048324216 tok/s`.

Full-output averages:

- controls: `115.1337798014934 tok/s`;
- attention fusion: `117.78518245705169 tok/s`.

## Decision

Reject for the short headline lane. The attention fusion improved full-output
medians in this screen, but it hurt the primary `tokens 1-100 after TTFT`
metric and did not produce a lane above the current `123.67689864739785 tok/s`
record. Do not spend a full512 promotion run on this as a short-record path.

Possible future use: service/full-output lane only, if a future objective cares
more about full512/wall throughput than the first 100 generated tokens.
