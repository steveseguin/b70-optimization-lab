# 2026-07-05: MTP Text `input_ids` Dispatch No-Win

## Summary

Closed no-win. A default-off vLLM experiment tried to route text-only Qwen3.5
MTP recurrent draft calls through `input_ids` instead of precomputed
`inputs_embeds`, hoping to keep embedding lookup inside the captured draft
forward and remove an external embed/copy path. The idea did not reach a valid
endpoint result:

- first attempt crashed during engine profiling before readiness;
- compile-shape workaround got past the first crash but stalled during decode
  PIECEWISE graph capture and was killed;
- active vLLM source was reverted;
- patch artifact is preserved for reference only.

Do not rerun this exact lane unless the Qwen3.5 MTP compile/cudagraph shape is
redesigned.

## Motivation

Dispatch tracing on the current Qwen27 record family showed every recurrent
MTP-next draft forward using external embeddings:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-mtp-next-dispatch-trace-20260705T173032Z-20260705T173032Z/mtp-next-dispatch.jsonl
```

Observed shape:

- `input_ids=None`
- `inputs_embeds=[1,5120]`
- `cudagraph_runtime_mode=PIECEWISE`
- repeated for all 64 traced rows

Because the active model resolves to `Qwen3_5MTP` (`config.model_type=qwen3_5`,
server log `Resolved architecture: Qwen3_5MTP`), the experiment targeted
`llm_base_proposer.py` and `qwen3_5_mtp.py`, not the Qwen3Next model file.

## Attempt 1: Direct Text `input_ids`

Label:

```text
qwen27-mtp-text-inputids-next-20260705T205433Z
```

Run directory:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-mtp-text-inputids-next-20260705T205433Z-20260705T205433Z
```

Compact summary:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-mtp-text-inputids-next-20260705T205433Z-candidate-summary-20260705T205433Z.json
```

Identity highlights:

```text
model_dir=/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e
gpu_index=0
port=19420
num_speculative_tokens=3
enable_xpu_graph=1
compilation_config={"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}
VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1
VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0
VLLM_XPU_LM_HEAD_INT8=1
VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16
VLLM_XPU_MTP_TEXT_INPUT_IDS_NEXT=1
```

Result:

- no smoke;
- no strict fresh benchmark;
- summary status `bench_rc=99`, `smoke_rc=99`;
- engine initialization failed in the dummy/profile path.

Root failure:

```text
AttributeError: 'NoneType' object has no attribute 'size'
```

The crash came from the torch compile dynamic-shape sizing path for
`inputs_embeds`. The experiment intentionally passed `inputs_embeds=None`, but
the Qwen3.5 MTP compile decorator still marked `inputs_embeds` as a dynamic
argument, so Dynamo tried to call `size()` on `None`.

## Attempt 2: Remove `inputs_embeds` Dynamic Dim In This Mode

Label:

```text
qwen27-mtp-text-inputids-next-v2-20260705T205746Z
```

Run directory:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-mtp-text-inputids-next-v2-20260705T205746Z-20260705T205746Z
```

Delta:

- same recipe as attempt 1;
- `VLLM_DISABLE_COMPILE_CACHE=1`;
- patched `qwen3_5_mtp.py` to omit `inputs_embeds` from dynamic arg dims when
  `VLLM_XPU_MTP_TEXT_INPUT_IDS_NEXT=1`.

Result:

- got past the `inputs_embeds=None` sizing crash;
- compiled with cache disabled;
- captured mixed prefill/decode PIECEWISE graphs;
- stalled at decode PIECEWISE capture:

```text
Capturing CUDA graphs (decode, PIECEWISE): 0%| | 0/1
```

The server never became ready, no strict/fresh artifact was produced, and the
run was killed. Treat this as a graph-capture no-win rather than a measured
performance result.

## Patch Artifact

Preserved reference patch:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-mtp-text-inputids-next-no-win-20260705.patch
```

The patch artifact captures the relevant source delta but is not a promoted
working patch. Active vLLM source was restored to remove all
`VLLM_XPU_MTP_TEXT_INPUT_IDS_NEXT` references.

## Runner Improvement Kept

`scripts/run-vllm-candidate.sh` now records these identity fields in
`identity.env`:

```text
mtp_text_input_ids_next
mtp_next_dispatch_trace_file
disable_compile_cache
```

This is useful for future compile/cudagraph experiments and should remain.

## Decision

Closed no-win. The current Qwen27 record path is still:

- webhie AutoRound INT4 checkpoint;
- runtime INT8 LM-head with BF16 scales;
- MTP3/cg8;
- `65.27648650325429 tok/s` strict fresh median tokens 1-100 after TTFT;
- LocalMaxxing `cmr5iu3gk00bfq901nidgcana`.

This lane does not change the record, should not be submitted to LocalMaxxing,
and should not consume more endpoint runs unless a deeper compile/cudagraph
design changes how Qwen3.5 MTP accepts optional `inputs_embeds`.

## Next Implication

The wrapper-level MTP dispatch shortcut did not unlock >65 tok/s. Continue
with mechanisms that can actually change the cost model:

- stronger target-matched drafter / more accepted tokens per verifier step;
- graph-safe exact GDN/spec-state transaction or tape;
- target-forward/kernel reductions with standalone proof before endpoint runs.
