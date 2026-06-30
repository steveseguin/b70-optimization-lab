# Gemma 4 26B Q8 FA-on 32K/VMM P-Min Gap Screen

Date: 2026-06-30

Status: **closed negative**. Do not full512-confirm or submit.

Purpose: close the small remaining `p_min` neighborhood gap around the current
record setting after a read-only audit found these values had not been compared
under the latest FA-on 32K/VMM selected-down VDR2 stack.

This was a bounded strict128 screen only. It is not a LocalMaxxing/headline
result and does not replace the full512 strict record at
`121.41411987308553 tok/s`.

## Identity

Common run identity:

- target/verifier: Gemma 4 26B A4B `UD-Q8_K_XL`;
- draft: Q4_0 MTP draft;
- hardware: one Intel Arc Pro B70 per run, four GPUs used in parallel;
- llama.cpp commit: `c926ad098`;
- `FLASH_ATTN=on`;
- `CTX_SIZE=32768`;
- `GGML_SYCL_ENABLE_VMM=1`;
- `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`;
- `THREADS=8`, `POLL=100`;
- VDR2 selected-down fused weighted-sum:
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`;
- F16 p021 small-ncols and bulk sampled-ID verifier host read enabled;
- `n_max=3`, `n_min=2`;
- `MAX_TOKENS=128`;
- fixed realistic prompt suite, each prompt once;
- `cached_tokens=0` for every request;
- no prompt/KV/context/response reuse, n-gram/history acceleration, or warmed
  repeated prompt averaging;
- all lanes passed `realistic_final_gate.passed=true` and canary.

Only `--spec-draft-p-min` changed.

## Results

Primary metric is median generated-token throughput for tokens 1-100 after
TTFT across the fixed realistic suite.

| GPU | `p_min` | Gate | Canary | Median 1-100 | p10 | Mean | Full128 after TTFT | Wall full128 | TTFT ms | Summary |
|---:|---:|:---:|:---:|---:|---:|---:|---:|---:|---:|---|
| 0 | 0.04625 | pass | 128/128 | 115.154972 | 107.455531 | 115.930003 | 113.677799 | 97.530848 | 178.659 | `data/gemma4-q8-gpu0-faon-vmm-selecteddown-n3-nmin2-p004625-strict128-20260630T021544Z/summary.json` |
| 1 | 0.04725 | pass | 128/128 | 113.275964 | 102.730590 | 114.540576 | 110.273319 | 94.336294 | 180.318 | `data/gemma4-q8-gpu1-faon-vmm-selecteddown-n3-nmin2-p004725-strict128-20260630T021544Z/summary.json` |
| 2 | 0.047625 | pass | 128/128 | **118.417767** | 107.452389 | 119.185633 | 115.707075 | 99.119992 | 179.724 | `data/gemma4-q8-gpu2-faon-vmm-selecteddown-n3-nmin2-p0047625-strict128-20260630T021544Z/summary.json` |
| 3 | 0.04875 | pass | 128/128 | 118.160708 | 102.695398 | 116.996649 | 115.942842 | 99.161303 | 179.915 | `data/gemma4-q8-gpu3-faon-vmm-selecteddown-n3-nmin2-p004875-strict128-20260630T021544Z/summary.json` |

Comparison points:

- Matching-stack `p_min=0.0475` controls from
  `20260629-faon-vmm-depthscreen-negative.md` measured
  `119.79709987498046` and `119.51944277144372 tok/s` in strict128.
- `p_min=0.0500` on the matching stack measured only
  `115.0386426314836 tok/s`.
- The active full512 headline remains `121.41411987308553 tok/s`.

## Decision

- No candidate beats the matching-stack `p_min=0.0475` strict128 controls.
- Do not full512-confirm any of these values.
- Keep the promoted recipe at `n_max=3`, `n_min=2`, `p_min=0.0475`,
  `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`.
- Treat this as closing the remaining threshold-only gap for the current
  FA-on 32K/VMM selected-down VDR2 identity. Future short-record work should
  return to source-level verifier-cost reduction, not more isolated p_min
  roulette.
