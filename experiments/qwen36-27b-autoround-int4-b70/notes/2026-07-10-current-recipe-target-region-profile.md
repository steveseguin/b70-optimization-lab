# Qwen27 current-recipe target-region profile

Date: 2026-07-10

Status: diagnostic attribution complete; not a headline benchmark and not
LocalMaxxing eligible.

## Identity and limits

Both runs used the exact current record model revision
`webhie/Qwen3.6-27B-int4-AutoRound@f5750c90b3776db658594df5fe8051098226dd8e`,
runtime INT8 target LM-head with BF16 scales, runtime INT4 draft LM-head with
BF16 scales, target-verified MTP3, ReplaySSM, one fresh realistic-suite prompt,
and `cached_tokens=0`. The diagnostic deliberately disabled graph capture and
used `--enforce-eager` plus XPU synchronization around selected Python regions.

Consequently, its one-prompt throughput (`30-31 tok/s`) is intrusive diagnostic
output. It must not be compared with or advertised as the graph-on strict
`68.236 tok/s` record. Region proportions rank work inside the target body;
they do not predict graph-replay latency linearly.

Artifacts outside Git:

- coarse target profile:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/profiles/qwen27-current-recipe-eager-region-profile-20260710T013903Z`;
- GDN drill-down:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/profiles/qwen27-current-recipe-eager-gdn-region-profile-20260710T014224Z`.

Reproduction helper:
`experiments/qwen36-27b-autoround-int4-b70/scripts/profile-current-recipe-regions.sh`.

## Coarse target-body result

The 64-layer target contains 48 GDN linear-attention layers and 16 full
attention layers. Outlier-removed per-layer medians were:

| Region | Median per layer | Approximate 64-layer target contribution |
|---|---:|---:|
| 48 GDN linear-attention layers | 0.785 ms | 37.7 ms (48%) |
| 16 full-attention layers | 1.250 ms | 20.0 ms (25%) |
| 64 MLP regions | 0.333 ms | 21.3 ms (27%) |

The percentages are normalized within those three synchronized categories.
They establish GDN as the largest aggregate target family, but also show that a
100 tok/s result cannot come from a tiny sampler or metadata tweak alone.

## GDN drill-down

For steady decode blocks (blocks 4-7, 48 GDN layers each), median region times
per layer were approximately:

| GDN region | Median |
|---|---:|
| QKVZ projection | 0.135 ms |
| BA projection | 0.105 ms |
| ReplaySSM core operation | 0.413 ms |
| output norm | 0.141 ms |
| output projection | 0.108 ms |
| whole linear-attention layer | 1.219 ms |
| unaccounted allocation/layout/dispatch | 0.316 ms |

The core is about 34% of the synchronized steady GDN layer, projections about
20%, norm/output projection about 20%, and unaccounted work about 26%.
Inspection confirmed that the record recipe does not use the generic native
GDN path that allocates `q/k/v/b/a` and launches ordinary causal-conv plus
gated-delta kernels. `VLLM_XPU_GDN_REPLAYSSM_SPEC=1` routes target verification
through the already-fused `gdn_replayssm_stage_conv` and
`gdn_replayssm_spec_decode` kernels. Do not duplicate that historical fusion.

## Decision

The next code experiment should measure and reduce work across the actual
ReplaySSM boundary: staging allocation/layout, stage-conv, recurrent decode,
pending-state metadata, and output merge. It must be default-off, parity-tested,
and screened under graph-on endpoint execution. A candidate that only improves
an intrusive eager microbenchmark is not a win.

Acceptance-model pre-gates are also being changed from a fixed `3.3` cutoff to
a paired confidence/ROI rule. A statistically credible gain below `3.3` may be
worth an endpoint test, but flat or negative paired results remain closed.
