# 2026-07-04: DFlash SWA Revisit

## Goal

Revisit `z-lab/Qwen3.6-27B-DFlash` after the prior no-win DFlash sweep, because
the local vLLM `qwen3_dflash.py` implementation appeared to ignore the draft
model's `layer_types`:

```text
layer_types = [
  "sliding_attention",
  "sliding_attention",
  "sliding_attention",
  "sliding_attention",
  "full_attention",
]
sliding_window = 2048
```

The model card warns that inference support may require vLLM changes for
interleaved SWA. The hypothesis was that treating every draft layer as full
attention hurt draft quality/acceptance, explaining the prior k=8 result at
only `49.994 tok/s` with acceptance falling sharply after position 2-3.

## Patch

Patch snapshot:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-qwen3-dflash-layer-types-swa-20260704.patch
```

The patch threads an optional `per_layer_sliding_window` into
`DFlashQwen3Attention`, then makes `DFlashQwen3DecoderLayer` opt into DFlash
layer-type modes via:

```text
VLLM_XPU_QWEN3_DFLASH_LAYER_TYPES=off          # default, current local behavior
VLLM_XPU_QWEN3_DFLASH_LAYER_TYPES=mixed        # honor config layer_types
VLLM_XPU_QWEN3_DFLASH_LAYER_TYPES=all-sliding  # diagnostic single KV group
```

The patch is default-off so current DFlash behavior remains unchanged unless a
run explicitly enables it.

Syntax checks passed:

```text
python3 -m py_compile vllm/model_executor/models/qwen3_dflash.py
ruff check vllm/model_executor/models/qwen3_dflash.py
```

## Mixed SWA Result

Command shape:

```bash
GPU_INDEX=1 PORT=19411 \
LABEL=qwen27-dflash-swa-layer-types-k8-cg8-realistic128-chat-tokenids-qwensuite \
QWEN36_27B_ENABLE_MTP=0 \
QWEN36_27B_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_QWEN3_DFLASH_LAYER_TYPES=mixed \
NUM_SPECULATIVE_TOKENS=8 \
GPU_MEMORY_UTILIZATION=0.90 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}' \
VLLM_EXTRA_ARGS='--speculative-config {"method":"dflash","model":"/mnt/fast-ai/llm-cache/hf/manual/z-lab--Qwen3.6-27B-DFlash","num_speculative_tokens":8}' \
scripts/run-qwen36-27b-autoround-vllm-candidate.sh
```

Run dir:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-dflash-swa-layer-types-k8-cg8-realistic128-chat-tokenids-qwensuite-20260704T045200Z
```

Outcome: invalid / startup crash before readiness.

Root cause:

```text
AssertionError: All drafting layers should belong to the same kv cache group
```

Honoring the model's mixed sliding/full layer types creates multiple draft
KV-cache groups. The current `llm_base_proposer.py` DFlash/EAGLE path assumes
all draft attention layers share one `CommonAttentionMetadata` stream and
asserts a single group during `initialize_attn_backend`. Supporting true mixed
DFlash SWA therefore needs deeper proposer metadata support, not just a
model-layer patch.

## All-Sliding Diagnostic

Purpose: keep a single KV-cache group by forcing every DFlash draft layer to
use the sliding window. This is not the exact draft model architecture, but it
is still target-verified speculative decoding; it only tests whether local/SWA
attention can materially improve draft acceptance without the mixed-group
proposer rewrite.

Command delta from the mixed run:

```text
VLLM_XPU_QWEN3_DFLASH_LAYER_TYPES=all-sliding
LABEL=qwen27-dflash-allsliding-k8-cg8-realistic128-chat-tokenids-qwensuite
```

Run dir:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-dflash-allsliding-k8-cg8-realistic128-chat-tokenids-qwensuite-20260704T045643Z
```

Result file:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-dflash-allsliding-k8-cg8-realistic128-chat-tokenids-qwensuite-20260704T045643Z.json
```

Outcome: valid but severe no-win.

```text
realistic_final_gate.passed = true
cached_tokens_all_zero = true
median tok/s 1-100 after TTFT = 20.6305
p10 tok/s 1-100 after TTFT = 19.4594
mean tok/s 1-100 after TTFT = 28.3153
median TTFT = 2066.3 ms
```

Server log acceptance snapshots show why it is slow: initial rows briefly
accept some early positions, then most rows collapse to around `1%` average
draft acceptance:

```text
0.867, 0.511, 0.267, 0.133, 0.067, 0.067, 0.044, 0.000  # early
0.031, 0.023, 0.016, 0.016, 0.008, 0.008, 0.000, 0.000  # later
0.021, 0.007, 0.007, 0.007, 0.007, 0.007, 0.007, 0.007  # later
```

## Decision

DFlash remains closed no-win for the current Qwen27/B70 stack:

- default/full-attention local DFlash was valid but only `~50 tok/s`;
- true mixed SWA cannot start because current proposer metadata assumes one
  draft KV-cache group;
- all-sliding single-group diagnostic starts and is valid/fresh, but collapses
  to `20.63 tok/s`.

Do not spend more time on DFlash config sweeps. A future revisit needs a real
implementation of multi-KV-group draft metadata in `llm_base_proposer.py` and
`gpu_model_runner.py` so DFlash can run its actual `4 sliding + 1 full`
architecture. That is a larger backend task and not an immediate route past the
current `65.276 tok/s` valid record.
