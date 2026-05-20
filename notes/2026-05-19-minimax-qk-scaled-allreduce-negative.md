# MiniMax M2.7 Q/K Scaled Allreduce Custom-Op Negative

Date: 2026-05-19

## Summary

Tested `VLLM_MINIMAX_QK_RMS_ALLREDUCE_SCALE_OP=1` on top of the promoted 4x B70 MiniMax M2.7 AutoRound stack.

The candidate preserved quality across the full strict gate, including the `raw145-n256` exact-token check that caught the earlier Q/K scale-folding regression, but throughput was below the current promoted baseline. It should not be promoted or submitted to LocalMaxxing.

## Result

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Engine: `vLLM 0.20.1-local`, XPU, TP4
- Hardware: 4x Intel Arc Pro B70 32GB
- Shape: p512/n1536, ctx2048, batch 1, MBT512, block256
- Candidate mean output: `88.55875062027927` tok/s
- Candidate mean total: `118.07833416037236` tok/s
- Promoted baseline output: `89.31419538094708` tok/s
- Delta: `-0.75544476066781` output tok/s, about `-0.846%`

Per-repeat output tok/s:

- `88.67947748105625`
- `88.76126257759582`
- `87.19314984020325`
- `89.60111258226175`

Per-repeat total tok/s:

- `118.239303308075`
- `118.3483501034611`
- `116.257533120271`
- `119.46815010968233`

## Quality Gate

Passed:

- `raw145-n64-exact`
- `raw145-n256-exact`
- `semantic-suite-n64-r2`
- `arithmetic-repeat-n64-r16`
- `extended-sixpack-n64-r2`

Hashes matched the promoted references:

- raw145 n64: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- semantic suite: `adacbf144264486ea7d378ebb6a4c0ba23951b72c4cf86251a762b07ebef5805`
- arithmetic repeat: `578ec378bf31cb16fb49ac5c0043270fd00a0f7898e18ac498a41ffe775d7994`
- extended sixpack: `1e3560554f57b2b56cec8f49f28bc8ba12e9e0ced26bdc99a976f1433c99caa7`

## Candidate

Added a `torch.ops.vllm.all_reduce_inplace_scaled` custom op that performed:

1. `group._all_reduce_out_place(qk_var)`
2. `qk_var.mul_(1.0 / tp_world)`

The intent was to preserve the exact operation order of the promoted path while making the `(1, 2)` FP32 Q/K variance allreduce and scale visible as one custom-op boundary.

## Reliability Notes

The run produced intermittent shutdown noise:

- `Bad address (src/pipe.cpp:367)` in the semantic-suite log
- `Bad address (src/pipe.cpp:367)` in the fourth benchmark log

The quality and benchmark commands still completed, but this reinforces treating the candidate as a non-promoted negative.

## Artifacts

- Summary: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-qk-allreduce-scaled-customop-currenthigh-20260519-strict-tp4-ctx2048-mbt512-bs256-20260519T233656Z-summary.json`
- Quality directory: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-qk-allreduce-scaled-customop-currenthigh-20260519-strict-tp4-ctx2048-mbt512-bs256-20260519T233656Z-quality`
- Benchmark JSONs:
  - `/home/steve/bench-results/minimax-m2.7-strict-candidates/vllm-minimax-m27-autoround-tp4-p512n1536-20260519T235221Z.json`
  - `/home/steve/bench-results/minimax-m2.7-strict-candidates/vllm-minimax-m27-autoround-tp4-p512n1536-20260519T235506Z.json`
  - `/home/steve/bench-results/minimax-m2.7-strict-candidates/vllm-minimax-m27-autoround-tp4-p512n1536-20260519T235753Z.json`
  - `/home/steve/bench-results/minimax-m2.7-strict-candidates/vllm-minimax-m27-autoround-tp4-p512n1536-20260520T000047Z.json`

## Decision

Rejected. Runtime source and venv changes were reverted. The strict harness keeps the environment capture field for this variable so future replay can describe the candidate cleanly.
