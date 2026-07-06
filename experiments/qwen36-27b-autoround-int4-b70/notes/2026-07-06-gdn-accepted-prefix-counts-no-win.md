# Qwen27 GDN Accepted-Prefix Counts: No-Win Endpoint Test

Date: 2026-07-06

Classification: strict fresh candidate screen, no promote, no LocalMaxxing.

## Purpose

The GDN recurrent-state contract shows that scheduler-visible accepted counts
are not always the same as draft-owned accepted-prefix lengths:

- a partial reject row can include a target-owned replacement token;
- a full accept row can include or suppress a target-owned bonus;
- shifted full-accept rows can expose scheduled draft suffixes;
- GDN/DeltaNet state commit must select only the verified draft prefix.

This experiment added a default-off `VLLM_XPU_GDN_ACCEPTED_PREFIX_COUNTS=1`
path that computes a GDN-only accepted-prefix count buffer from the verifier
row and passes it to GDN attention metadata, while leaving the shared
`num_accepted_tokens` buffer intact for scheduler/Mamba bookkeeping.

Patch snapshot:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-gdn-accepted-prefix-counts-no-win-20260706.patch
```

## Precheck

Both GDN contracts passed before endpoint work:

```bash
cd /home/steve/llm-optimizations
export PYTHONPATH="/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels${PYTHONPATH:+:$PYTHONPATH}"
export LD_LIBRARY_PATH="/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
/home/steve/.venvs/vllm-xpu/bin/python scripts/check-gdn-spec-recurrent-exact.py --device xpu:0 --num-reqs 2 --spec-len 3 --heads 2 --dim 8
/home/steve/.venvs/vllm-xpu/bin/python scripts/check-gdn-native-spec-prefix.py --device xpu:0 --num-reqs 3 --spec-len 4 --head-k-dim 32 --head-v-dim 32
```

The first contract still reports `old_accepted_count_path_equal=false`, which
is the reason this experiment was plausible.

## Endpoint Command

```bash
cd /home/steve/llm-optimizations
LABEL=qwen27-gdn-accepted-prefix-counts-replayssm-$(date -u +%Y%m%dT%H%M%SZ) \
GPU_INDEX=0 PORT=19420 \
QUALITY_REPEAT_RUNS=64 QUALITY_SKIP_LONG_CONTEXT=1 \
VLLM_XPU_GDN_ACCEPTED_PREFIX_COUNTS=1 \
VLLM_XPU_GDN_REPLAYSSM_SPEC=1 \
VLLM_XPU_GDN_REPLAYSSM_COMMIT_IN_FORWARD=1 \
VLLM_XPU_GDN_REPLAYSSM_SLOT_MGMT_TORCH_FALLBACK=1 \
VLLM_XPU_SPEC_DECODE_RESTORE_DRAFT_PARTIAL_REJECT_GDN_STATE=1 \
VLLM_XPU_SPEC_DECODE_RESTORE_DRAFT_FULL_ACCEPT_GDN_STATE=1 \
VLLM_XPU_LM_HEAD_INT8=1 \
VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16 \
VLLM_XPU_DRAFT_LM_HEAD_INT4=1 \
VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128 \
VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=bf16 \
QWEN36_27B_ENABLE_XPU_GRAPH=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}' \
QWEN36_27B_ENABLE_MTP=1 \
NUM_SPECULATIVE_TOKENS=3 \
experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh
```

The candidate wrapper now records `gdn_accepted_prefix_counts` in
`identity.env`; the run below predated that wrapper identity-field addition,
so the flag is recorded by this note and the command line.

## Result

Compact summary:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-gdn-accepted-prefix-counts-replayssm-20260706T064240Z-candidate-summary-20260706T064240Z.json
```

Strict realistic suite:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-gdn-accepted-prefix-counts-replayssm-20260706T064240Z-realistic128-chat-tokenids-qwensuite-20260706T064240Z.json
```

Repeat64 quality:

```text
data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-gdn-accepted-prefix-counts-replayssm-20260706T064240Z-repeat64-ctx1024-20260706T064240Z.json
```

Server log:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-gdn-accepted-prefix-counts-replayssm-20260706T064240Z-20260706T064240Z/server.stdout.log
```

Outcome:

- smoke passed;
- cached tokens were `0` on every realistic-suite request;
- quality passed: repeat64 passed, exact short canaries passed, baseline match
  all;
- final realistic gate failed because one prompt produced fewer than the
  100 token-id events needed for the primary window;
- measured rows were far below the record anyway: median
  `37.45137308954522 tok/s`, p10 `28.868642538309405`, mean
  `42.89043118046305`.

## Decision

No promote. Do not submit to LocalMaxxing.

This exact GDN-only accepted-prefix metadata path is closed as no-win for the
current ReplaySSM MTP3 recipe. The quality pass is useful: it suggests the row
mapping is not obviously corrupting outputs. The throughput loss is decisive:
feeding draft-prefix counts into the graph/ReplaySSM path changes the runtime
shape/accounting enough to collapse the speed lane, and it does not beat the
current `67.519 tok/s` record.

Keep the patch for reference, but do not carry it in active source. Future GDN
work should be a real fixed-shape transaction or branch/regenerate design, not
this metadata-only accepted-prefix buffer.
