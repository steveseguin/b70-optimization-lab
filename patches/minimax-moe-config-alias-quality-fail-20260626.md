# MiniMax B70 MoE Config Alias Quality Failure

Date: 2026-06-26

## Patch Tried

Add this file to the isolated MiniMax vLLM worktree:

```text
vllm/model_executor/layers/fused_moe/configs/E=256,N=384,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,dtype=int4_w4a16.json
```

Contents copied from the old promoted device-name config:

```json
{
  "triton_version": "3.7.0",
  "1": {
    "BLOCK_SIZE_M": 16,
    "BLOCK_SIZE_N": 64,
    "BLOCK_SIZE_K": 128,
    "GROUP_SIZE_M": 1,
    "num_warps": 4,
    "num_stages": 4,
    "SPLIT_K": 1
  },
  "64": {
    "BLOCK_SIZE_M": 64,
    "GROUP_SIZE_M": 1,
    "SPLIT_K": 1
  },
  "256": {
    "BLOCK_SIZE_M": 64,
    "GROUP_SIZE_M": 1,
    "SPLIT_K": 1
  },
  "512": {
    "BLOCK_SIZE_M": 64,
    "GROUP_SIZE_M": 1,
    "SPLIT_K": 1
  }
}
```

## Why Tried

Fresh current runs were using default MoE config because the runtime now reports
the B70 as `Intel(R)_Arc(TM)_Pro_B70_Graphics`, while the existing tuned config
is keyed to `Intel(R)_Graphics_[0xe223]`.

## Result

Rejected. The alias was selected, but `raw145-n64-exact` failed immediately:

```text
expected token hash: 267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd
observed token hash: 7f4222437a76869f7fde3e202d3c90a5e202583f603b57d4c9950fae6ad8bd67
```

Observed output was non-degenerate but shifted into repeated Greek-token text,
so this is a semantic/numerical change, not a runtime crash.

Artifacts:

- `/mnt/fast-ai/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-m27-b70-moe-config-alias-20260626-strict-tp4-ctx2048-mbt512-bs256-20260626T134602Z-summary.json`
- `/mnt/fast-ai/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-m27-b70-moe-config-alias-20260626-strict-tp4-ctx2048-mbt512-bs256-20260626T134602Z-quality/raw145-n64-exact.json`

The active alias file was removed from the vLLM worktree after recording this
result so future strict runs do not inherit a known quality-failing config.

