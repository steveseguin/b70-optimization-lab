# MiniMax M2.7 MoE WS Up N-Tile 1 Runtime Fail - 2026-05-21

## Goal

Test whether forcing the llm-scaler MiniMax INT4 MoE workspace up-projection
decode tile to `N_TILE=1` improves single-stream decode throughput on the
current promoted 4x B70 stack. The default decode path has used `N_TILE=2`;
older tile screens covered larger values, so this was the remaining smaller
tile shape.

This changed only the MoE workspace tile knob:

`VLLM_XPU_MOE_WS_UP_NTILE=1`

No model, quantization, sampling, router precision, speculative decoding,
driver, power, or quality-harness relaxation was used.

## Quality Gate

The raw145 n64 exact-output gate passed before speed screening:

- Passed: `true`
- Expected-token hash match: `true`
- Combined token SHA256:
  `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- Deterministic across selected runs: `true`

## Speed Screen

The warm p512/n1536 speed screen did not produce throughput data. It failed on
the first decode path after graph capture with a Level Zero resource error:

`RuntimeError: level_zero backend failed with error: 40 (UR_RESULT_ERROR_OUT_OF_RESOURCES)`

The failure occurred inside vLLM input preparation while converting
`num_computed_tokens` to `torch.int64`. The log showed a GPU KV cache size of
`33,792` tokens and graph capture completing with `0.40 GiB` before the
runtime failure.

## Decision

Reject for now. The candidate preserved exact output on the short quality gate,
but it is not a usable optimization because the warm throughput screen was not
runtime-stable. It was not promoted to the full strict quality suite and was
not submitted to LocalMaxxing.

If revisited, use a fresh graph cache and a lower
`--gpu-memory-utilization` value to distinguish tile-kernel instability from
Level Zero memory-pressure sensitivity. Treat any future result as a new
candidate that must repeat the exact-output gates.

## Artifacts

- Raw145 n64 quality JSON:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/moe-ws-up-ntile1-quality-20260521T105359Z/minimax-moe-ws-up-ntile1-raw145-n64.json`
- Raw145 n64 quality log:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/moe-ws-up-ntile1-quality-20260521T105359Z/minimax-moe-ws-up-ntile1-raw145-n64.log`
- Failed warm screen log:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/moe-ws-up-ntile1-warm-20260521T110002Z/minimax-moe-ws-up-ntile1-warm-p512n1536.log`
- Summary data:
  `data/minimax-m27-moe-ws-up-ntile1-runtime-fail-20260521.json`
