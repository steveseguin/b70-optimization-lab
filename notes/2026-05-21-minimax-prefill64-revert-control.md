# MiniMax M2.7 Prefill64 Revert Control

Date: 2026-05-21

## Outcome

The opt-in N-major prefill64 MoE experiment was quality-clean but slower, so I reverted the active local vLLM runtime/source back to the promoted decode-only gate:

```python
x.shape[0] <= 4
```

After the revert, the promoted path reproduced cleanly at `89.696` output tok/s and `119.595` total tok/s on p512/n1536.

## Quality

All strict gates passed before accepting the throughput result:

- raw145 n64 exact hash: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256 exact hash: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- semantic-suite n64/r2
- arithmetic-repeat n64/r8
- extended-sixpack n64/r2

## Interpretation

This confirms the `VLLM_XPU_LLM_SCALER_MOE_APPLY_MAX_TOKENS=64` candidate was a real regression, not system drift:

- prefill64 candidate: `86.114` output tok/s
- reverted promoted control: `89.696` output tok/s
- original promoted LocalMaxxing result: `89.314` output tok/s

The prefill64 patch remains documented as a negative experiment and should not be applied for the promoted path.

LocalMaxxing accepted this restored-control datapoint as `cmpfllzei001mqj01kk94cgiu`.

## Artifacts

- Summary: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/minimax-promoted-control-reverted-prefill64-strict-tp4-ctx2048-mbt512-bs256-20260521T141540Z-summary.json`
- Benchmark JSON: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/vllm-minimax-m27-autoround-tp4-p512n1536-20260521T143129Z.json`
- Benchmark log: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/vllm-minimax-m27-autoround-tp4-p512n1536-20260521T143129Z.log`
- LocalMaxxing payload: `data/localmaxxing-minimax-m27-autoround-prefill64-revert-control-p512n1536-20260521.payload.json`
- LocalMaxxing response: `data/localmaxxing-responses/minimax-m27-autoround-prefill64-revert-control-p512n1536-20260521.response.json`
