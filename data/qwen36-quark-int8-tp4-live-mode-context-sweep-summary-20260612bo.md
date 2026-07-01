# Qwen3.6 Live Mode And Context Sweep

Endpoint: `http://127.0.0.1:18080`
Model root: `/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118`

| Case | Mode | Prompt | Output | Stream tok/s | E2E tok/s | Decode ms/token | Prefill ms | TTFT ms | Queue ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| stream_p512_o512 | stream | 512 | 512 | 99.590 | 98.328 | 10.023 | 69.284 | 74.503 | 0.0079 |
| nonstream_p512_o512 | nonstream | 512 | 512 | n/a | 98.668 | 9.989 | 69.235 | 74.030 | 0.0079 |
| stream_p512_o256 | stream | 512 | 256 | 100.384 | 97.860 | 9.925 | 69.146 | 74.203 | 0.0077 |
| stream_p4096_o256 | stream | 4096 | 256 | 99.964 | 87.326 | 9.980 | 358.145 | 375.545 | 0.0092 |

## Comparisons

- Non-stream p512/o512 decode median is `9.989` ms/token versus stream `10.023` ms/token (`-0.34`% delta); E2E tok/s delta is `0.35`%.
- Stream p4096/o256 decode median is `9.980` ms/token versus p512/o256 `9.925` ms/token (`0.55`% delta), while TTFT grows from `74.2` ms to `375.5` ms.

## Interpretation

- SSE streaming is not a large c1 decode bottleneck for this endpoint; non-streaming did not materially improve decode ms/token.
- Longer prompt context mainly increases TTFT/prefill. Steady decode ms/token stayed near 10 ms at p512 and p4096.
- Queue time remained around 0.008-0.009 ms/request, so queueing/frontdoor work is not the first 2x target.
- The next high-value optimization should focus on model execution, command submission/synchronization, TP/collective topology, or verifier-safe multi-token acceptance.
