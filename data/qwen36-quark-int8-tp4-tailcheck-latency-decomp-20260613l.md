# Qwen3.6 C1 Latency Decomposition

- Status: `pass`.
- Decision: `unknown`.
- Current best: `100.863 tok/s`.
- Current best ms/token: `9.914`.
- Target: `200.000 tok/s` (`5.000 ms/token`).
- Required ms/token reduction: `49.57%`.

## Comparisons

- `backend_stream_client_vs_vllm_decode_pct`: `0.018%`
- `backend_nonstream_e2e_vs_backend_stream_corrected_pct`: `-2.984%`
- `frontdoor_stream_vs_backend_stream_corrected_pct`: null

## Decision Reasons

- backend client throughput matches vLLM decode histogram within 3%
- vLLM queue time is effectively zero for c1

## Scenarios

### `backend_stream`
- Path: `http://127.0.0.1:18080`
- Mode: `stream`
- `client_after_first_corrected_tok_s`: `100.836`
- `client_e2e_tok_s`: `97.944`
- `vllm_decode_tok_s_from_histogram`: `100.817`
- `vllm_decode_ms_per_generation_token`: `9.919`
- `vllm_queue_ms`: `0.012`
- `vllm_prefill_ms`: `68.728`
- `client_ttft_ms`: `84.867`
- `vllm_ttft_ms`: `73.552`

### `backend_nonstream`
- Path: `http://127.0.0.1:18080`
- Mode: `nonstream`
- `client_e2e_tok_s`: `97.827`
- `vllm_decode_tok_s_from_histogram`: `100.863`
- `vllm_decode_ms_per_generation_token`: `9.914`
- `vllm_queue_ms`: `0.016`
- `vllm_prefill_ms`: `72.670`
- `vllm_ttft_ms`: `77.499`

## Next Optimization Focus

- Do not spend primary effort on HTTP, SSE, or frontdoor overhead for c1 decode.
- The 200 tok/s target requires roughly 5 ms/token decode; current clean c1 is about 10 ms/token.
- Focus on XPU/vLLM decode internals: MoE kernel path, graph replay, collectives, scheduler step shape, and topology.
