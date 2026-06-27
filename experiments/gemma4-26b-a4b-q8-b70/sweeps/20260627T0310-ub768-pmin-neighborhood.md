# 2026-06-27 - UBATCH=768 p-min neighborhood screens

Goal: test whether the `UBATCH_SIZE=768` micro-record lane improves with a
lower `--spec-draft-p-min` than the current validated `0.136` recipe.

Validation policy reminder: these are repeated-prompt benchmark harnesses, so
only row 0 is a fresh-response headline. Later benchmark rows are support-only.
Screens with 64 canary rows are not publishable records; a candidate must pass a
full validation run before LocalMaxxing submission.

## Baseline

Current validated one-B70 Gemma 4 26B A4B Q8 record:

- run: `data/gemma4-q8-gpu3-b1024u768-fullrepeat-20260626T235649Z/summary.json`
- row0 fresh throughput: `104.07050714456982 tok/s`
- support repeated mean: `103.588578767931 tok/s`
- canary: `6144/6144` rows pass
- shape: `BATCH_SIZE=1024`, `UBATCH_SIZE=768`, `MTP_N_MIN=2`,
  `MTP_P_MIN=0.136`
- LocalMaxxing: `cmqvmjvzx02qvqr01qh9jikow`

## First neighborhood screen (`20260627T031002Z`)

All runs used:

- `BENCH_PROMPT_MODE=filled-long`, `PROMPT_TOKENS=512`, `MAX_TOKENS=512`
- `CANARY_REPEATS=16` -> 64 canary rows
- `BENCH_REPEATS=1`
- `BATCH_SIZE=1024`, `UBATCH_SIZE=768`, `THREADS=8`, `POLL=100`
- `MTP_N_MAX=7`, `MTP_BACKEND_SAMPLING=0`,
  `MTP_DRAFT_THREADS=32`, `MTP_DRAFT_THREADS_BATCH=32`,
  `MTP_EXTRA_ARGS='--ctx-checkpoints 0'`
- record-stack env:
  `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`,
  `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1`,
  `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7`,
  `LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1`,
  `LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1`,
  `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`,
  `LLAMA_MTP_DEFER_TARGET_H_NEXTN=1`,
  `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`,
  `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1`,
  `LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`,
  `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`

| GPU | Run | Knob | Canary | Fresh row0 tok/s | Verdict |
| --- | --- | --- | --- | ---: | --- |
| 0 | `data/gemma4-q8-gpu0-ub768-pmin010-screen-20260627T031002Z/summary.json` | `n_min=2`, `p_min=0.10` | 64/64 | `104.90764207185568` | Above current record as a screen only; promoted to full validation. |
| 1 | `data/gemma4-q8-gpu1-ub768-pmin012-screen-20260627T031002Z/summary.json` | `n_min=2`, `p_min=0.12` | 64/64 | `103.7344189219287` | Loss. |
| 2 | `data/gemma4-q8-gpu2-ub768-pmin015-screen-20260627T031002Z/summary.json` | `n_min=2`, `p_min=0.15` | 64/64 | `102.18590163178644` | Loss. |
| 3 | `data/gemma4-q8-gpu3-ub768-nmin3-pmin0136-screen-20260627T031002Z/summary.json` | `n_min=3`, `p_min=0.136` | 64/64 | `104.17822408660554` | Slight screen above current, but far below the `p_min=0.10` screen. |

## Second neighborhood screen (`20260627T031448Z`)

The lower-threshold follow-up did not reproduce the `p_min=0.10` screen spike:

| GPU | Run | Knob | Canary | Fresh row0 tok/s | Verdict |
| --- | --- | --- | --- | ---: | --- |
| 1 | `data/gemma4-q8-gpu1-ub768-pmin008-screen-20260627T031448Z/summary.json` | `n_min=2`, `p_min=0.08` | 64/64 | `103.65548455829654` | Loss. |
| 2 | `data/gemma4-q8-gpu2-ub768-pmin009-screen-20260627T031448Z/summary.json` | `n_min=2`, `p_min=0.09` | 64/64 | `104.05676217362864` | Roughly tied with current, not a record. |
| 3 | `data/gemma4-q8-gpu3-ub768-pmin0105-screen-20260627T031448Z/summary.json` | `n_min=2`, `p_min=0.105` | 64/64 | `104.00613345729681` | Roughly tied/loss. |

## Interpretation

The `p_min=0.10` screen is the only above-record candidate, but it is likely in
the same variance class as the earlier `UBATCH_SIZE=832` screen spike:

- `data/gemma4-q8-gpu2-ubatch832-screen-20260627T003714Z/summary.json`:
  screen row0 `105.00621024594338 tok/s`, 256 canary rows pass.
- `data/gemma4-q8-gpu2-b1024u832-fullrepeat-20260627T003946Z/summary.json`:
  full validation row0 `103.90548697450369 tok/s`, 6144 canary rows pass.

Therefore, do not submit the `p_min=0.10` screen result. The promoted
validation run is:

- `data/gemma4-q8-gpu0-ub768-pmin010-fullrepeat-20260627T031448Z/summary.json`.

If the full validation does not beat `104.07050714456982 tok/s`, keep the
current LocalMaxxing record and treat the `p_min=0.10` result as a screen-only
variance spike.

## Shape-combination follow-up (`20260627T032140Z`)

While the full validation was running on GPU0, three idle-GPU screens tested
whether the `p_min=0.10` threshold combines with adjacent shape knobs:

| GPU | Run | Knob | Canary | Fresh row0 tok/s | Verdict |
| --- | --- | --- | --- | ---: | --- |
| 1 | `data/gemma4-q8-gpu1-u832-pmin010-screen-20260627T032140Z/summary.json` | `UBATCH=832`, `n_min=2`, `p_min=0.10` | 64/64 | `103.68848416131569` | Loss. |
| 2 | `data/gemma4-q8-gpu2-u704-pmin010-screen-20260627T032140Z/summary.json` | `UBATCH=704`, `n_min=2`, `p_min=0.10` | 64/64 | `103.89731271407179` | Loss. |
| 3 | `data/gemma4-q8-gpu3-u768-nmin3-pmin010-screen-20260627T032140Z/summary.json` | `UBATCH=768`, `n_min=3`, `p_min=0.10` | 64/64 | `104.12813019085074` | Tiny screen edge over current, but below the promoted `p_min=0.10` candidate and not worth validating first. |

This follow-up reinforces that the only candidate worth spending full canary
depth on is still GPU0 `UBATCH=768`, `n_min=2`, `p_min=0.10`.

## Full validation result for `p_min=0.10`

`data/gemma4-q8-gpu0-ub768-pmin010-fullrepeat-20260627T031448Z/summary.json`
invalidated the screen spike:

- canary: `1536` repeats / `6144` rows, pass;
- benchmark rows: 8 rows, all `cached_tokens=0`;
- fresh row0 after TTFT: `104.00197765543678 tok/s`;
- support mean after TTFT: `103.13646894407574 tok/s`;
- wall row0: `90.5796928059348 tok/s`;
- current record to beat: `104.07050714456982 tok/s`.

Decision: valid loss. Do not submit. Keep current LocalMaxxing record
`cmqvmjvzx02qvqr01qh9jikow`. The `104.90764207185568 tok/s` screen was a
variance spike, matching the pattern seen with the prior `UBATCH_SIZE=832`
screen.
