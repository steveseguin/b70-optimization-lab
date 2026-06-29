# 2026-06-26 MiniMax Fresh-Cache Control And B70 MoE Config Alias

## Context

Recent MiniMax M2.7 TP4 optimization attempts looked like little progress:
current strict runs were landing around `82-83 tok/s`, well below the promoted
`89.314195 output tok/s` LocalMaxxing record. A fresh-cache control was run to
separate real regression from stale inherited torch-compile artifacts.

## Fresh-Cache Control

Command shape:

```bash
cd /home/steve/qwen36-results-main
source repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh
export PYTHONPATH="/home/steve/src/vllm-minimax-boundary:${PYTHONPATH:-}"
export LABEL=minimax-m27-currenthigh-freshcache-control-20260626
export BENCH_REPEATS=2
export RUN_EXTENDED_QUALITY=0
export RUN_REPEAT_ARITHMETIC_QUALITY=1
export REPEAT_ARITHMETIC_RUNS=8
export RUN_AOT_BOUNDARY_CONTEXT=1
unset STRICT_REUSE_INHERITED_VLLM_CACHE_ROOT
scripts/run-minimax-strict-quality-gated-candidate.sh
```

Result:

- strict quality passed:
  - raw145 n64 exact;
  - raw145 n256 exact;
  - semantic n64 r2;
  - arithmetic repeat n64 r8.
- output throughput repeats: `82.044699`, `83.172970`;
- mean output throughput: `82.608835 tok/s`;
- mean total throughput: `110.145113 tok/s`.

Artifacts:

- summary:
  `/mnt/fast-ai/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-m27-currenthigh-freshcache-control-20260626-strict-tp4-ctx2048-mbt512-bs256-20260626T132932Z-summary.json`
- AOT boundary context:
  `/mnt/fast-ai/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-m27-currenthigh-freshcache-control-20260626-strict-tp4-ctx2048-mbt512-bs256-20260626T132932Z-aot-boundary-context.json`

Important log finding: every quality/benchmark stage warned that the tuned MoE
config was missing for the current device name:

```text
Using default MoE config. Performance might be sub-optimal!
Config file not found at .../configs/E=256,N=384,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,dtype=int4_w4a16.json
```

The existing tuned file is keyed to the older device identity:

```text
E=256,N=384,device_name=Intel(R)_Graphics_[0xe223],dtype=int4_w4a16.json
```

This likely explains much of the `89 -> 82 tok/s` regression after the driver /
runtime started reporting `Intel(R) Arc(TM) Pro B70 Graphics`.

## Alias Config Experiment

Patch tried in `/home/steve/src/vllm-minimax-boundary`:

```text
Add vllm/model_executor/layers/fused_moe/configs/E=256,N=384,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,dtype=int4_w4a16.json
with the same contents as the old Intel(R)_Graphics_[0xe223] int4 config.
```

The run selected the config successfully:

```text
Using configuration from .../E=256,N=384,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,dtype=int4_w4a16.json for MoE layer.
```

But it failed the first exact canary:

- label: `minimax-m27-b70-moe-config-alias-20260626`;
- failed: `raw145-n64-exact`;
- failure: combined token hash mismatch;
- observed token hash:
  `7f4222437a76869f7fde3e202d3c90a5e202583f603b57d4c9950fae6ad8bd67`;
- expected token hash:
  `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`;
- output was non-degenerate but shifted into a repeated Greek-token continuation.

Artifacts:

- summary:
  `/mnt/fast-ai/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-m27-b70-moe-config-alias-20260626-strict-tp4-ctx2048-mbt512-bs256-20260626T134602Z-summary.json`
- failed quality JSON:
  `/mnt/fast-ai/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-m27-b70-moe-config-alias-20260626-strict-tp4-ctx2048-mbt512-bs256-20260626T134602Z-quality/raw145-n64-exact.json`

Decision:

- reject the alias config as a quality-preserving speed fix;
- do not submit to LocalMaxxing;
- remove the alias from the active vLLM config directory so future runs do not
  inherit a known quality-failing MoE tune.

## Isolated MoE Config Screens

The old config alias failure was narrowed with isolated `VLLM_TUNED_CONFIG_FOLDER`
folders under `experiments/minimax_moe_tuned_configs/` instead of copying
candidates into the live vLLM source tree.

Control / first useful recovery:

- `explicit-default-current-device/` passed `raw145-n64-exact`, proving that a
  current-device config file itself is not enough to create drift.
- `m1-old-bn64-bk128-current-device/` passed strict quality:
  `raw145-n64-exact`, `raw145-n256-exact`, `semantic-suite-n64-r2`, and
  `arithmetic-repeat-n64-r8`.
- `m1-old-bn64-bk128-current-device/` speed:
  output repeats `83.716563`, `83.820778`; mean output `83.768670 tok/s`;
  mean total `111.691560 tok/s`.
- Decision: valid modest recovery over the fresh-cache control
  (`82.608835 -> 83.768670 output tok/s`), but not close to the promoted
  `89.314195 output tok/s` record and not a LocalMaxxing submission.

Metadata isolation:

- `m1-bn64-bk128-warps4-current-device/` passed raw145 n64 screen and then full
  strict quality, so `num_warps=4` alone is not the old alias quality bug.
- `m1-bn64-bk128-warps4-current-device/` speed:
  output repeats `83.750409`, `82.331092`; mean output `83.040750 tok/s`;
  mean total `110.721001 tok/s`.
- Decision: valid but slower than the tile-only candidate. Preserve as a
  negative/neutral result; do not promote or submit.
- `m1-bn64-bk128-stages4-current-device/` passed one raw145 n64 screen, but
  FAILED the first gate of the full strict fresh reload with the same bad token
  hash as the rejected old alias:
  `7f4222437a76869f7fde3e202d3c90a5e202583f603b57d4c9950fae6ad8bd67`.
- Decision: reject `num_stages=4` as unstable/unsafe even when tested without
  `num_warps=4`. The one-shot raw pass was not sufficient validation.

Interpretation so far: copying the full old file was unsafe, but the old
decode tile without old metadata is quality-safe and only modestly faster than
the default. The old alias failure is explained by `num_stages=4` instability,
while `num_warps=4` alone is quality-clean but slower.

## AOT Inspector Improvement

`scripts/inspect-minimax-aot-boundary-context.py` now includes pre-context and
classifies hidden-state allreduces into:

- `hidden_embedding_allreduce`;
- `hidden_attention_oproj_allreduce`;
- `hidden_delayed_residual_allreduce`;
- `hidden_moe_output_allreduce` when visible;
- `qk_rms_variance`.

This is needed because shape-only classification (`f16[...,3072]`) hides
whether a graph contains the rejected delayed-residual path or the attention
`o_proj` row-parallel path.

## Next Direction

The current practical baseline is quality-clean but degraded at ~`82.6 tok/s`.
The old MoE tune likely explains a large part of the historical `89 tok/s`
record, but it is not quality-valid under the current B70 device identity /
runtime. The next useful optimization lane is therefore:

1. retune the MiniMax int4 MoE config for
   `Intel(R)_Arc(TM)_Pro_B70_Graphics` under strict raw145 canaries, starting
   from conservative parameters rather than blindly copying the old tune;
2. only after restoring a quality-clean MoE config, return to hidden-state
   collective fusion or MoE-output boundary work.
