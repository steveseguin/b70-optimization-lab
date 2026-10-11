# Reference-runtime baseline screen

Unmodified llama.cpp reference-runtime baseline, not our runtime; not certified. These are 64-token screening runs, not the realistic final gate or a lossless CPU-oracle pass.

Decode and prompt rates are runtime-reported tokens/s. Prompt rates use each prompt’s actual input length, not a measured 512-token prefill benchmark. Generated tokens exclude EOG: the pinned completion loop generates 64 tokens with 63 timed decode runs at the cap; immediate EOG is 0. Early EOG counts use the retained stdout end marker. Unknown counts are —.

Byte-equal compares hash-verified retained stdout from two successful processes, including the CLI end marker; it does not establish token-oracle parity or useful output. Missing, failed, empty or unverified output is unassessed. Medians exclude failed/missing/nonfinite/zero rates and retain immediate-EOG prompt rates. Runs from different directories are never pooled.

## /home/steve/llm-optimizations/experiments/qwen38-flash-next-ud-iq3xxs-b70/baseline-llamacpp/runs/window2-twocard-20261011T024653Z

Status: **complete**; 24/24 rows recorded. Medians below describe observed rows only, including pre-fault rows if the window faulted.

ONEAPI_DEVICE_SELECTOR: `level_zero:0,1`; llama --device: `SYCL0,SYCL1`; plan: `twocard`.

| Prompt | R1 decode tok/s | R2 decode tok/s | R1 prompt tok/s | R2 prompt tok/s | R1 generated | R2 generated | Byte-equal | R1 / R2 status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| incident-retrospective | 28.34 | 28.65 | 53.38 | 64.02 | 64 | 64 | yes | ok / ok |
| code-review | — | — | 63.29 | 62.66 | 0 | 0 | yes | ok / ok |
| customer-email | 28.49 | 28.57 | 58.12 | 58.16 | 64 | 64 | yes | ok / ok |
| sql-debugging | 28.61 | 28.63 | 61.95 | 62.64 | 64 | 64 | yes | ok / ok |
| release-plan | 28.49 | 28.55 | 57.30 | 57.35 | 64 | 64 | yes | ok / ok |
| benchmark-analysis | 28.62 | 28.61 | 52.16 | 52.00 | 64 | 64 | yes | ok / ok |
| architecture-tradeoff | 28.54 | 28.15 | 55.68 | 49.91 | 64 | 64 | yes | ok / ok |
| bug-report-synthesis | 28.67 | 28.44 | 54.84 | 49.97 | 64 | 64 | yes | ok / ok |
| technical-guide | 28.38 | 28.34 | 55.03 | 57.31 | 64 | 64 | yes | ok / ok |
| risk-register | 28.37 | 28.46 | 48.34 | 49.94 | 64 | 64 | yes | ok / ok |
| performance-hypotheses | 28.61 | 28.49 | 53.43 | 53.31 | 64 | 64 | yes | ok / ok |
| decision-memo | 28.16 | 28.49 | 49.08 | 50.25 | 64 | 64 | yes | ok / ok |

| Observed-row median | Decode tok/s (n) | Prompt tok/s (n) |
| --- | ---: | ---: |
| repeat1 | 28.49 (11) | 54.94 (12) |
| repeat2 | 28.49 (11) | 55.31 (12) |
| all observed | 28.49 (22) | 54.94 (24) |

## /home/steve/llm-optimizations/experiments/qwen38-flash-next-ud-iq3xxs-b70/baseline-llamacpp/runs/window2-onecard-20261011T024653Z

Status: **complete**; 24/24 rows recorded. Medians below describe observed rows only, including pre-fault rows if the window faulted.

ONEAPI_DEVICE_SELECTOR: `level_zero:2`; llama --device: `SYCL0`; plan: `onecard`.

| Prompt | R1 decode tok/s | R2 decode tok/s | R1 prompt tok/s | R2 prompt tok/s | R1 generated | R2 generated | Byte-equal | R1 / R2 status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| incident-retrospective | 16.03 | 15.40 | 53.54 | 53.08 | 64 | 64 | yes | ok / ok |
| code-review | — | — | 53.81 | 52.98 | 0 | 0 | yes | ok / ok |
| customer-email | 16.11 | 16.13 | 49.85 | 49.95 | 64 | 64 | yes | ok / ok |
| sql-debugging | 15.78 | 15.46 | 53.56 | 53.33 | 64 | 64 | yes | ok / ok |
| release-plan | 15.73 | 12.63 | 49.98 | 49.69 | 64 | 64 | yes | ok / ok |
| benchmark-analysis | 15.71 | 15.58 | 44.84 | 28.93 | 64 | 64 | yes | ok / ok |
| architecture-tradeoff | 15.88 | 15.98 | 44.14 | 43.63 | 64 | 64 | yes | ok / ok |
| bug-report-synthesis | 16.05 | 15.74 | 46.53 | 45.87 | 64 | 64 | yes | ok / ok |
| technical-guide | 15.73 | 16.06 | 49.06 | 48.57 | 64 | 64 | yes | ok / ok |
| risk-register | 15.57 | 15.96 | 39.04 | 39.46 | 64 | 64 | yes | ok / ok |
| performance-hypotheses | 15.87 | 16.07 | 45.27 | 46.43 | 64 | 64 | yes | ok / ok |
| decision-memo | 16.08 | 16.06 | 43.50 | 43.59 | 64 | 64 | yes | ok / ok |

| Observed-row median | Decode tok/s (n) | Prompt tok/s (n) |
| --- | ---: | ---: |
| repeat1 | 15.87 (11) | 47.80 (12) |
| repeat2 | 15.96 (11) | 47.50 (12) |
| all observed | 15.88 (22) | 47.55 (24) |
