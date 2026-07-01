# Qwen3.6 Local Argmax And MTP Rejected

Date: 2026-06-10

## Context

The accepted Qwen3.6 Quark W8A8 INT8 no-prefix TP4 profile remains:

- Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- Backend: vLLM/XPU, TP4, 32K context, piecewise XPU graph, no prefix cache
- Accepted single artifact: `data/qwen36-quark-int8-tp4-noprefix-accepted-single-refresh2-20260610.json`
- Accepted single corrected after-first decode: `98.69124458727285 tok/s`
- Accepted e2e decode: `97.42802156674345 tok/s`

## MTP Check

The checkpoint config advertises `mtp_num_hidden_layers: 1`, and this local vLLM tree has a `qwen3_5_mtp` drafter implementation. The actual safetensors index does not contain MTP weights:

- `model.safetensors.index.json` total keys: `62696`
- keys containing `mtp`: `0`

Decision: do not pursue current-model MTP speculative decoding for this checkpoint. It would require weights that are not present, and downloading/swapping a different model is outside the current constraint.

## Local Argmax Candidate

The local vLLM tree has a greedy local-argmax path that avoids full-vocab logits gather for safe greedy requests. Qwen3.5/Qwen3.6 did not expose `get_top_tokens()`, so the runner could not use that path.

Tested patch:

- `patches/vllm-qwen36-local-argmax-get-top-tokens-rejected-20260610.patch`

Runtime flags common to both variants:

- `VLLM_XPU_LOCAL_ARGMAX_DECODE=1`
- Same accepted TP4/no-prefix/32K/piecewise graph settings

Variant 1 used the default pair all-gather reducer.

- Artifact: `data/qwen36-quark-int8-tp4-noprefix-local-argmax-single-20260610.json`
- Corrected after-first decode: `97.63840043080454 tok/s`
- E2E decode: `96.38714252970836 tok/s`
- Total client throughput: `192.7742850594167 tok/s`
- TTFT: `78.31955200526863 ms`

Variant 2 used packed all-reduce:

- Additional flag: `VLLM_XPU_LOCAL_ARGMAX_PACKED_ALLREDUCE=1`
- Artifact: `data/qwen36-quark-int8-tp4-noprefix-local-argmax-packed-single-20260610.json`
- Corrected after-first decode: `98.58692468108492 tok/s`
- E2E decode: `97.3604605420973 tok/s`
- Total client throughput: `194.7209210841946 tok/s`
- TTFT: `75.565325882053 ms`

## Decision

Reject and revert the Qwen `get_top_tokens()` source edit.

The packed reducer lowered TTFT slightly, but corrected after-first and e2e decode both remained below the accepted baseline. Full-logits gather/sampling is not currently the dominant single-request bottleneck for this workload, and the extra local-max/reduction path does not buy enough to keep.

