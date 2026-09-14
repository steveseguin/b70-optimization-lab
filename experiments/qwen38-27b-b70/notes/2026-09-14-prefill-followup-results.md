# Three additional short-prefill baselines

Completed September 14, 2026 UTC (September 13 EDT) on the two-ASRock-B70
host. Three useful published setups now have measured 512-token reading
speeds. **No runtime optimization or new decode record is promoted.**
All selected servers are stopped and both-card compute/XCCL and journal
postflights passed. No power, swap, page-cache, driver or reboot changes.

## Measured reading speed

One user, exactly 256 or 512 input tokens, no saved prompt cache. These are
server prefill measurements: input tokens divided by vLLM’s time from first
scheduled execution to first token. HTTP time to first token is measured
separately; it includes more than prompt processing.

| Model / setup | Input tokens | Prefill ms | Input tokens/s | HTTP first-token wait ms |
| --- | ---: | ---: | ---: | ---: |
| Qwen3.5 4B W4A16 · 2 GPUs · MTP3 | 256 | 41.81 | 6,122.95 | 43.85 |
| Qwen3.5 4B W4A16 · 2 GPUs · MTP3 | 512 | 69.50 | 7,366.87 | 71.72 |
| Qwen3.5 9B W4A16 · 2 GPUs · MTP3 | 256 | 64.69 | 3,957.40 | 69.56 |
| Qwen3.5 9B W4A16 · 2 GPUs · MTP3 | 512 | 115.85 | 4,419.39 | 121.01 |
| Qwen3.8 27B INT4 · 1 GPU · MTP4 | 256 | 221.32 | 1,156.69 | 230.57 |
| Qwen3.8 27B INT4 · 1 GPU · MTP4 | 512 | 423.60 | 1,208.71 | 446.71 |

Each point has 18 measured requests: three repetitions for each of prose,
code and structured documentation in each of two control arms. Each arm takes
a median within each class, then a median across classes; the reported value
is the arithmetic mean of the two arm aggregates. Warmups are excluded.
The complete individual measurements, raw SSE, numeric inputs and outputs,
metric snapshots, launch logs and original references are retained in the
[hash-bound evidence manifest](../data/2026-09-14-prefill-followup/evidence/manifest.json).

Inputs are unrepeated repository excerpts, truncated to exact numeric token
lengths. The timing screen uses 128 outputs with `ignore_eos`. It is separate
from the full natural-completion quality suite. The [earlier four measurements](2026-09-13-short-prefill-results.md)
used repeated/truncated short paragraphs and different setup identities; do
not derive a matched GPU-scaling speedup from the two campaigns.

## Quality and decode checks

All 108 measured prefill requests reported zero cached tokens and repeated
exactly across the two control arms. Every setup also passed the full
12-prompt natural-completion suite with a 512-token cap and objective canaries.
All 36 complete strict outputs matched their qualified historical references.

| Setup | Strict decode now | Historical reference | Difference | Complete outputs | Maximum prefill control drift |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5 4B W4A16 · 2 GPUs · MTP3 | 247.85 tok/s | 247.45 tok/s | +0.16% | 12/12 exact | 0.86% |
| Qwen3.5 9B W4A16 · 2 GPUs · MTP3 | 177.54 tok/s | 177.24 tok/s | +0.17% | 12/12 exact | 0.24% |
| Qwen3.8 27B INT4 · 1 GPU · MTP4 | 80.89 tok/s | 81.17 tok/s | -0.34% | 12/12 exact | 0.87% |

These decode differences are historical support checks, not matched
optimization comparisons. They show no meaningful regression in this replay.
Each setup used one continuously loaded server, so no independent-process
prefill or optimization repeat is claimed. Existing qualified defaults and
historical decode records retain their identities.

## Optimization investigation

One diagnostic trace on 4B TP2 found 848 FP16 GEMMs with 32 input rows per rank.
FP16 matrix multiplication is a substantial cost, but the full-vocabulary
projection uses one row rather than all 512 prompt rows. Summed traced FP16
device time was 27.4–28.8 ms per rank; these profiling timings include overhead
and are not the unprofiled server duration above.

- The earlier direct-output allocation candidate was reviewed and not rerun;
  its small/inconclusive screen does not become a new improvement.
- A prefill-only CLASSPAD hybrid was considered and declined before patching.
  It changes intermediate arithmetic and needs a separate qualification effort.
- No new runtime candidate was benchmarked or promoted. Retain the defaults.

The [optimization review](2026-09-14-prefill-optimization-review.md) and
[trace analysis](../data/2026-09-14-prefill-trace-analysis.json) preserve the
operator shapes, both-rank timings, source hashes and limitations. The original
compressed worker traces are included in the evidence packet.

## Identity and replay

All three baselines use the unmodified published R304 vLLM XPU 0.29.0 image
`sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2`,
FP16 activations, native KV, CLASSPAD0/rowchunk32, a 67,248-row draft shortlist,
fixed MTP3 for 4B/9B or MTP4 for 27B, one active sequence, 1024 context/batch
budget, no prefix caching and the public graph settings. The existing launcher
verified all 17 runtime files and each model file through direct and ordinary
reads. The 4B profiler was configured at launch but activated only for its
separate one-output-token trace between the measured control arms.

Configuration and stopping rules: [preregistration](2026-09-14-prefill-followup-prereg.md).
Exact values and identities: [summary](../data/2026-09-14-prefill-followup/summary.json).
Offline replay receipt: [verification](../data/2026-09-14-prefill-followup/verification.json).

From the repository root, verify every archive/source hash and recompute the
published aggregates, cache checks and full-output comparisons without GPUs:

```bash
python3 experiments/qwen38-27b-b70/scripts/verify-prefill-followup-evidence.py
```

The [client](../scripts/bench-prefill-followup.py), [single-stage controller](../scripts/run-prefill-followup-stage.py),
[collector](../scripts/summarize-prefill-followup.py) and [exporter](../scripts/export-prefill-followup-evidence.py)
preserve the measurement method without changing the prior frozen campaign.

LocalMaxxing disposition: withheld. These are prefill baselines and profiling
evidence, not new qualified decode submissions.

## Remaining gaps

The [coverage inventory](2026-09-14-prefill-coverage.md) covers all 32 homepage
setups. Other draft choices, the separate 9B FP8 runtime, llama.cpp setups,
and four-card models remain unmeasured at this comparison point. They require
additional model/runtime sessions or unavailable hardware; none is filled
using a nearby length, another setup, a raw-engine test or an HTTP timing proxy.
This closes the selected three-configuration follow-up without expanding the campaign.

## Publication checks

Archive/source hashes and all three raw receipt replays pass. Package/catalog,
renderer, guide, recipe, link and manifest-path checks pass. Desktop and mobile
inspection covered all three affected details pages and the homepage, graph
labels/tooltips, exact tables, evidence links, copy buttons, missing states,
and no-JavaScript reading. See the [browser receipt](../data/2026-09-14-prefill-followup/browser-check.json).

The hash-pin audit found 231 existing historical Flash-Next references drifted
across two unrelated verifier files; zero targets were missing. Those frozen
pins were left unchanged. This follow-up's own source and archive hashes pass.
