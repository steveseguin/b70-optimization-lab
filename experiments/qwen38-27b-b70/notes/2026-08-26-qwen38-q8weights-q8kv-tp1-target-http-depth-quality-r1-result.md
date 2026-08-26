# Qwen3.8 Q8_0 weights / Q8_0 KV TP1 HTTP depth result

The current-weight Qwen3.8 27B Q8_0 artifact passed all seven target-only,
MTP0, graph-off, fit-off TP1 HTTP cells in one server lifetime:

| active context | decode tok/s |
|---:|---:|
| 0 | 15.64211300487966 |
| 2,048 | 14.874633425244946 |
| 4,096 | 14.242379238866612 |
| 8,192 | 13.144786025605898 |
| 16,384 | 11.10097936684887 |
| 24,576 | 9.640680271615087 |
| 32,768 | 8.548307893500933 |

Every depth request returned 128 token IDs with zero cached tokens. All 16
terminal checks passed. The full battery passed 7/7 exact cases, two identical
repeat hashes, the 25,200-token needle (25,212 tokens after API templating), and
10/10 cache-zero requests. Cleanup left no open port, busy render node, forced
kill, or surviving server.

The frozen Grade-D estimate was high throughout. Its central value was 25.17%
above measured HTTP serving at x=0 and 29.20% above at 32K; every actual point
fell below the estimate's lower band. The exact seven-point comparison is
preserved in
[`../data/2026-08-26-qwen38-q8weights-q8kv-tp1-estimator-calibration-r1.json`](../data/2026-08-26-qwen38-q8weights-q8kv-tp1-estimator-calibration-r1.json).
That is an out-of-sample protocol calibration: the estimate explicitly targeted
raw-engine llama-bench and withheld HTTP, while this result measures HTTP.

Raw evidence is retained at
`/mnt/fast-ai/bench-results/qwen38-q8weights-q8kv-tp1-target-http-depth-quality-20260826-r1`
(24 files). The terminal receipt SHA-256 is
`a48968624a9b167e2e997031b8dfadc4af91d89dd0e838e76351cd0c96cf3f4e`.
The compact result is
[`../data/2026-08-26-qwen38-q8weights-q8kv-tp1-target-http-depth-quality-r1-result.json`](../data/2026-08-26-qwen38-q8weights-q8kv-tp1-target-http-depth-quality-r1-result.json).

Authority is exactly seven Grade-C Q8_0-weight/Q8_0-KV HTTP cells and their own
quality disclosure. It grants no F16-KV, other-weight, MTP, graph, TP2/TP4,
prefill, concurrency, headline, protected-speed, LocalMaxxing, or submission
claim.
