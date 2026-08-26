# Official Qwen3.8 FP8 TP4 exact-depth result

The preregistered official-FP8 TP4 profile passed all six measured depths on
one clean service lifetime. It uses the exact publisher FP8 revision and
`f01e24f...` vLLM XPU image, four B70 cards, MTP0, F16/auto KV, one slot, and a
size-one PIECEWISE decode graph.

| Exact active context | Decode tok/s | HTTP TTFT |
| ---: | ---: | ---: |
| 2,048 | `35.526051366782006` | `1,972.888 ms` |
| 4,096 | `34.898259891958816` | `3,662.974 ms` |
| 8,192 | `33.969008846291906` | `7,200.293 ms` |
| 16,384 | `33.643737958666264` | `14,424.102 ms` |
| 24,576 | `33.27243664089886` | `21,792.120 ms` |
| 32,768 | `33.106580865553255` | `29,236.436 ms` |

Every request returned exactly 128 token IDs, reported zero cached prompt
tokens, and passed the exact prompt count, timing, no-truncation, and
no-context-shift gates. All 66 weights passed strict `O_DIRECT` plus complete
ordinary-read verification before launch. Cleanup recorded `clean`; the
container was absent and port 19457 was closed when this result was sealed.

This is Grade C repeated-token shape evidence, not natural prose. The optional
effective-prompt-throughput values are prompt tokens divided by observed HTTP
TTFT and include scheduling and first-token work; they are not server/kernel
prefill. No x=0 point is fabricated.

The profile is additive and materially different from the faster AutoRound TP4
frontier. It does not replace any protected/headline value, authorize MTP or a
LocalMaxxing submission, or imply a causal TP scaling comparison with the TP1
eager or TP2 PIECEWISE profiles.

Evidence:

- [compact result](../data/2026-08-26-qwen38-official-fp8-tp4-http-depth-r1-result.json)
- [frozen preregistration](../data/2026-08-26-qwen38-official-fp8-tp4-http-depth-r1-prereg.json)
- raw root: `/mnt/fast-ai/bench-results/qwen38-official-fp8-tp4-http-depth-20260826-r1-attempt1`
