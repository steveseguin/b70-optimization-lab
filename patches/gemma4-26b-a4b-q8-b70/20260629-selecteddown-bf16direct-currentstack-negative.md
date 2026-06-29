# 2026-06-29 Selected-Down BF16 Direct Retest

Status: **closed negative** for the current VDR2 selected-down record stack.

## Context

The earlier `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_BF16_DIRECT=1` branch was
closed negative on 2026-06-28, but the current promoted recipe has since moved
to the VDR2 selected-down fused weighted-sum stack. A current-stack retest was
reasonable because the node profile still showed BF16 `MUL_MAT_ID` work near
the top of the decode profile.

Before the retest, the AOT VDR2 build tree had dangling `libggml-sycl.so`
symlinks from an interrupted source experiment. It was repaired by rebuilding:

```bash
cd /home/steve/src/llama.cpp-gemma-record-repro-c926
source /opt/intel/oneapi/setvars.sh --force >/dev/null
cmake --build build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 --target ggml-sycl -j 8
```

The rebuilt library resolved correctly via `ldd`.

## Strict128 Screen

All four lanes used the fixed realistic cold suite, each prompt once, no
cache/history reuse, and `cached_tokens=0` except where explicitly noted.

| Lane | Summary | Median 1-100 | p10 | Mean | Full128 after TTFT | Wall full128 | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| control GPU0 | `data/gemma4-q8-gpu0-selecteddown-bf16retest-control-strict128-20260629T050957Z/summary.json` | 115.31490782465856 | 100.72807312717013 | 114.53370847604039 | 108.74649622919776 | 94.39295175162559 | valid control |
| control GPU1 | `data/gemma4-q8-gpu1-selecteddown-bf16retest-control-strict128-20260629T050957Z/summary.json` | 114.65044043013646 | 104.09484856785859 | 113.97722064119215 | 113.52404248490154 | 97.2408997414604 | valid control |
| BF16 direct GPU2 | `data/gemma4-q8-gpu2-selecteddown-bf16direct-strict128-20260629T050957Z/summary.json` | 116.01878647461015 | 94.29226673183864 | 115.49181999921012 | 115.57698883919096 | 98.63119596059542 | small/inconsistent screen high |
| BF16 direct GPU3 | `data/gemma4-q8-gpu3-selecteddown-bf16direct-strict128-20260629T050957Z/summary.json` | 109.13641099750896 | 98.79229301256872 | 108.07363179458362 | 108.2384077325414 | 93.70919250853419 | loss |

The GPU2 strict128 lane was only a tiny screen high and the GPU3 lane lost, so
this was not promotable. It did justify a full512 confirmation.

## Full512 Confirmation

| Lane | Summary | Median 1-100 | p10 | Mean | Full512 after TTFT | Wall full512 | Validity | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| control GPU0 | `data/gemma4-q8-gpu0-selecteddown-bf16retest-control-full512-20260629T051323Z/summary.json` | 115.49839246092888 | 110.21117275046173 | 117.08572864303964 | 106.52690068109663 | 102.07109383151632 | valid | support |
| control GPU1 | `data/gemma4-q8-gpu1-selecteddown-bf16retest-control-full512-20260629T051323Z/summary.json` | **115.8466634928202** | 102.5726047181403 | 114.57370008916365 | 104.66140955057205 | 100.6396791169625 | valid | new tiny record repeat |
| BF16 direct GPU2 | `data/gemma4-q8-gpu2-selecteddown-bf16direct-full512-20260629T051323Z/summary.json` | 113.57688385554042 | 103.06069655293786 | 112.52503354790946 | 102.46801605527617 | 98.49347137032763 | invalid (`cached_tokens` contained one `null`) | reject |
| BF16 direct GPU3 | `data/gemma4-q8-gpu3-selecteddown-bf16direct-full512-20260629T051323Z/summary.json` | 109.10858524345157 | 98.19189207448389 | 110.68627396416217 | 104.2606201660195 | 99.46004778998716 | valid | loss |

## Decision

Do **not** promote BF16 direct. It did not beat paired controls at full512 and
one BF16 lane failed the strict fresh-response validity gate.

The control repeat on GPU1 is the same promoted VDR2 selected-down recipe and
validly nudged the headline from `115.72789384447941` to
`115.8466634928202` median tok/s. That repeat was submitted to LocalMaxxing as
`cmqyrpox4021dqk01co5o4fcw`.

Next useful work remains source-level verifier cost reduction, not more BF16
direct retests without a materially different kernel.
