# Reference-runtime baseline screen

Unmodified llama.cpp reference-runtime baseline, not our runtime; not certified. These are 64-token screening runs, not the realistic final gate or a lossless CPU-oracle pass.

Decode and prompt rates are runtime-reported tokens/s. Prompt rates use each prompt’s actual input length, not a measured 512-token prefill benchmark. Generated tokens exclude EOG: the pinned completion loop generates 64 tokens with 63 timed decode runs at the cap; immediate EOG is 0. Early EOG counts use the retained stdout end marker. Unknown counts are —.

Byte-equal compares hash-verified retained stdout from two successful processes, including the CLI end marker; it does not establish token-oracle parity or useful output. Missing, failed, empty or unverified output is unassessed. Medians exclude failed/missing/nonfinite/zero rates and retain immediate-EOG prompt rates. Runs from different directories are never pooled.

## /home/steve/llm-optimizations/experiments/qwen38-flash-next-ud-iq3xxs-b70/baseline-llamacpp/runs/window3-onecard-uncontended-20261011T032319Z

Status: **complete**; 24/24 rows recorded. Medians below describe observed rows only, including pre-fault rows if the window faulted.

ONEAPI_DEVICE_SELECTOR: `level_zero:2`; llama --device: `SYCL0`; plan: `onecard`.

| Prompt | R1 decode tok/s | R2 decode tok/s | R1 prompt tok/s | R2 prompt tok/s | R1 generated | R2 generated | Byte-equal | R1 / R2 status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| incident-retrospective | 15.84 | 15.94 | 54.56 | 53.96 | 64 | 64 | yes | ok / ok |
| code-review | — | — | 53.77 | 54.12 | 0 | 0 | yes | ok / ok |
| customer-email | 15.81 | 16.02 | 48.81 | 51.57 | 64 | 64 | yes | ok / ok |
| sql-debugging | 15.98 | 16.13 | 53.38 | 53.25 | 64 | 64 | yes | ok / ok |
| release-plan | 16.07 | 16.01 | 50.39 | 50.88 | 64 | 64 | yes | ok / ok |
| benchmark-analysis | 15.87 | 15.82 | 44.29 | 43.28 | 64 | 64 | yes | ok / ok |
| architecture-tradeoff | 15.98 | 15.80 | 44.28 | 43.98 | 64 | 64 | yes | ok / ok |
| bug-report-synthesis | 16.03 | 16.04 | 46.13 | 46.20 | 64 | 64 | yes | ok / ok |
| technical-guide | 15.66 | 15.59 | 48.41 | 48.31 | 64 | 64 | yes | ok / ok |
| risk-register | 16.14 | 15.93 | 39.41 | 37.41 | 64 | 64 | yes | ok / ok |
| performance-hypotheses | 15.90 | 15.94 | 46.58 | 46.69 | 64 | 64 | yes | ok / ok |
| decision-memo | 15.99 | 15.91 | 44.15 | 44.26 | 64 | 64 | yes | ok / ok |

| Observed-row median | Decode tok/s (n) | Prompt tok/s (n) |
| --- | ---: | ---: |
| repeat1 | 15.98 (11) | 47.49 (12) |
| repeat2 | 15.94 (11) | 47.50 (12) |
| all observed | 15.94 (22) | 47.50 (24) |
