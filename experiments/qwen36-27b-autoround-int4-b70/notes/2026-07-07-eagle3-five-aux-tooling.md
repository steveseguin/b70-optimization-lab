# 2026-07-07: EAGLE3 five-aux tooling for accepted-depth research

## Classification

Diagnostic tooling only. This is not a throughput benchmark, not a quality run,
and not a LocalMaxxing submission.

## Why

The current strict Qwen27 record is `68.236 tok/s` with MTP3 and about
`2.74695` target-verified tokens per verifier step. The step-cost budget shows
MTP3 cannot reliably reach `>100 tok/s` at current step cost; accepted depth
must improve beyond the intrinsic MTP3 ceiling, or target/verifier step cost
must drop by multi-ms amounts.

Small target-body cleanup just closed as too small
(`qkvz+ba` projection packing projected only `~0.16 ms` across 48 GDN layers),
so the next credible lane is a stronger target-matched draft.

## Change

The offline Ex0bit EAGLE3 evaluator/trainer now supports arbitrary aux hidden
state count instead of hard-coding three aux states:

- existing checkpoints still infer `aux_count=3` from `fc.weight`;
- `--aux-count 5` expands a 3-aux checkpoint to five aux slots;
- default expansion maps source slots `[0, 1, 2]` to target slots `[0, 2, 4]`,
  matching old layers `[1, 31, 60]` into DFlash/Hipfire-style layers
  `[1, 16, 31, 46, 61]`;
- new slots are zero-filled, so the expanded checkpoint initially behaves like
  the old draft and can learn the extra aux layers during training;
- the 4-GPU rollout training harness passes through `AUX_COUNT` and
  `AUX_SOURCE_TARGET_SLOTS`.

Smoke:

```text
aux_count=5
fc_shape=(5120, 25600)
nonzero slots=[0, 2, 4]
zero slots=[1, 3]
```

## Planned first run

Collect a fresh 5-aux corpus with the concrete-context v6b suite:

```bash
SUITE=experiments/qwen36-27b-autoround-int4-b70/eagle-chat-corpus-v6b-suite.json \
EAGLE3_AUX_LAYERS=1,16,31,46,61 \
SHARD_PROMPTS=96 \
OUTPUT_TOKENS=160 \
experiments/qwen36-27b-autoround-int4-b70/scripts/run-eagle3-aux-corpus-v2-4gpu.sh
```

Then run a bounded four-GPU training screen from the original Ex0bit compressed
checkpoint:

```bash
CORPUS=<5aux-run-root> \
AUX_COUNT=5 \
AUX_SOURCE_TARGET_SLOTS=0,2,4 \
SWEEP=survival-objective \
EPOCHS=6 \
BATCH_SIZE=64 \
experiments/qwen36-27b-autoround-int4-b70/scripts/run-ex0bit-eagle3-rollout-train-v3-4gpu.sh
```

Endpoint integration remains gated. Do not wire this into vLLM unless offline
acceptance reaches at least the previous endpoint-worthiness threshold
(`1.5-2.0` mean accepted, ideally clearly higher on heldout).
