# 2026-07-01 SWA left-bound fast builder: negative

## Purpose

Test whether a host-side fast path for SWA `kq_left_bound` construction improves
long-context prompt processing for Gemma 4 26B A4B Q8 on one B70 per replica.
The patch is default-off behind `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_FAST=1`
and only attempts the fast path for non-2D, causal, standard-SWA ubatches with
monotonic positions and contiguous non-empty KV cells. It falls back to the
existing exact scanner on any unsupported shape.

## Build note

The first rebuild failed at the final SYCL/OpenMP link because the oneAPI
environment was not sourced. The existing build dir is configured for oneAPI
2026.0 (`/opt/intel/oneapi/compiler/2026.0/bin/icpx`). Rebuilding with:

```bash
source /opt/intel/oneapi/setvars.sh --force
cmake --build /home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 --target llama-server -j 8
```

resolved the link and AOT device build. The rebuilt binary reports:

```text
version: 9769 (c926ad098)
built with IntelLLVM 2026.0.0 for Linux x86_64
```

## Artifacts

- Patch: `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-swa-left-bound-fast-builder.patch`
- Diffstat: `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-swa-left-bound-fast-builder.diffstat`
- Long-context summary: `data/gemma4-long-context-service-gate-20260701Tswa-lb-fast-ab1.json`

The long-context and short-decode wrappers were also fixed to summarize from the
canonical workspace (`/home/steve/llm-optimizations`) instead of stale
`/home/steve/qwen36-results-main`. The long-context wrapper now supports an
optional per-lane SWA fast flag so control and candidate lanes can run in the
same window.

## Validation command

Same-window A/B across all four B70s:

```bash
cd /home/steve/llm-optimizations
source /opt/intel/oneapi/setvars.sh --force
STAMP=20260701Tswa-lb-fast-ab1 \
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1 \
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048 \
LONG_CONTEXT_CASE_IDS="lc-12288-early lc-16384-late lc-22000-middle" \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
CANARY_REPEATS=2 MAX_TOKENS=96 BASE_PORT=18620 READINESS_TIMEOUT_S=900 \
LANE_SPECS="0:2048:1024:swafast-control-a:2048:0 1:2048:1024:swafast-on-a:2048:1 2:2048:1024:swafast-control-b:2048:0 3:2048:1024:swafast-on-b:2048:1" \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh
```

All lanes passed exact long-context validation, canary, and `cached_tokens=0`.

## Results

| Group | Lanes | Median prefill tok/s avg | Median decode tok/s avg | Validity |
| --- | ---: | ---: | ---: | --- |
| Control, `SWA_FAST=0` | 2 | 1127.498 | 119.872 | pass |
| Candidate, `SWA_FAST=1` | 2 | 1118.819 | 119.488 | pass |

Per-lane median prefill tok/s:

- control: `1127.940`, `1127.057`;
- fast: `1111.466`, `1126.172`.

The candidate is about `-0.77%` on prefill and `-0.32%` on long-context decode in
this same-window run.

## Decision

Negative. Do not promote `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_FAST=1`, and do
not run a short-decode guard for this candidate because the long-context service
signal is already worse. Preserve the patch/result so future work does not
rediscover this host-side moving-left-bound path as a likely win.

The next useful prompt-processing direction is not this scanner rewrite. Prefer
profiling where TTFT is now going under the validated phase-prefill/GQA8 service
recipe, or return to decode-side verifier cost work if short-context record work
is higher priority.
