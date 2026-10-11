# Reference-runtime baseline screen

Unmodified llama.cpp reference-runtime baseline, not our runtime; not certified. These are 64-token screening runs, not the realistic final gate or a lossless CPU-oracle pass.

Decode and prompt rates are runtime-reported tokens/s. Prompt rates use each prompt’s actual input length, not a measured 512-token prefill benchmark. Generated tokens exclude EOG: the pinned completion loop generates 64 tokens with 63 timed decode runs at the cap; immediate EOG is 0. Early EOG counts use the retained stdout end marker. Unknown counts are —.

Byte-equal compares hash-verified retained stdout from two successful processes, including the CLI end marker; it does not establish token-oracle parity or useful output. Missing, failed, empty or unverified output is unassessed. Medians exclude failed/missing/nonfinite/zero rates and retain immediate-EOG prompt rates. Runs from different directories are never pooled.

## experiments/qwen38-flash-next-ud-iq3xxs-b70/baseline-llamacpp/runs/window-20261011-boot13858eef

Status: **FAULT / partial**; 9/24 rows recorded. Medians below describe observed rows only, including pre-fault rows if the window faulted.

ONEAPI_DEVICE_SELECTOR: `level_zero:0,1`; llama --device: `SYCL0,SYCL1`; plan: `not recorded`.

| Prompt | R1 decode tok/s | R2 decode tok/s | R1 prompt tok/s | R2 prompt tok/s | R1 generated | R2 generated | Byte-equal | R1 / R2 status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| incident-retrospective | 26.85 | — | 57.52 | — | 64 | — | unassessed | ok / missing |
| code-review | — | — | 49.21 | — | 0 | — | unassessed | ok / missing |
| customer-email | 25.93 | — | 47.04 | — | 64 | — | unassessed | ok / missing |
| sql-debugging | 25.62 | — | 52.58 | — | 64 | — | unassessed | ok / missing |
| release-plan | 26.06 | — | 49.03 | — | 64 | — | unassessed | ok / missing |
| benchmark-analysis | 25.65 | — | 44.33 | — | 64 | — | unassessed | ok / missing |
| architecture-tradeoff | 26.08 | — | 43.58 | — | 64 | — | unassessed | ok / missing |
| bug-report-synthesis | 25.88 | — | 45.13 | — | 64 | — | unassessed | ok / missing |
| technical-guide | 25.65 | — | 44.38 | — | 64 | — | unassessed | ok / missing |
| risk-register | — | — | — | — | — | — | unassessed | missing / missing |
| performance-hypotheses | — | — | — | — | — | — | unassessed | missing / missing |
| decision-memo | — | — | — | — | — | — | unassessed | missing / missing |

| Observed-row median | Decode tok/s (n) | Prompt tok/s (n) |
| --- | ---: | ---: |
| repeat1 | 25.91 (8) | 47.04 (9) |
| repeat2 | — (0) | — (0) |
| all observed | 25.91 (8) | 47.04 (9) |
