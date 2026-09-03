# Qwen3.8 Flash-Next FP8 A72 deterministic graph endpoint result

Date: 2026-09-03 01:05--01:29 EDT
Status: **complete frozen-client pass** (`client-gates-passed.txt`,
`fullgraphdet-runtime-after.json` status passed); third server of the
deterministic graph identity agreeing with A70 and A71 on every output;
promotion candidate pending the user's authority decision

## Server

Full decode graph (`FULL_DECODE_ONLY`, capture size 1), public oneCCL
`4ceafd1` with twoshots, tuned M1 W13-N32 map, PLE-only UVA placement, 2304
max model length, 128 MiB cache, `VLLM_XPU_MKLDNN_DETERMINISTIC=1`, overlay
head `2169dbfe...` (805cde59 plus the V2-runner `CUDAGraphStat` receipt).
Host after the `iommu=pt` reboot with ACS redirect cleared for the boot,
GuC 70.72.1. Load 13 minutes; no hang; no kernel GPU fault.

## Gates

| gate | A72 | A71 | A70 |
| --- | --- | --- | --- |
| recovery canary, identity, twoshots, W13-N32 resolver receipt | pass | pass | pass |
| exact semantic cases | 6/7 (`code_execution=30`) | same | same |
| 16-repeat | 16/16 `3b0b3192...` | same | same |
| exact cache-zero 2K needle | pass | pass | pass |
| short rows (after first text, tok/s) | `24.161593 / 21.876065 / 23.210509` | `22.32/21.50/23.48` | `23.03/24.02/22.58` |
| exact-2K rows (99-interval, tok/s) | `13.176489 / 14.617140` | `14.21/14.08` | `13.26/13.95` |
| exact-2K output hash (both rows) | `afffd2110812...` | same | same |
| runtime receipt: size-1 FULL dispatches | **1213** (table now printed; 7 collective processes) | absent | absent |

Three-attempt short medians: `23.210509` (A72), `22.323215` (A71),
`23.028483` (A70); center `23.028483 tok/s` against A56's single-attempt
native-line `23.626811`. The deterministic flag's served cost on this
identity is therefore about 2.5% at the median, within the row spread.

## What the receipt shows

The first `CUDAGraph Stats` table on this line lists `1 | 1 | 0 | FULL`
for decode steps and `NONE` rows for the 64-token prefill chunks, exactly
the dispatch the identity claims. The V2-runner fix that produced it
changes no dispatch or arithmetic (the outputs match A70/A71).

## Standing

This is the first Flash-Next TP4 endpoint with a complete frozen-client
record on a server proven logit-exact (A66/A67 probes) and repeated across
three fresh servers (A70/A71/A72). Promotion needs the user's decision on
the exact-2K authority: `afffd211...` (deterministic line, three servers)
versus the protected `5fd297f7...` (native line, 2026-08-27). Nothing
protected changed.

Receipts: run dir `...attempt72/`, tracked
[`summary`](../data/20260903-tp4-mtp0-a72-deterministic-graph-endpoint-summary.json)
and [`runtime-after`](../data/20260903-tp4-mtp0-a72-fullgraph-runtime-after.json).
