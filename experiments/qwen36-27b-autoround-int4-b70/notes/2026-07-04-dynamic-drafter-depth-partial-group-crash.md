# 2026-07-04 - Dynamic drafter depth prototype: partial-group crash

## Summary

Tested a default-off source prototype intended to fix the weakness in the
earlier scheduler-only adaptive-depth no-win: actually shorten the Qwen MTP
proposer loop so low-acceptance steps stop paying all three draft LM-head calls.

Result: the prototype is not viable on the current XPU spec path. It crashed
with an XPU indexing assert as soon as it created a shorter partial speculative
group. This confirms that the current Qwen/GDN XPU verifier path still expects
full speculative groups for stable graph execution.

No LocalMaxxing submission: candidate did not complete the strict gate.

## Patch

Patch snapshot:

- `patches/qwen36-27b-autoround-int4-b70/vllm-dynamic-drafter-depth-partial-group-crash-20260704.patch`

Important caveat: this is an active-stack snapshot from `/home/steve/src/vllm`,
not a clean upstream patch. The experiment-specific pieces were:

- `vllm/v1/spec_decode/llm_base_proposer.py`
  - added an optional `num_speculative_tokens_override`;
  - used the override to stop the serial MTP proposer loop early.
- `vllm/v1/worker/gpu_model_runner.py`
  - computed a single-request dynamic depth from the previous step's accepted
    draft-token count;
  - made the draft-token CPU copy path handle shorter tensors.

The active vLLM source was reverted after the crash. Syntax was rechecked after
revert:

```bash
cd /home/steve/src/vllm
/home/steve/.venvs/vllm-xpu/bin/python -m py_compile \
  vllm/v1/spec_decode/llm_base_proposer.py \
  vllm/v1/worker/gpu_model_runner.py
```

## Strict A/B

Both runs used the current fastest webhie/BF16-scale INT8-LM-head recipe:

- `MODEL_DIR=/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e`;
- `NUM_SPECULATIVE_TOKENS=3`;
- `COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}'`;
- `QWEN36_27B_ENABLE_XPU_GRAPH=1`;
- `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`;
- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`;
- `VLLM_XPU_LM_HEAD_INT8=1`;
- `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`.

Control:

- artifact:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-dyndraft-control-mtp3-cg8-20260704T043335Z-20260704T043335Z.json`;
- strict gate: pass, `cached_tokens=0`;
- median: `66.38933459706479 tok/s`;
- p10: `58.50132094237427`;
- mean: `65.20973836738533`;
- TTFT median: `604.704387835227 ms`;
- interpretation: support/variance only, not a record. It is the same recipe as
  the approved `65.27648650325429 tok/s` LocalMaxxing row.

Candidate:

- env:
  `VLLM_XPU_SPEC_DECODE_DYNAMIC_DRAFTER_DEPTH=1`,
  `VLLM_XPU_SPEC_DECODE_DYNAMIC_DRAFTER_MIN_DEPTH=2`,
  `VLLM_XPU_SPEC_DECODE_DYNAMIC_DRAFTER_LOW_ACCEPT=0`;
- run directory:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-dyndraft-min2-low0-mtp3-cg8-20260704T043335Z-20260704T043335Z`;
- outcome: HTTP 500 on the strict suite; no result JSON;
- server failure:
  `_xpu` indexing assert in `ATen/native/xpu/sycl/Indexing.h:622`,
  `index out of bounds`, followed by `EngineDeadError`.

## Interpretation

This is a useful closure, not just a crash:

- the previous scheduler-only adaptive-depth patch lost because it shortened
  scheduled verifier rows but still let the proposer generate the full
  fixed-depth MTP draft;
- this prototype did shorten the proposer, but the resulting partial
  speculative groups hit the same class of XPU verifier/metadata limitations
  already called out by `VLLM_XPU_SPEC_DECODE_DISABLE_PARTIAL_DRAFT_GROUPS`;
- therefore dynamic depth is not a low-risk route until the XPU Qwen/GDN spec
  verifier supports partial groups end-to-end.

Do not retry variable-depth proposer/scheduler heuristics as config-only or
Python-only work. A real implementation would first need source-level partial
group support in the verifier metadata/GDN path, with graph capture and quality
validation, before it can be judged on throughput.

Current next credible lanes remain:

1. fixed-depth LM-head call/row reduction that preserves full-group metadata;
2. accepted-token improvement without partial groups;
3. a better exact LM-head primitive integrated with oneDNN/XPU execution.
