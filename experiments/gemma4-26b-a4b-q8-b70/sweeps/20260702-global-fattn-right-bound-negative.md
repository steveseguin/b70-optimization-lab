# Gemma 4 26B Q8: global FlashAttention right-bound negative

Date: 2026-07-02

Purpose: test a host-derived exact right-bound tensor for global causal
FlashAttention prefill. The intended win was to avoid the SYCL-side mask scan
for `KV_max` in large global-attention prefill tiles, analogous to the prior
SWA left-bound service lane.

This is a service/prefill diagnostic, not a LocalMaxxing short-decode headline.

## Source / Patch Artifacts

- Pre-experiment dirty-tree snapshot:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702T054719Z-pre-global-fattn-right-bound.patch`
- Built experiment snapshot:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702T061300Z-global-fattn-right-bound-built.patch`
- Repro wrapper:
  `repro/gemma4-26b-a4b-q8-b70/run-vdr2-globalrb-service-confirm.sh`

Implementation summary:

- added optional `src[6]` right-bound tensor to `FLASH_ATTN_EXT`;
- built `attn_inp_kq_right_bound` on host with exact mask-equivalent right edge;
- SYCL tile/vector kernels clamp `k_VKQ_max` to the max right-bound across the
  query columns in the tile;
- gated by:
  - `LLAMA_EXPERIMENTAL_GLOBAL_FATTN_RIGHT_BOUND=1`;
  - `LLAMA_EXPERIMENTAL_GLOBAL_FATTN_RIGHT_BOUND_MIN_Q=2048`.

## Build

The first rebuild failed at final host link with unresolved SYCL/OpenMP symbols
because the oneAPI runtime environment was not sourced. Re-running the same
target after:

```bash
source /opt/intel/oneapi/setvars.sh --force
cmake --build build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 --target llama-server -j 8
```

succeeded. The rebuilt binary reported:

```text
version: 9769 (c926ad098)
built with IntelLLVM 2026.0.0 for Linux x86_64
```

## Smoke

One-lane active-path smoke:

- aggregate: `data/gemma4-long-context-service-gate-20260702T061300Z-globalrb-smoke.json`
- run dir: `data/gemma4-q8-gpu0-longctx-globalrb-smoke-ctx32768-o96-20260702T061300Z-globalrb-smoke/`
- case: `lc-12288-early`, actual prompt tokens `16213`
- exact JSON validation: pass
- `cached_tokens=0`
- canary: pass
- approximate prefill: `1221.063903 tok/s`
- long-context decode: `127.267874 tok/s`

The smoke proved the path was runnable but was not enough to claim a win.

## A/B + GPU Crossover

Command:

```bash
STAMP=20260702T061900Z-globalrb-onecase \
BASE_PORT=18640 \
LONG_CONTEXT_CASE_IDS='lc-12288-early' \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=13000 \
CANARY_REPEATS_LONG=1 \
MAX_TOKENS_LONG=96 \
READINESS_TIMEOUT_S=900 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-globalrb-service-confirm.sh
```

Comparison artifact:

- `data/gemma4-globalrb-comparison-20260702T061900Z-globalrb-onecase.json`

All eight lanes passed:

- exact JSON validation;
- canary;
- `cached_tokens=0`.

Result:

| variant | lanes | mean prefill tok/s | median prefill tok/s | mean decode tok/s |
|---|---:|---:|---:|---:|
| control | 4 | `1221.324446` | `1224.909956` | `126.782822` |
| globalrb | 4 | `1206.916212` | `1208.678239` | `126.672276` |

Candidate delta: `-1.179722%` mean prefill versus control.

## Decision

Negative. The source path is correct enough to pass the long-context gate, but
it does not improve the current service stack and slightly regresses the paired
prefill measurement. Do not promote or leave this patch active in the source
tree.

Likely reason: after the prior SWA-left-bound and DV512/GQA8 service work, the
remaining global `KV_max` scan is not the dominant cost for this shape; the
extra right-bound input and per-tile right-bound loads add overhead without
offsetting enough scan work.

Next better lanes:

- return to verifier/decode work for the fresh-response short record;
- for prompt processing, look at larger structural global-FA scheduling changes
  or prompt-phase-only memory/kernel reductions rather than per-tile bound
  metadata.
