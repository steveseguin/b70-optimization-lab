# Qwen27 full-target graph + ReplaySSM transaction record

## Decision

Promote **`95.384867741895 tok/s`** as the new strict-fresh Qwen3.6 27B
AutoRound INT4 TP2 record on two Intel Arc Pro B70 GPUs. It combines the
quality-clean graph-safe FlashAttention full target graph with two previously
validated exact ReplaySSM transaction fusions:

- recurrent kernel writes pending metadata directly;
- pure-spec recurrent output writes directly into the final GDN core view.

No target weight, quantization, prompt, cache, or acceptance semantics changed.

## Swapped four-GPU crossover

Each window ran candidate and control simultaneously, then swapped the physical
GPU pairs:

| Window | Candidate | Control |
| --- | ---: | ---: |
| candidate 0,1 / control 2,3 | `95.331625` | `87.900916` |
| control 0,1 / candidate 2,3 | `94.523356` | `93.685412` |

Both assignments favored the candidate. Candidate mean of medians was
`94.927491`, control `90.793164` (`+4.5536%`). The first window includes a
large pair/thermal effect, so promotion relies on the isolated confirmation,
not the crossover average.

Tracked crossover:
`data/qwen36-27b-autoround-int4-b70-baselines/qwen27-tp2-fp16-fullgraph-transaction-crossover-20260711.json`.

## Isolated strict and quality confirmation

- median generated tokens 1-100 after TTFT: **`95.384867741895 tok/s`**;
- p10: `86.97541500323224`;
- mean: `95.62305049791388`;
- full-output after-TTFT median: `91.69809656297546 tok/s`;
- wall-clock full-output median: `80.40533067412697 tok/s`;
- TTFT median: `742.3079368891194 ms`.

Validity and quality:

- 12 unique realistic prompts, each sent once cold;
- `cached_tokens=0` for all 12 requests;
- no prefix/KV/history/response/checkpoint reuse;
- target-verified intrinsic MTP3;
- exact arithmetic, copy, and JSON cases passed;
- repeat128 passed;
- complete baseline-output parity passed;
- 1K needle passed.

Tracked evidence:

- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-tp2-fp16-fullgraph-transaction-realistic512-20260711.json`;
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-tp2-fp16-fullgraph-transaction-summary-20260711.json`;
- `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-tp2-fp16-fullgraph-transaction-repeat128-ctx1024-20260711.json`.

## Reproduction

```bash
cd /home/steve/llm-optimizations
GPU_INDEX=0,1 ZE_AFFINITY_MASK=0,1 \
ONEAPI_DEVICE_SELECTOR=level_zero:0,1 PORT=19622 \
RUN_QUALITY=1 QUALITY_REPEAT_RUNS=128 BENCH_MAX_TOKENS=512 \
experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-fullgraph-transaction-candidate.sh
```

This remains a short-context record lane. Forced chunk decode scales poorly at
long context; the graph-safe paged-decode follow-up remains separate.
