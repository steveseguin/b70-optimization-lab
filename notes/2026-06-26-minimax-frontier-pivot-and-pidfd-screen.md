# MiniMax Frontier Pivot And pidfd IPC Screen, 2026-06-26

## Why Pivot Here

Gemma 4 26B A4B Q8 on one B70 has a valid fresh-response record at
`103.2992004295621 tok/s` after TTFT, but the most recent micro-op screens are
flat (`~102-103 tok/s`) and below the record. Further useful Gemma work likely
needs a larger router/speculation/verifier design, not more small flag sweeps.

MiniMax M2.7 AutoRound INT4 on 4x B70 is the better next optimization lane:

- current strict baseline: `89.314195` output tok/s / `119.085594` total;
- strict quality gates: raw145 n64/n256 exact hashes, semantic suite,
  arithmetic repeat, extended sixpack;
- remaining bottleneck is better scoped: TP collective/graph boundaries around
  Q/K variance, attention hidden-state allreduce, and MoE-output allreduce.

The historical evidence says high-level wrappers are mostly exhausted. Useful
future work should either:

1. move MoE-output allreduce/epilogue lower into the llm-scaler WS kernel path;
2. build a lower-level Q/K variance allreduce + RMS apply primitive;
3. fuse attention `o_proj` allreduce with residual/RMSNorm at a backend or
   compiler level;
4. implement a graph-safe exact router/top-k boundary inside the MiniMax WS
   MoE path.

Do not retry already-closed paths unless there is a materially different
implementation:

- Python-level attention `o_proj`, post-attn norm+MoE, router+WS, and Q/K
  post-AR wrappers were neutral or slower.
- `esimd_resadd_norm_gemv_int4_pert` is not a drop-in MiniMax router/projection
  win: it has a documented cross-workgroup residual/normed-output race and the
  corrected no-store diagnostic was slower on the real `o_proj` shape.
- Broad CCL/env sweeps, block-size changes, generic in-place allreduce
  thresholds, local-argmax variants, and logits gather shortcuts have already
  been rejected or are quality-sensitive.

## New Tooling Added

Added `scripts/inspect-minimax-aot-boundary-context.py`.

Purpose: inspect `computation_graph.py` files and extract the operation window
after each `all_reduce -> wait_tensor` pair. This gives a non-perturbing view
of what each collective immediately feeds, avoiding synchronized runtime timing
that changes graph behavior.

Also updated `scripts/run-minimax-strict-quality-gated-candidate.sh` to:

- record `CCL_IPC` and `CCL_ZE_IPC_EXCHANGE` in candidate summaries;
- optionally run the AOT boundary-context inspector via
  `RUN_AOT_BOUNDARY_CONTEXT=1`.

## Active Screen: pidfd IPC Transfer From REAP

Smallest untested high-value check:

```bash
source repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh
export PYTHONPATH="/home/steve/src/vllm-minimax-boundary:${PYTHONPATH:-}"
export CCL_IPC=pidfd
export CCL_ZE_IPC_EXCHANGE=pidfd
export LABEL=minimax-m27-currenthigh-pidfd-ipc-20260626
export BENCH_REPEATS=4
export RUN_AOT_BOUNDARY_CONTEXT=1
export STRICT_REUSE_INHERITED_VLLM_CACHE_ROOT=1
scripts/run-minimax-strict-quality-gated-candidate.sh
```

Rationale:

- the later REAP MiniMax lane got a small repeatable win from pidfd IPC;
- the original promoted 256-expert strict lane mostly tested older/default IPC
  contexts and fabric-vertex separately, not this exact transfer;
- this closes a concrete cross-lane uncertainty before spending source-build
  time on backend fusion.

Important guardrail: the active venv normally imports vLLM from the dirty
`/home/steve/src/vllm` tree. This screen forces
`PYTHONPATH=/home/steve/src/vllm-minimax-boundary` so it uses the isolated
MiniMax promoted source stack instead.

## Result: pidfd IPC Is A Clean Negative On The Current Strict High

Run summary:

- summary:
  `/mnt/fast-ai/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-m27-currenthigh-pidfd-ipc-20260626-strict-tp4-ctx2048-mbt512-bs256-20260626T125528Z-summary.json`
- quality artifacts:
  `/mnt/fast-ai/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-m27-currenthigh-pidfd-ipc-20260626-strict-tp4-ctx2048-mbt512-bs256-20260626T125528Z-quality/`
- AOT boundary context:
  `/mnt/fast-ai/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-m27-currenthigh-pidfd-ipc-20260626-strict-tp4-ctx2048-mbt512-bs256-20260626T125528Z-aot-boundary-context.json`

Strict quality status: **passed**.

- raw145 n64 exact: pass;
- raw145 n256 exact: pass;
- semantic suite n64 x2: pass;
- arithmetic repeat n64 x8: pass.

Performance:

- output tok/s repeats:
  `83.47563753425258`, `83.31422053943204`,
  `82.05084907518079`, `83.36878307691242`;
- mean output tok/s: **83.05237255644445**;
- mean total tok/s: **110.73649674192595**.

This is well below the current strict record
`89.314195` output tok/s / `119.085594` total, so it is **not** a
LocalMaxxing submission candidate. `CCL_IPC=pidfd` +
`CCL_ZE_IPC_EXCHANGE=pidfd` should not be promoted for the current MiniMax
strict lane.

The AOT context tool found `1000` allreduce sites across `8` rank graph files:

- `496` `qk_rms_variance` boundaries;
- `504` `hidden_state_unknown` boundaries.

This reinforces the source-level direction: reduce or move the Q/K variance and
hidden-state collective boundaries lower in the MiniMax path. More CCL/env flag
sweeps are unlikely to move the current frontier enough.
