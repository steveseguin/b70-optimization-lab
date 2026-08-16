# Qwen3.8 27B target-only optimization pass 2

## Outcome

The first post-bring-up pass promoted a TP2 adaptation of upstream's Q4_K
dense gate/up/SwiGLU fusion. On the fixed cold endpoint suite it improves the
conventional 99-interval median from `48.885968` to **`49.717503 tok/s`**
(`+1.7010%`) without speculation. All 12 complete outputs are byte-for-byte
identical to the prior target-only oracle and every request reports zero cached
prompt tokens.

This is a Q4_K_M target-only result. It does not use MTP, DFlash, an auxiliary
draft model, prompt reuse, context checkpoints, response reuse, or history
acceleration.

## Correct TP2 benchmark grammar

`llama-bench` uses slash-separated values for one tensor-parallel case:

```text
-dev SYCL0/SYCL1 -sm tensor -ts 1/1
```

Comma-separated `-dev SYCL0,SYCL1 -ts 1,1` creates separate benchmark cases.
Early pass-2 rows near 25 tok/s used that wrong grammar and are discarded
single-card diagnostics, not TP2 regressions. The server CLI continues to use
commas (`--device SYCL0,SYCL1 --tensor-split 1,1`).

## Matthew Dodd's August 15 settings

The newly suggested settings were tested on the correct TP2 route:

```text
GGML_SYCL_REORDER_IN_GEMM=1
GGML_SYCL_FORCE_REORDER=1
-b 8192 -ub 2048
```

They are valuable for prefill: at p64 they move prompt evaluation from
`325.288510` to `392.543995 tok/s` (`+20.68%`) on the promoted fusion build.
Decode moves from `50.271708` to `50.131180 tok/s` (`-0.28%`), so the default
decode repro retains `-b 1024 -ub 256` and exposes the larger settings only as
an optional prefill-heavy mode. A separate matched test before the new fusion
showed the same pattern: prompt `320.138247` to `393.658082`, decode
`49.399679` to `49.498725` (`+0.20%`, noise-class).

## Upstream transfer

Upstream llama.cpp commit
[`650913862`](https://github.com/ggml-org/llama.cpp/commit/65091386227039bfb81ee3426537656e3b4a3f83)
([PR #26779](https://github.com/ggml-org/llama.cpp/pull/26779)) fuses
`mul_mat(gate) + mul_mat(up) + GLU` for dense Q4_K decode. The public patch
reports 2.0–3.4% B70 batch-1 decode gains and larger gains under concurrency,
but correctly declines split buffers in the unsliced graph.

The lab meta backend already slices the graph by device. The new default-off
path therefore admits only a device-local, contiguous, one-row Q4_K gate/up
pair with the exact SwiGLU consumer. It:

1. installs the existing reordered Q4_K layout for both matrices;
2. reuses the accepted Q8_1 activation-quantization lookup;
3. walks both matrices with the incumbent SG16 DP4A block and reduction order;
4. writes `silu(gate) * up` directly to the device-local output;
5. skips the two materialized mat-vec outputs and standalone SwiGLU launch.

The specialized path refuses the phase-rotated research arm and falls back on
any shape, stride, graph-liveness, type, or buffer mismatch. Source and restore
instructions are preserved in
[`patches/qwen38-27b-q4km-tp2-asrock-b70/`](../../../patches/qwen38-27b-q4km-tp2-asrock-b70/README.md).

## Evidence

Same-binary `llama-bench`, p64/n256/r5, equal TP2:

| Arm | Prompt tok/s | Decode tok/s | Decode stdev | Fusion hits |
| --- | ---: | ---: | ---: | ---: |
| Door off | `330.594252` | `49.460273` | `0.086967` | 0 |
| Door on | `325.288510` | **`50.271708`** | `0.148347` | 163,968 |

The decode gain is `+1.6406%`, and the ranges are cleanly separated.

Fixed 12-prompt endpoint gate:

| Metric | Prior | Fused candidate | Change |
| --- | ---: | ---: | ---: |
| Conventional median, events 1–100 / 99 intervals | `48.885968` | **`49.717503`** | `+1.7010%` |
| Historical helper median | `49.379765` | `50.219700` | `+1.7010%` |
| Full output after TTFT | `49.082534` | `49.734644` | `+1.3286%` |
| Full wall throughput | `48.277657` | `48.802352` | `+1.0868%` |
| TTFT median | `169.750 ms` | `173.574 ms` | `+2.25%` latency |

The full run recorded `754,176` fused Q4_K gate/up/SwiGLU hits across both
devices, `VERIFY_MISMATCH=0`, no Xe fault/reset/hang, 12/12 exact output
hashes, and 12/12 `cached_tokens=0`. Raw evidence SHA-256:
`a3b1c58a76c7eae6027811ee61b6289ba295db15faafc1650668ae6ccb7992e8`.

## Next decode targets

- avoid re-materializing or re-quantizing the fused SwiGLU output before the
  down projection, while preserving the accepted F32 boundary;
- measure a shape-scoped subgroup-count variant inside this fused kernel
  instead of globally changing all MMVQ geometry;
- test concurrency with `llama-batched-bench`, where the upstream fusion and
  `ne[1]` routing have more headroom, but keep it separate from the one-active-
  generation LocalMaxxing metric;
- continue mining Intel's BMG ESIMD multi-GEMV and residual/RMS/GEMV fusion
  patterns as scheduling references rather than format-compatible drop-ins.

## LocalMaxxing status

The policy-compliant submission queue is preserved at
[`localmaxxing/qwen38-27b-q4km-tp2-target-only-49.718tok-20260815.queue.json`](../localmaxxing/qwen38-27b-q4km-tp2-target-only-49.718tok-20260815.queue.json).
Local preflight passes with the Qwen3.8 model identity and the conventional
`49.717503 tok/s` score. The authenticated server dry-run was not executed
because neither `LMX_API_KEY` nor the documented external credential file was
present on this host. Do not submit it under a Qwen3.6 identity; restore the
credential and require the server dry-run to accept `ggml-org/Qwen3.8-27B-GGUF`
before the real POST.
