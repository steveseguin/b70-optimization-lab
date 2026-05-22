# 2026-05-22 MiniMax JSON Quality Follow-Ups

This addendum extends `2026-05-22-minimax-json-quality-context-concurrency.md`
with batch-1 graph policy, c2 isolation, and prefill chunk follow-ups.

## Harness Change

Added `--compile-size-policy {one,one-and-concurrency,none}` to
`scripts/run-minimax-json-quality-throughput.py`.

- `one-and-concurrency` preserves the original behavior.
- `one` uses `compile_sizes=[1]`, matching the website harness and letting c2
  experiments keep the proven batch-1 graph path.
- `none` uses `compile_sizes=[]` for diagnostic screens.

Patch delta: `patches/minimax-json-quality-compile-size-policy-20260522.diff`.

## Valid Results

No-padding c1 control:

- Run: `/home/steve/bench-results/minimax-m2.7-json-quality/20260522T122143Z-ctx4096-c1-mbt512-compile1-retry3-repeat2/result.json`
- Delivered: 6/6 valid JSON outputs.
- Raw candidates: 6/7 valid (`85.71%`).
- Selected valid decode: `87.176 tok/s`.
- Effective accepted-output including retries: `82.222 tok/s`.

2k-context c1 control:

- Run: `/home/steve/bench-results/minimax-m2.7-json-quality/20260522T124101Z-ctxpad2048-c1-mbt512-compile1-retry3-repeat2/result.json`
- LocalMaxxing: `cmpgx0yrb009fpc0183xjri4j`.
- Delivered: 6/6 valid JSON outputs.
- Raw candidates: 6/9 valid (`66.67%`).
- Selected valid decode: `83.151 tok/s`.
- Effective accepted-output including retries: `54.898 tok/s`.
- Selected prompt+output accounting: `2567.477 tok/s`.
- Conservative submitted `tokSTotal`: `1695.105`, using selected
  prompt+accepted output over all-attempt elapsed.

## Negative Results

`c2_graph_compile_size_one_stall`:

- Run: `/home/steve/bench-results/minimax-m2.7-json-quality/20260522T122443Z-ctx4096-c2-mbt512-compile1-retry3-repeat2/run.log`
- Runtime: graph mode, `compile_sizes=[1]`, c2, `gpu_memory_utilization=0.95`.
- KV cache reported 34,560 tokens and 8.44x theoretical 4k concurrency.
- Graph capture failed launching
  `triton_red_fused__to_copy_add_int4_gemm_w4a16_mean_mul_pow_rsqrt_7`,
  then stalled in shared-memory broadcast.

`c2_no_graph_indexing_assert`:

- Run: `/home/steve/bench-results/minimax-m2.7-json-quality/20260522T123325Z-ctx4096-c2-mbt512-nograph-noenv-retry3-repeat1/run.log`
- Runtime: `cudagraph_mode=NONE`, graph comm env switches off, c2,
  `gpu_memory_utilization=0.95`.
- Model loaded and graph capture was skipped.
- Generation died with Torch XPU `Indexing.h:622` index-out-of-bounds
  assertions and `VllmWorker-0` shutdown.

`c1_2k_context_mbt1024_ocloc_ice`:

- Run: `/home/steve/bench-results/minimax-m2.7-json-quality/20260522T123623Z-ctxpad2048-c1-mbt1024-compile1-retry3-repeat2/run.log`
- Runtime: graph mode, c1, ~2k context pad, `max_num_batched_tokens=1024`.
- Intel `ocloc` returned error 245 with `IGC: Internal Compiler Error:
  Floating point exception` while compiling Triton reduction kernels.
- The run then stalled in shared-memory broadcast.

## Current Recommendation

For reliable quality-gated c1 MiniMax AutoRound testing, keep graph mode,
`compile_sizes=[1]`, and `max_num_batched_tokens=512`. Do not promote c2 or
1024-token prefill chunk results until the XPU indexing and `ocloc` failures are
fixed.
