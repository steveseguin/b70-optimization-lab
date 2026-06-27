# 2026-06-27T14:20Z Q8 MoE-ID Reorder Breakthrough

## Goal

Break the `>150 tok/s` fresh-response target for Gemma 4 26B A4B Q8 on one
Intel B70 without relying on repeated-continuation history or cache reuse.

Headline policy remains strict: use benchmark row 0 only, require
`cached_tokens=0`, and treat later repeated-prompt rows as support-only.

## Result So Far

The first successful screens use the existing Q8 target + Q4_0 MTP draft stack
plus a new default-off Q8_0 MoE expert reorder for the broad multi-token
`MUL_MAT_ID` verifier path.

| Run | Canary | Fresh row0 tok/s | Support mean tok/s | Status |
| --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu1-mulmatid-fast-q8reorder-ub768-screen-20260627T142028Z/` | 256/256 | 170.080 | 170.095 | Positive screen; full confirm pending |
| `data/gemma4-q8-gpu2-mulmatid-fast-control-ub768-screen-20260627T142028Z/` | 256/256 | 77.315 | 77.336 | Control loss without Q8 reorder |
| `data/gemma4-q8-gpu1-q8reorder-ub704-nmin3-pmin010-screen-20260627T142827Z/` | 256/256 | 171.140 | 170.180 | Best screen; full confirm pending |
| `data/gemma4-q8-gpu2-q8reorder-ub832-nmin3-pmin010-screen-20260627T142827Z/` | 256/256 | 169.134 | 168.148 | Valid screen, slower |
| `data/gemma4-q8-gpu3-q8reorder-ub768-nmin2-pmin010-screen-20260627T142827Z/` | 256/256 | 168.347 | 168.842 | Valid screen, slower |
| `data/gemma4-q8-gpu2-q8reorder-ub640-nmin3-pmin010-screen-20260627T143126Z/` | 256/256 | 168.856 | 169.086 | Valid screen, slower |
| `data/gemma4-q8-gpu3-q8reorder-ub736-nmin3-pmin010-screen-20260627T143126Z/` | 256/256 | 168.746 | 168.569 | Valid screen, slower |
| `data/gemma4-q8-gpu2-q8reorder-ub704-nmin3-pmin008-screen-20260627T143328Z/` | 256/256 | 167.470 | 168.298 | Valid screen, slower |
| `data/gemma4-q8-gpu3-q8reorder-ub704-nmin3-pmin012-screen-20260627T143328Z/` | 256/256 | 168.893 | 169.489 | Valid screen, slower |
| `data/gemma4-q8-gpu2-q8reorder-ub704-nmax8-nmin3-pmin010-screen-20260627T143608Z/` | 256/256 | 89.432 | 89.435 | Rejected; n_max=8 exceeds current path sweet spot |
| `data/gemma4-q8-gpu3-q8reorder-ub704-nmax6-nmin3-pmin010-screen-20260627T143608Z/` | 256/256 | 160.302 | 159.485 | Valid but slower |
| `data/gemma4-q8-gpu2-q8reorder-ub704-nmin4-pmin010-screen-20260627T144257Z/` | 256/256 | 168.700 | 168.403 | Valid screen, slower; `n_min=4` loses |
| `data/gemma4-q8-gpu3-q8reorder-ub704-nmin3-pmin011-screen-20260627T144257Z/` | 256/256 | 168.663 | 169.528 | Valid screen, slower; `p_min=0.11` loses |
| `data/gemma4-q8-gpu1-q8reorder-ub696-nmin3-pmin010-screen2-20260627T151031Z/` | 256/256 | 170.029 | 169.853 | Valid screen, below current record |
| `data/gemma4-q8-gpu3-q8reorder-ub712-nmin3-pmin010-screen2-20260627T151031Z/` | 256/256 | 168.903 | 168.392 | Valid screen, slower |
| `data/gemma4-q8-gpu1-q8reorder-ub704-nmin3-pmin0095-screen-20260627T151332Z/` | 256/256 | 170.409 | 170.634 | Valid screen, below current UB720 full |
| `data/gemma4-q8-gpu3-q8reorder-ub704-nmin3-pmin0105-screen-20260627T151332Z/` | 256/256 | 169.341 | 169.293 | Valid screen, slower |
| `data/gemma4-q8-gpu0-q8reorder-ub716-nmin3-pmin010-screen-20260627T151906Z/` | 256/256 | 169.741 | 169.960 | Valid screen, below current UB720 full |
| `data/gemma4-q8-gpu1-q8reorder-ub724-nmin3-pmin010-screen-20260627T151906Z/` | 256/256 | 168.938 | 168.169 | Valid screen, slower |
| `data/gemma4-q8-gpu2-q8reorder-ub720-nmin3-pmin0095-screen-20260627T151906Z/` | 256/256 | 168.113 | 168.153 | Valid screen, slower |
| `data/gemma4-q8-gpu3-q8reorder-ub720-nmin3-pmin0105-screen-20260627T151906Z/` | 256/256 | 167.785 | 168.056 | Valid screen, slower |

Identity mistake: the first UB696/UB712 screens at `20260627T150535Z`
accidentally omitted `EXTRA_LLAMA_ARGS` and inherited
`GGML_SYCL_DISABLE_OPT=1`, so they measured a no-MTP/opt-disabled lane at
~26 tok/s. They are invalid for UBATCH tuning and should not be interpreted as
real losses.

Full confirmations:

| Run | Canary | Fresh row0 tok/s | Support mean tok/s | LocalMaxxing | Status |
| --- | ---: | ---: | ---: | --- | --- |
| `data/gemma4-q8-gpu0-q8reorder-ub720-nmin3-pmin010-fullconfirm-20260627T144855Z/` | 6144/6144 | 171.108 | 170.129 | `cmqwi45d803gyqr01td3vf9ka` | Current promoted full pass |
| `data/gemma4-q8-gpu0-mulmatid-fast-q8reorder-ub768-fullconfirm-20260627T142318Z/` | 6144/6144 | 169.949 | 169.550 | `cmqwh8du403gfqr01d6ut1ddo` | Superseded full pass |
| `data/gemma4-q8-gpu1-q8reorder-ub704-nmin3-pmin010-fullconfirm-20260627T143126Z/` | 6144/6144 | 170.112 | 169.876 | `cmqwhkbzj03guqr01h00c8n04` | Superseded full pass |
| `data/gemma4-q8-gpu2-q8reorder-ub688-nmin3-pmin010-fullconfirm-20260627T144855Z/` | 6144/6144 | 168.757 | 168.700 | n/a | Valid full pass, slower |

Current frontier: `UBATCH_SIZE=720`, `n_min=3`, `p_min=0.10` is the promoted
record. Later candidates must complete `6144/6144` canary rows, benchmark row0
must report `cached_tokens=0`, and row0 must exceed
`171.1076295077342 tok/s` before promotion.

Two high-looking UB720/UB688 screens used `PROMPT_TOKENS=588` and produced an
actual prompt length of `663` tokens, so they are not directly comparable to
the submitted LocalMaxxing shape (`PROMPT_TOKENS=512`, actual `588` tokens).

## Patch Artifact

Focused patch snapshot:
`patches/gemma4-26b-a4b-q8-b70/q8-moe-id-reorder-positive-20260627.md`

The source worktree has many older Gemma patches, so the patch artifact records
the exact Q8 reorder locations instead of pretending the whole dirty diff is a
clean single patch.

## Interpretation

The earlier conclusion that broad `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1`
was dead is now refined: it is dead **without** Q8_0 reorder, but becomes the
best fresh-response lane once Q8_0 MoE expert slices are reordered into the
layout expected by the multi-token reorder body.

This is the first non-history Gemma 26B Q8 lane to exceed `150 tok/s` in
fresh-response full confirmation. It replaces the `104.309 tok/s` LocalMaxxing
record and is the active baseline for further Gemma 26B Q8 work.
