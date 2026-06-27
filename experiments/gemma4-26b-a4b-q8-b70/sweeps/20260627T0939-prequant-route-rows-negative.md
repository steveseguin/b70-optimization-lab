# Gemma4 26B Q8 Prequant Route-Rows Experiment (2026-06-27 09:39 UTC)

## Context

The current valid one-B70 fresh-response record is:

- run: `data/gemma4-q8-gpu0-rmsreuse-ub768-nmin3-pmin010-fullrepeat-20260627T070421Z/`
- headline row0 throughput after TTFT: `104.30919255569083 tok/s`
- wall row0 throughput: `90.85119259916031 tok/s`
- canary: `6144/6144`
- LocalMaxxing id: `cmqw1tgzx0366qr01g4lkv7f1`

Route timing showed the routed expert `q8_0 x f32 -> q8_1` work dominating the
multi-token MoE path. The idea was to gather all routed rows once, prequantize
the gathered `src1` rows to `q8_1` once, and call the direct MMVQ kernel for
eligible expert slices instead of re-entering the generic `ggml_sycl_mul_mat()`
path for each expert.

Common validation policy: repeated benchmark prompts make row0 the only
fresh-response headline. Later rows are support-only even with
`cached_tokens=0`.

## Patch Sketch

The attempted source change was in
`/home/steve/src/llama.cpp-gemma-record-stack/ggml/src/ggml-sycl/ggml-sycl.cpp`.
It was gated by:

```cpp
LLAMA_SYCL_MUL_MAT_ID_PREQUANT_ROUTE_ROWS=1
```

The unsafe first version called `ggml_sycl_op_mul_mat_vec_q()` directly for all
per-expert row counts after one contiguous q8_1 quantization pass.

Plato's independent audit found the correctness break:

- direct MMVQ supports at most `MMVQ_MAX_BATCH_SIZE == 8` source rows;
- for `num_src1_rows > 8`, direct Q8_0 MMVQ only launches the first column and
  leaves later output stale;
- do not force `reorder=false`; disable this path if
  `src0->extra->optimized_feature.reorder` is active;
- require compact Q8_0 expert rows
  (`src0->nb[1] == (ne10 / QK8_0) * sizeof(block_q8_0)`).

The guarded version therefore only enabled direct MMVQ when all hard preconditions
were true and only for expert slices with `num_src1_rows <= MMVQ_MAX_BATCH_SIZE`.
Slices above that fell back to `ggml_sycl_mul_mat()`.

## Results

| Run | Variant | Canary | Fresh row0 tok/s | Decision |
| --- | --- | ---: | ---: | --- |
| `data/gemma4-q8-gpu1-prequant-route-rows-rmsreuse-ub768-screen-20260627T091428Z/` | unsafe direct MMVQ | failed at first JSON row | n/a | Invalid. |
| `data/gemma4-q8-gpu1-prequant-route-rows-rmsreuse-ub768-screen2-20260627T092538Z/` | unsafe direct MMVQ rerun | failed at first JSON row | n/a | Invalid. |
| `data/gemma4-q8-gpu1-prequant-route-rows-guarded-rmsreuse-ub768-screen-20260627T093939Z/` | guarded direct MMVQ | `64/64` | `104.0281678873085` | Correct but slower than record. |

Both unsafe runs emitted the same first-row JSON canary failure:

```text
<channel|>Please provide the text, image, or question you would like me to process. I am ready to assist, but I need your input to begin
```

The guarded run used the current record runtime identity plus
`LLAMA_SYCL_MUL_MAT_ID_PREQUANT_ROUTE_ROWS=1` and produced:

- canary: `64/64`;
- fresh row0 after TTFT: `104.0281678873085 tok/s`;
- wall row0: `90.42430844989461 tok/s`;
- support mean: `104.09914337892796 tok/s`.

## Decision

Reject this active source patch for now. It is not a fresh-response improvement
over `104.30919255569083 tok/s`, and the guarded fast path appears to add enough
overhead or hit too few eligible slices to pay for itself.

The patch was preserved here as a negative experiment, then removed from the
active source stack. Future route-row work should not call direct MMVQ for
`num_src1_rows > MMVQ_MAX_BATCH_SIZE`, and should first quantify how many expert
slices are actually `<= 8` rows before adding more prequantization machinery.

## Follow-Up Ideas

- Add cheap counters for `expert_row_counts <= 8` vs `> 8` under the current
  record prompt before revisiting this lane.
- If most slices are above 8, optimize the generic Q8 expert matmul path instead
  of trying to force MMVQ.
- If many slices are `<= 8`, investigate a single fused route+quant+MMVQ kernel
  to remove the extra standalone prequantization pass.
