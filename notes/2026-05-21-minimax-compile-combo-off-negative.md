# MiniMax M2.7 Compile Combo-Kernel-Off Negative

Date: 2026-05-21

## Outcome

I tested a compiler-only candidate that disabled Inductor combo kernels while keeping the promoted MiniMax TP4 llm-scaler path unchanged:

```json
{
  "use_inductor_graph_partition": true,
  "compile_sizes": [1],
  "cudagraph_mode": "PIECEWISE",
  "inductor_compile_config": {
    "combo_kernels": false,
    "benchmark_combo_kernel": false
  }
}
```

It passed the strict quality gates, but throughput regressed:

- repeat output tok/s: `87.257`, `86.590`
- mean output tok/s: `86.924`
- mean total tok/s: `115.898`
- restored control: `89.696` output tok/s
- delta vs restored control: `-3.09%`

## Quality

All strict quality checks passed:

- raw145 n64 exact hash: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256 exact hash: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- semantic-suite n64/r2 hash: `adacbf144264486ea7d378ebb6a4c0ba23951b72c4cf86251a762b07ebef5805`
- arithmetic-repeat n64/r8 hash: `261779104d5abf1642713bfc560ca8d2d6c0f16edbcc929c8b0819b5a760dd7c`
- extended-sixpack n64/r2 hash: `1e3560554f57b2b56cec8f49f28bc8ba12e9e0ced26bdc99a976f1433c99caa7`

## Interpretation

This candidate is quality-safe but should not be promoted. Disabling combo kernels did not fix a visible stability issue in this run and cost about three percent decode throughput versus the restored promoted path.

Keep the promoted compilation config with default combo-kernel behavior.

LocalMaxxing accepted this negative datapoint as `cmpfml9ti002dqj01utjig7xk`.

## Artifacts

- Summary: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/minimax-compile-combo-off-strict-tp4-ctx2048-mbt512-bs256-20260521T144449Z-summary.json`
- Benchmark JSON 1: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/vllm-minimax-m27-autoround-tp4-p512n1536-20260521T150034Z.json`
- Benchmark JSON 2: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/vllm-minimax-m27-autoround-tp4-p512n1536-20260521T150325Z.json`
- LocalMaxxing payload: `data/localmaxxing-minimax-m27-autoround-compile-combo-off-negative-p512n1536-20260521.payload.json`
- LocalMaxxing response: `data/localmaxxing-responses/minimax-m27-autoround-compile-combo-off-negative-p512n1536-20260521.response.json`
