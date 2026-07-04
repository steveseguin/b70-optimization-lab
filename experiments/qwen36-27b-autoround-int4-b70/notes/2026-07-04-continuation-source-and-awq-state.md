# 2026-07-04 - Continuation: source state, AWQ variant, and next action

## Scope

Continuation of the Qwen3.6 27B INT4 AutoRound one-B70 lane after the strict
candidate runner repro:

- current best valid record remains
  `webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8 LM-head BF16 scales`;
- strict fresh median remains `65.27648650325429 tok/s`, LocalMaxxing
  `cmr5iu3gk00bfq901nidgcana`;
- latest same-recipe runner support row is
  `64.84180902803895 tok/s`, strict/fresh/`cached_tokens=0`, no quality rerun
  because the recipe was already quality-gated.

No LocalMaxxing submission was made in this continuation block.

## Source snapshot preserved

Before any further source work, timestamped snapshots of the dirty local source
trees were saved:

```text
patches/qwen36-27b-autoround-int4-b70/source-snapshots/vllm-active-dirty-20260704T125939Z.patch
patches/qwen36-27b-autoround-int4-b70/source-snapshots/vllm-xpu-kernels-active-dirty-20260704T125939Z.patch
```

These are not promoted patches. They are safety snapshots of the active local
worktrees:

- `/home/steve/src/vllm` on branch `codex/qwen36-quark-int8-tracking`;
- `/home/steve/src/vllm-xpu-kernels` detached with dirty kernel changes.

Do not revert those source trees casually. If a future experiment needs a clean
tree, make a separate checkout or explicitly preserve a new snapshot first.

## Quick no-repeat audit

A local notes/source audit found no new cheap env-only candidate worth another
strict run. The obvious flags are already closed:

- exact/spec top-ID sampler plumbing: strict-valid but flat because
  `get_top_tokens()` still materializes dense LM-head logits;
- draft-only verifier row reduction: collapsed/invalid for headline use because
  it removes normal target replacement / target-owned bonus behavior;
- scheduler-only adaptive depth: strict-valid but slower because it lowers
  emitted tokens per verifier step;
- MTP1/MTP2/MTP4/MTP5 and capture-size sweeps: current recipe keeps MTP3/cg8;
- scratchpad ring-size: movements stayed below variance;
- hot-vocab draft top-1: loses too much acceptance;
- standalone full-vocab compact top-1 and candidate-max kernels: exact but not
  faster than dense oneDNN plus argmax.

The remaining source lanes are therefore deep, not config roulette:

1. a genuinely integrated LM-head/top-ID primitive that removes dense logits
   without a second reduction launch;
2. a native lazy verifier that avoids whole LM-head rows/calls while preserving
   target replacement and bonus semantics;
3. DFlash/parallel-drafting multi-KV metadata support, not an assertion delete;
4. a stronger target-matched drafter trained/evaluated on held-out data.

An independent source audit reached the same conclusion: the best remaining
mechanism is an exact top-ID producer that helps **both** draft and target
greedy LM-head calls. The existing consumers are already in place; the blocker
is the producer. Any new attempt should start in `vllm-xpu-kernels` / oneDNN
LM-head code and stop at microbench unless it is exact and at least `>1.10x`
faster for both rows `1` and rows `4` at the real Qwen27 shape
(`hidden=5120`, `vocab=248320`, BF16 scales). Do not run endpoint validation
for another near-parity full-vocab scan.

## AWQ INT4 variant status

Current unscreened same-quality-class candidate:

```text
cyankiwi/Qwen3.6-27B-AWQ-INT4
revision 8f269fb53eb3fe3be8f01f9755f20570cef0ebe0
total size about 19.06 GiB
```

Rationale: it is a same-family Qwen3.6 27B INT4/AWQ checkpoint and therefore a
plausible strict-screen candidate, unlike FP8/NVFP4 lanes which need separate
quality/quantization labeling.

A download was started into the normal internal HF cache:

```text
/mnt/fast-ai/llm-cache/hf/hub/models--cyankiwi--Qwen3.6-27B-AWQ-INT4
```

Detached shell children were killed by the tool environment, so the active
download must run as a tracked foreground/tool session if it is still needed.
If the snapshot completes, first strict screen should use:

```bash
cd /home/steve/llm-optimizations
MODEL_DIR=/mnt/fast-ai/llm-cache/hf/hub/models--cyankiwi--Qwen3.6-27B-AWQ-INT4/snapshots/8f269fb53eb3fe3be8f01f9755f20570cef0ebe0 \
QWEN36_27B_AR_REPO=cyankiwi/Qwen3.6-27B-AWQ-INT4 \
LABEL=qwen27-cyankiwi-awq-int4-int8lmhead-bf16scale-mtp3-cg8 \
SERVED_MODEL_NAME=qwen36-27b-cyankiwi-awq-int4 \
GPU_INDEX=0 PORT=19420 \
MAX_MODEL_LEN=2048 MAX_NUM_BATCHED_TOKENS=1024 MAX_NUM_SEQS=1 \
GPU_MEMORY_UTILIZATION=0.95 \
QWEN36_27B_ENABLE_MTP=1 NUM_SPECULATIVE_TOKENS=3 \
QWEN36_27B_ENABLE_XPU_GRAPH=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}' \
VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1 \
VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0 \
VLLM_XPU_LM_HEAD_INT8=1 \
VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16 \
VLLM_EXTRA_ARGS='--quantization compressed-tensors' \
QWEN36_27B_DEFAULT_ENABLE_THINKING=0 \
QWEN36_27B_ENABLE_PROMPT_TOKEN_DETAILS=1 \
QUALITY_BASELINE_JSON=data/qwen36-27b-autoround-int4-b70-baselines/quality-webhie-int8lmhead-bf16scale-mtp3-cg8-repeat32-ctx1024-20260703T223138Z.json \
RUN_QUALITY=1 READINESS_TIMEOUT_S=1200 \
experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh
```

Promotion requires the full strict gate plus quality:

- fixed Qwen realistic suite, each prompt once, `cached_tokens=0`;
- same target quant/checkpoint identity clearly labeled as AWQ INT4;
- deterministic quality suite and baseline comparison before any LocalMaxxing
  submission;
- explicit compressed-tensors quantization in the launch identity;
- no graph-none fallback, CPU fallback, silent dequantization, or speculative
  state shortcut in server logs;
- same-window webhie control if the result is inside the known variance band.

## Next action

If the AWQ checkpoint finishes, screen it first because it is a clean
checkpoint-level candidate. If it does not finish promptly, do not block the
lane on network transfer: continue only with a deliberate deep source patch
cycle from the four remaining lanes above, with a preserved patch and a
microbench/strict stop criterion before endpoint promotion.
