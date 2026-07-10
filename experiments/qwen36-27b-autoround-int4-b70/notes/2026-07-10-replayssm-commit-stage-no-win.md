# ReplaySSM fused commit-stage experiment (2026-07-10)

## Decision

Closed as a preserved no-win. Do not promote the commit-stage kernel.

The kernel is bitwise correct, but commit-stage alone regressed mean strict
throughput by `0.65%`, and adding it on top of the validated small transaction
fusions changed mean throughput by only `+0.29%` with 95% CI
`[-1.12%, +1.84%]`. No quality cycle or LocalMaxxing submission was justified.

## Design

The default-off `VLLM_XPU_GDN_REPLAYSSM_FUSE_COMMIT_STAGE=1` path tried to:

1. load the old three-column causal-conv history and previous pending rows;
2. commit the accepted prefix in registers and write the resulting history;
3. loop all speculative positions in one `(row, dimension-group)` workgroup;
4. stage Q/K/V/A/B and the next `conv_pending` rows;
5. queue a tiny per-row cursor update after all data workgroups had consumed
   the old pending flag.

The separate metadata kernel was required for correctness. Clearing `pending`
inside one data workgroup would race other dimension workgroups still reading
the old value.

## Correctness guards

All native guards passed before the endpoint screen:

- commit-stage matched sequential native commit plus native stage bit-for-bit
  for Q/K/V, A/B, `conv_state`, `conv_pending`, all cursor metadata, clamped
  accepted counts, an inactive row, variable sequence lengths, and the real
  Qwen convolution width (`10240`);
- the original stage-conv bitwise guard still passed;
- the recurrent and fused pending-metadata guard still passed.

Artifacts are under:

```text
data/qwen36-27b-autoround-int4-b70-profiles/replayssm-commit-stage-20260710/
```

## Strict-fresh screen

The screen used four GPUs, the fixed realistic suite, each prompt once,
`cached_tokens=0`, no history/cache reuse, target-verified MTP3, and no
continuous telemetry observer.

| Lane | Median tok/s | Mean tok/s | p10 |
| --- | ---: | ---: | ---: |
| control | 66.6547 | 66.0953 | 58.6988 |
| validated small fusions | 65.9549 | 67.0374 | 60.6894 |
| commit-stage only | 65.8123 | 65.6073 | 59.0099 |
| all fusions | 68.0278 | 67.1811 | 62.8701 |

Prompt-paired bootstrap comparisons:

- control -> commit-stage: mean `-0.6535%`, CI
  `[-2.3018%, +1.0955%]`, only 3/12 prompts positive;
- small fusions -> all fusions: mean `+0.2888%`, CI
  `[-1.1238%, +1.8416%]`, only 5/12 prompts positive.

The apparent all-fusions versus control gain is explained by the already
validated small fusion plus card/run variance; the incremental commit-stage
effect is not supported.

## Why it likely lost

The original stage kernel exposes one workgroup per speculative position. The
candidate reduced the nominal group count by about 4x, but it also serialized
four positions inside each remaining dimension workgroup and retained old
history plus up to eight pending values in registers. On B70 this likely lost
occupancy/latency hiding and added register pressure. The separate tiny
metadata launch also meant launch count did not fall.

Do not retry this exact layout. A credible successor must either:

- integrate cursor calculation into the recurrent kernel so the metadata
  launch disappears, while retaining enough independent stage workgroups; or
- optimize the existing recurrent kernel's repeated Q/K work across value
  buckets, where arithmetic duplication is larger and parallelism can remain.

## Preserved source

- `patches/qwen36-27b-autoround-int4-b70/vllm-active-with-replayssm-commit-stage-no-win-20260710.patch`
- `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-kernels-active-with-replayssm-commit-stage-no-win-20260710.patch`

The active source should return to the validated small-fusion state after this
record is committed.
