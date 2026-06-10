# Qwen3.6 GDN Partial Clone Rejected

Date: 2026-06-10

## Goal

The accepted GDN qkvz/ba quant-reuse mode uses:

- one shared `per_token_quant_int8_xpu(hidden_states)` result, then
- cloned quantized activation and cloned scale tensors for each of the two
  following `int8_gemm_w8a8` consumers.

The unguarded reuse mode was faster but failed repeat stability. This screen
tested whether cloning only one side of the shared quant pair could preserve
quality safety with less clone overhead:

- `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone-q`
- `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone-scale`

Patch artifact:

- `patches/vllm-qwen36-gdn-reuse-partial-clone-rejected-20260610.patch`

## Control

Fresh accepted backend control immediately before the screen:

- artifact:
  `data/qwen36-quark-int8-tp4-noprefix-current-control-continue-20260610.json`
- corrected after-first output speed: `99.6301 tok/s`
- e2e output speed: `98.3908 tok/s`
- total client throughput: `196.7815 tok/s`
- mean client TTFT: `74.77 ms`

## Results

Both candidates used the same Qwen3.6 Quark W8A8 INT8 TP4 32K no-prefix
runtime, clone-safe custom-op all-reduce, and fresh graph caches.

| mode | artifact | corrected after-first tok/s | e2e tok/s | total tok/s | TTFT |
| --- | --- | ---: | ---: | ---: | ---: |
| accepted control | `data/qwen36-quark-int8-tp4-noprefix-current-control-continue-20260610.json` | `99.6301` | `98.3908` | `196.7815` | `74.77 ms` |
| `clone-q` | `data/qwen36-quark-int8-tp4-noprefix-gdn-reuseqkvzbaquant-cloneq-single-r8-20260610.json` | `98.9995` | `97.7415` | `195.4830` | `76.66 ms` |
| `clone-scale` | `data/qwen36-quark-int8-tp4-noprefix-gdn-reuseqkvzbaquant-clonescale-single-r8-20260610.json` | `99.2045` | `97.9641` | `195.9282` | `75.43 ms` |

## Decision

Reject both partial-clone modes. They failed the speed gate against the same-day
control, so no long frontdoor quality suite was run.

Keep the existing accepted `clone` mode for GDN qkvz/ba quant reuse. The local
source was restored to the accepted clone-only behavior after this screen.
