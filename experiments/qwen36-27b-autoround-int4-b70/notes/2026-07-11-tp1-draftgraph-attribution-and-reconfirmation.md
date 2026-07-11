# Qwen27 TP1 draft-graph attribution and reconfirmation

Date: 2026-07-11

## Question

Did the move to TP2 abandon an untested one-GPU draft-graph optimization, and
does the `68.236 tok/s` TP1 result still reproduce under the current source
stack?

## Historical audit

The July 6 TP1 record already used the graph path. Its server log loaded an
`eagle_head` compile graph, initialized the MTP draft during graph warmup, and
captured PIECEWISE sizes `1,2,4,8`. The current code defaults
`VLLM_XPU_DRAFT_DISABLE_CUDAGRAPHS` to `0`; the historical identity did not
override it.

The July 11 TP2 graph patch is not a missing TP1 optimization. TP2 lowered the
compiled draft all-gather through functional `all_gather_into_tensor` plus
`wait_tensor`, and XPU command graphs rejected the event wait. The new opaque
custom-op boundary fixes that distributed operation. TP1 has world size one,
so it has no draft all-gather to fix.

## Four-GPU crossover

The diagnostic harness ran four independent TP1 servers in two swapped
windows. Window 1 assigned graph draft to GPUs 0/1 and eager draft to 2/3;
window 2 swapped the treatments. Every row used the fixed unique prompt suite,
ran each prompt once, passed the strict gate, and reported `cached_tokens=0`.
Quality was intentionally skipped because this was an attribution screen.

| Mode | Rows | Mean of medians | Min | Max |
| --- | ---: | ---: | ---: | ---: |
| graph draft | 4 | `65.1641` | `63.6887` | `66.0733` |
| eager draft | 4 | `65.1958` | `63.9747` | `66.1406` |

Graph delta: **`-0.0487%`**. This is zero at endpoint scale. The intrinsic MTP
drafter is already a small part of the TP1 step; graph capture does not explain
the historical record and is not a new TP1 speed lane.

Raw crossover root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/tp1-draftgraph-crossover-20260711T160307Z
```

Tracked compact summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-tp1-draftgraph-crossover-summary-20260711.json
```

## Isolated full-suite reconfirmation

After the crossover, three one-server-at-a-time runs used the canonical recipe
with `BENCH_MAX_TOKENS=512`:

| GPU | Median tok/s | p10 | Mean | Quality |
| ---: | ---: | ---: | ---: | --- |
| 0 | `65.3587` | `60.5032` | `65.9970` | exact + repeat64 + baseline + 1K pass |
| 1 | `66.7156` | `60.2965` | `66.4469` | skipped after strict pass |
| 2 | `65.4201` | `60.5779` | `65.7726` | skipped after strict pass |

All three strict rows passed with 12 unique cold prompts and zero cached tokens.
The mean of the medians is `65.8314 tok/s`; the range is `2.06%` of that mean.
The mean is `3.52%` below the valid July 6 high of `68.2363`, inside the
established `4.4%` endpoint variance envelope. The exact peak did not repeat,
so use these labels precisely:

- `68.2363 tok/s`: valid historical TP1 high, quality gated and approved on
  LocalMaxxing as `cmr9atqb800msqr01u760xh0t`;
- `65.4-66.7 tok/s`: current July 11 reproduced isolated band;
- no source regression is established from this evidence, but do not describe
  `68.2363` as the expected value of every run.

The fixed suite is greedy (`temperature=0`, `top_p=1`, seed 1), but long-form
output hashes still differed between runs. Small XPU numerical/path variation
changes later greedy branches and MTP acceptance, which is one source of the
endpoint spread. This is why same-window crossover evidence is required for
micro-optimizations.

## Reproduction

Canonical full strict + quality run:

```bash
cd /home/steve/llm-optimizations
GPU_INDEX=0 PORT=19440 \
  experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp1-current-candidate.sh
```

Four-GPU graph attribution:

```bash
cd /home/steve/llm-optimizations
experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp1-draftgraph-crossover-4gpu.sh
```

Compact result packet:

```text
results/qwen36-27b-autoround-int4-b70/tp1-draftgraph-attribution-reconfirm-20260711.json
```

## Decision and next move

TP1 was not proven exhausted, but the draft-graph transfer question is closed.
The prior TP1 kernel screens also closed small RMSNorm, Q/K+RoPE, output-norm,
slot-copy, and eager-reference fusion ideas at endpoint scale. A meaningful
one-GPU gain now requires either lower target verifier/body cost or more
target-verified output tokens per verifier step. Keep TP1 as a separate record
class, but use TP2 for the immediate absolute `100+ tok/s` push because its
current valid base is `82.894 tok/s`.
