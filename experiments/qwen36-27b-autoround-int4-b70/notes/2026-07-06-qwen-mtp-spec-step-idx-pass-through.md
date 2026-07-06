# Qwen MTP `spec_step_idx` Pass-Through Artifact

Date: 2026-07-06

## Summary

Preserved a focused future-use patch for Qwen MTP draft models:

- `patches/qwen36-27b-autoround-int4-b70/vllm-qwen-mtp-spec-step-idx-pass-through-future-20260706.patch`

The proposer hunk is against the active local Qwen27 vLLM experiment stack,
which already contains mixed draft-KV, timing, and diagnostic changes around
the same forward calls. If replaying on a clean upstream vLLM checkout, adapt
the two proposer call-site hunks manually; the model-wrapper hunks are the
substantive behavior change.

This patch plumbs `spec_step_idx` from `LLMBaseProposer` into the outer
`Qwen3_5MTP.forward()` and `Qwen3NextMTP.forward()` wrappers. The inner
predictor blocks already accept `spec_step_idx` and select:

```python
current_step_idx = spec_step_idx % self.num_mtp_layers
```

Without the pass-through, a multi-layer Qwen MTP checkpoint would reuse the
default step index and could fail to use position-specific MTP layers for
later speculative positions.

## Status For Current Qwen27 Lane

This is **not** a current Qwen27 record candidate. The checked
`webhie/Qwen3.6-27B-int4-AutoRound` snapshot has only one MTP layer:

```text
mtp.layers.0.*
```

No `mtp.layers.1` or deeper layers were found in the local safetensors scan,
so `spec_step_idx % self.num_mtp_layers` is always zero for the current
record-family checkpoint. The patch is expected to be a no-op for current
Qwen27 endpoint throughput and quality.

## Validation

Compile check passed in the XPU vLLM environment:

```bash
cd /home/steve/src/vllm
/home/steve/.venvs/vllm-xpu/bin/python -m py_compile \
  vllm/v1/spec_decode/llm_base_proposer.py \
  vllm/model_executor/models/qwen3_5_mtp.py \
  vllm/model_executor/models/qwen3_next_mtp.py
```

No GPU endpoint benchmark was run because the local checkpoint has only one
MTP layer and the change cannot plausibly move the current `68.236 tok/s`
headline. Keep this patch as a future audit item for Qwen checkpoints with
`mtp_num_hidden_layers > 1` or multiple `mtp.layers.N` tensors.

## Why Keep It

The earlier July 4 audit correctly concluded not to spend current Qwen27 GPU
time on `spec_step_idx`, but the code path was still a legitimate latent bug
for deeper Qwen MTP checkpoints. Preserving the focused patch prevents the
idea from being lost while keeping the current model lane honest.
