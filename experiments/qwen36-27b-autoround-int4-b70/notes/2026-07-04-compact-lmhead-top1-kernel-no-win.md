# Qwen27 compact INT8 LM-head top-1 kernel: exact but no win

Date: 2026-07-04

## Summary

Built and tested a native XPU prototype for the next Phase 2 idea: compute
top-1 token IDs/scores directly from the runtime INT8 LM-head without
materializing dense `[rows, vocab]` logits.

The prototype is buildable and token-exact against the current dense
`int8_gemm_w8a8(...)->argmax` baseline on synthetic Qwen27 LM-head shapes, but
it is **slower** than the oneDNN dense path at the real `5120 x 248320` vocab
shape. Do not wire this op into vLLM and do not spend endpoint validation on it.

No LocalMaxxing submission: diagnostic microbench only, no strict endpoint win.

## Patch / Harness

Source patch snapshot:

- `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-lmhead-compact-top1-n64-no-win-20260704.patch`

Harness:

- `scripts/bench-int8-lm-head-top1.py`

Local build target:

```bash
cd /home/steve/src/vllm-xpu-kernels
cmake --build build/xpu-c-only-2025 --target _xpu_C -j 8
cp build/xpu-c-only-2025/_xpu_C.abi3.so vllm_xpu_kernels/_xpu_C.abi3.so
```

The patch adds `torch.ops._xpu_C.int8_lm_head_top1_w8a8(...)`, returning
`(top_ids:int64, top_vals:float32)`.

## Results

Baseline compared:

- quantize hidden with `per_token_quant_int8_xpu`;
- dense oneDNN `int8_gemm_w8a8` to BF16 logits;
- `argmax(logits[:, :valid_vocab])`.

Candidate compared:

- same quantize hidden;
- compact tiled top-1 op, no dense logits output.

Real Qwen27 shape:

- hidden: `5120`;
- vocab: `248320`;
- valid vocab: `248320`;
- output dtype: BF16;
- LM-head scale dtype: BF16;
- rows: `1,2,3,4`;
- one GPU, diagnostic synthetic tensors.

Final 8x64-policy result:

- rows 1: dense `2.6036 ms`, compact `2.6759 ms`, speedup `0.973x`, exact;
- rows 2: dense `2.6058 ms`, compact `2.6689 ms`, speedup `0.976x`, exact;
- rows 3: dense `2.5738 ms`, compact `2.6655 ms`, speedup `0.966x`, exact;
- rows 4: dense `2.5764 ms`, compact `2.6606 ms`, speedup `0.968x`, exact.

Evidence:

- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-lmhead-top1-compact-n64-bf16scale-microbench-20260704.json`

Intermediate results:

- first one-row-per-tile prototype was exact but much worse for rows `2-4`
  because it reread the LM-head once per row:
  `qwen27-lmhead-top1-compact-bf16scale-microbench-20260704.json`;
- batched-row 8x32 prototype fixed row scaling but still lost:
  rows 1 `0.939x`, rows 4 `0.908x`;
  `qwen27-lmhead-top1-compact-batchedrows-bf16scale-microbench-20260704.json`.

## Interpretation

The intuition was right but not sufficient: avoiding the dense logits store does
remove output materialization, but the current oneDNN dense W8A8 path is already
very efficient for these small verifier row counts and reuses the LM-head weight
matrix well. The compact tiled op still pays:

- full vocab scan;
- scale multiply and BF16 rounding per candidate token;
- partial top-1 write/read;
- second reduction kernel launch;
- less mature scheduling than oneDNN.

This means the measured LM-head waste is real, but a standalone full-vocab
top-1 epilogue is not enough on this hardware/runtime.

## Closed Conclusion

Closed as **no-win**:

- do not integrate `int8_lm_head_top1_w8a8` into vLLM;
- do not run strict endpoint validation for it;
- do not retry small policy variants unless there is a new mechanism that
  removes an entire launch/reduction or uses a oneDNN-native fused reduction.

Next credible lanes:

1. Reduce the number of LM-head calls/rows per verifier step. Timing showed
   about `2258` LM-head/logits calls over `540` verifier steps (`~4.18`
   calls/step). A call-count reduction can save whole `~2.5 ms` GEMMs, which is
   larger than shaving a few percent from one call.
2. Improve accepted tokens per expensive verifier step while preserving exact
   target verification; this is the route to larger decode gains if quality
   holds.
3. Investigate a oneDNN-integrated top-k/top-1 post-op or a single-kernel
   dense-GEMM-plus-reduction path only if it can avoid the extra reduction
   launch and preserve exact BF16/INT8-LM-head semantics.

