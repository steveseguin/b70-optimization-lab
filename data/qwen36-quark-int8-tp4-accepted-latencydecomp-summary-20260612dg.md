# Qwen3.6 C1 Latency Decomposition

- Status: `pass`.
- Decision: `device_or_vllm_runtime_bound_not_http_or_frontdoor`.
- Current best: `100.480 tok/s`.
- Current best ms/token: `9.952`.
- Target: `200.000 tok/s` (`5.000 ms/token`).
- Required ms/token reduction: `49.76%`.

## Comparisons

- `backend_stream_client_vs_vllm_decode_pct`: `0.006%`
- `backend_nonstream_e2e_vs_backend_stream_corrected_pct`: `-0.980%`
- `frontdoor_stream_vs_backend_stream_corrected_pct`: `-0.053%`

## Decision Reasons

- backend client throughput matches vLLM decode histogram within 3%
- vLLM queue time is effectively zero for c1
- frontdoor path is within 2% of backend direct
- non-streaming does not materially improve throughput

## Scenarios

### `backend_stream`
- Path: `http://127.0.0.1:18080`
- Mode: `stream`
- `client_after_first_corrected_tok_s`: `100.024`
- `client_e2e_tok_s`: `98.521`
- `vllm_decode_tok_s_from_histogram`: `100.018`
- `vllm_decode_ms_per_generation_token`: `9.998`
- `vllm_queue_ms`: `0.012`
- `vllm_prefill_ms`: `72.432`
- `client_ttft_ms`: `88.111`
- `vllm_ttft_ms`: `77.045`

### `backend_nonstream`
- Path: `http://127.0.0.1:18080`
- Mode: `nonstream`
- `client_e2e_tok_s`: `99.044`
- `vllm_decode_tok_s_from_histogram`: `100.480`
- `vllm_decode_ms_per_generation_token`: `9.952`
- `vllm_queue_ms`: `0.013`
- `vllm_prefill_ms`: `68.142`
- `vllm_ttft_ms`: `72.523`

### `frontdoor_stream`
- Path: `http://127.0.0.1:8000`
- Mode: `stream`
- `client_after_first_corrected_tok_s`: `99.971`
- `client_e2e_tok_s`: `98.528`
- `vllm_decode_tok_s_from_histogram`: `99.957`
- `vllm_decode_ms_per_generation_token`: `10.004`
- `vllm_queue_ms`: `0.011`
- `vllm_prefill_ms`: `67.972`
- `client_ttft_ms`: `85.020`
- `vllm_ttft_ms`: `72.741`

## Next Optimization Focus

- Do not spend primary effort on HTTP, SSE, or frontdoor overhead for c1 decode.
- The 200 tok/s target requires roughly 5 ms/token decode; current clean c1 is about 10 ms/token.
- Focus on XPU/vLLM decode internals: MoE kernel path, graph replay, collectives, scheduler step shape, and topology.
