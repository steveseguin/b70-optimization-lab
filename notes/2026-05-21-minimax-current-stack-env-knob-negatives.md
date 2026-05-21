# MiniMax M2.7 Current-Stack Env Knob Negatives

Date: 2026-05-21

Model: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`

Hardware: 4x Intel Arc Pro B70, TP4, XPU/vLLM 0.20.1-local, llm-scaler INT4 MoE path

Reference promoted result:

- Warm accepted result: 93.443623 output tok/s, 124.591498 total tok/s, p512/n1536.
- Restored-control repeat: 89.696348 output tok/s, 119.595131 total tok/s, p512/n1536.

## Screens

### `CCL_ZE_IPC_EXCHANGE=pidfd`

Command delta:

```bash
source repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh
export CCL_ZE_IPC_EXCHANGE=pidfd
export LABEL=minimax-currentstack-ccl-pidfd-20260521
export RUN_EXTENDED_QUALITY=0
export RUN_REPEAT_ARITHMETIC_QUALITY=1
export REPEAT_ARITHMETIC_RUNS=8
scripts/run-minimax-strict-quality-gated-candidate.sh
```

Quality result: passed.

- raw145 n64: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- arithmetic per-run token hash: `def6899500b2364bc97d561fc5f9cc78aa9fbcd5a0eb032eab1f2c6735d2bbec`

Speed result:

- Output tok/s: 89.212628, 87.462406
- Mean output tok/s: 88.337517
- Total tok/s: 118.950171, 116.616541
- Mean total tok/s: 117.783356

Decision: rejected. Quality was clean, but throughput is below both the warm accepted run and the restored-control repeat.

### `VLLM_XPU_CUDAGRAPH_STRONG_OUTPUT=1`

Command delta:

```bash
source repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh
unset CCL_ZE_IPC_EXCHANGE
export VLLM_XPU_CUDAGRAPH_STRONG_OUTPUT=1
export LABEL=minimax-currentstack-strong-cudagraph-output-20260521
export RUN_EXTENDED_QUALITY=0
export RUN_REPEAT_ARITHMETIC_QUALITY=1
export REPEAT_ARITHMETIC_RUNS=8
scripts/run-minimax-strict-quality-gated-candidate.sh
```

Quality result: passed.

- raw145 n64: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- arithmetic per-run token hash: `def6899500b2364bc97d561fc5f9cc78aa9fbcd5a0eb032eab1f2c6735d2bbec`

Speed result:

- Output tok/s: 89.052803, 89.594216
- Mean output tok/s: 89.323510
- Total tok/s: 118.737071, 119.458955
- Mean total tok/s: 119.098013

Decision: rejected. Quality was clean, but throughput did not beat the restored-control repeat and remained below the warm accepted run.

## Takeaway

The remaining easy env-level graph/CCL knobs are not obvious wins on the current promoted stack. The next credible optimization work should stay close to measured bottlenecks: repeated small allreduces, Q/K variance reductions, attention output projection collectives, and MoE output allreduce scheduling/fusion.
