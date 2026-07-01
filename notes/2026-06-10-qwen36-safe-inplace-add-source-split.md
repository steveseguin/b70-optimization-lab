# Qwen3.6 Safe In-Place All-Reduce Add Source Split

Date: 2026-06-10

## Goal

Split the earlier rejected `add`-only safe in-place all-reduce rewrite by
individual add producer. The combined add-only filter improved single-request
speed but failed the arithmetic canary, so this pass tested whether either
logged producer was both quality-safe and useful for single-request speed.

The model/runtime stayed fixed:

- Qwen3.6 35B-A3B Quark W8A8 INT8 checkpoint
- TP4, 32K context, BF16 runtime
- no prefix caching
- PIECEWISE XPU graph
- `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone`
- `max_num_batched_tokens=8192`
- `max_num_seqs=48`

The only candidate delta was:

- `VLLM_XPU_EXPERIMENTAL_SAFE_INPLACE_ALLREDUCE=1`
- `VLLM_XPU_SAFE_INPLACE_ALLREDUCE_SOURCE_FILTER=source_name:add_92` or
  `source_name:add_53`

## Baseline

Current stable GDN clone/no-prefix reference:

- speed artifact:
  `data/qwen36-quark-int8-tp4-noprefix-gdn-reuseqkvzbaquant-clone-envclean-single-r8-20260610.json`
- quality artifact:
  `data/qwen36-quark-int8-tp4-noprefix-gdn-reuseqkvzbaquant-clone-envclean-frontdoor-quality-rerun32-20260610.json`
- corrected after-first output speed: `99.3181 tok/s`
- e2e output speed: `97.9820 tok/s`
- total speed: `197.0858 tok/s`
- mean TTFT: `79.45 ms`

## `source_name:add_92`

Runtime:

- session: `qwen36-tp4-safeinplace-add92-32k`
- cache root:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-safeinplace-add92-gdnclone-32k-noprefix-20260610b`
- log:
  `/tmp/qwen36-quark-int8-tp4-safeinplace-add92-gdnclone-32k-noprefix-20260610b.log`

Startup reached health with normal graph settings after one invalid launch was
discarded. The invalid launch had sourced the slot config without exporting its
variables, so XPU graph was disabled and no benchmark from that attempt was
used.

Rewrite census:

- skipped `where.self`
- skipped `int8_gemm_w8a8`
- rewrote `add_92`
- skipped `add_53`

Speed artifact:

- `data/qwen36-quark-int8-tp4-noprefix-safeinplace-add92-gdnclone-single-r8-20260610.json`

Result:

| metric | baseline | add_92 |
| --- | ---: | ---: |
| corrected after-first output tok/s | `99.3181` | `99.2822` |
| e2e output tok/s | `97.9820` | `98.0144` |
| total tok/s | `197.0858` | `196.0288` |
| mean client TTFT | `79.45 ms` | `76.78 ms` |

Decision: reject at the speed gate. It is effectively tied on decode, below the
baseline corrected after-first mean, and lower on total tok/s. No quality suite
was run because there is no speed win to validate.

## `source_name:add_53`

Runtime:

- session: `qwen36-tp4-safeinplace-add53-32k`
- cache root:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-safeinplace-add53-gdnclone-32k-noprefix-20260610`
- log:
  `/tmp/qwen36-quark-int8-tp4-safeinplace-add53-gdnclone-32k-noprefix-20260610.log`

Rewrite census:

- skipped `where.self`
- skipped `int8_gemm_w8a8`
- skipped `add_92`
- rewrote `add_53`

Speed artifact:

- `data/qwen36-quark-int8-tp4-noprefix-safeinplace-add53-gdnclone-single-r8-20260610.json`

Result:

| metric | baseline | add_53 |
| --- | ---: | ---: |
| corrected after-first output tok/s | `99.3181` | `99.3721` |
| e2e output tok/s | `97.9820` | `98.1038` |
| total tok/s | `197.0858` | `196.2076` |
| mean client TTFT | `79.45 ms` | `76.68 ms` |

The decode movement was only `+0.054 tok/s` corrected after first chunk and is
too small to promote without a clean quality result.

Quality artifact:

- `data/qwen36-quark-int8-tp4-noprefix-safeinplace-add53-gdnclone-frontdoor-quality-rerun32-20260610.json`

Quality result:

- exact canaries: pass
- arithmetic canary: pass
- JSON canary: pass
- long-context recall: pass
- baseline parity checks: pass
- repeat stability: fail

Repeat outlier:

```text
ntag.ntag.ntag.ntag.ntag.ntag.ntag.ntag.ntag.ntag. whiskey whiskey whiskey whiskey * * * *
```

Decision: reject. This isolates that `add_53` is not the arithmetic-canary
culprit from the earlier add-only run, but it is still not quality-safe under
the repeat-stability gate.

## Restore

The accepted GDN clone/no-prefix backend was restored after the screen:

- session: `qwen36-tp4-gdn-reusequant-clone-envclean-32k`
- backend health: passed on `127.0.0.1:18080`
- frontdoor model listing: passed on `127.0.0.1:8000/v1/models`
- restore telemetry:
  - model load memory: `8.58 GiB`
  - model loading: `14.139226 s`
  - cached torch.compile: `3.79 s`
  - available KV cache memory: `20.67 GiB`
  - max 32K concurrency estimate: `62.65x`
  - graph capture: `11 s`

## Decision

Do not promote either add-source split.

- `add_92`: speed-neutral / no useful decode gain.
- `add_53`: tiny decode gain, but repeat-stability quality failure.

The safe in-place all-reduce branch remains useful as a diagnostic of collective
boundaries, but these source-name filters do not provide a production-safe
single-request improvement.
