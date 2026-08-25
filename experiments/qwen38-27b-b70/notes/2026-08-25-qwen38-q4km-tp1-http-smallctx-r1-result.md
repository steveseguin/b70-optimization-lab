# Qwen3.8 Q4_K_M TP1 small-context HTTP r1: completed, not qualified

The exact one-B70 service profile is supported: `llama-server` became healthy
with 64 slots, 32K total F16 KV context (`512` per slot), and peak observed GPU
memory of `32281.7 / 32656 MiB`. It completed all 318 requests without OOM or
truncation. Every request returned 128 tokens, reported `cached_tokens=0`, and
ended at the requested length.

The output-identity gate failed, so no package curve is promoted:

| concurrent HTTP requests | repeat 1 aggregate tok/s | repeat 2 aggregate tok/s | exact vs sequential oracle r1 / r2 |
| ---: | ---: | ---: | ---: |
| 1 | 25.095 | 25.089 | 1/1 · 1/1 |
| 2 | 37.727 | 24.912 | 1/2 · 2/2 |
| 4 | 50.302 | 25.001 | 2/4 · 4/4 |
| 8 | 57.565 | 27.056 | 2/8 · 1/8 |
| 16 | 55.428 | 31.794 | 4/16 · 3/16 |
| 32 | 66.174 | 39.312 | 10/32 · 6/32 |
| 64 | 86.277 | 85.972 | 23/64 · 23/64 |

No measured output hash matched an oracle from another base task. The result
therefore does not show an exact cross-request response swap, but it does show
shape-dependent greedy output variation. The large repeat-order hysteresis at
2–32 also makes a same-server ascending-repeat curve unsuitable as the user
expectation.

The structured closeout is
[`2026-08-25-qwen38-q4km-tp1-http-smallctx-r1-summary.json`](../data/2026-08-25-qwen38-q4km-tp1-http-smallctx-r1-summary.json).
Full per-request timings, text, hashes, usage, and cache fields remain in
[`attempt1/result.json`](../data/qwen38-q4km-tp1-http-smallctx-20260825-r1-attempt1/result.json).
The core dump occurred only during the old double-signal shutdown after all
evidence was written; the runner now sends one TERM through `timeout` before
cleaning the empty scope.
