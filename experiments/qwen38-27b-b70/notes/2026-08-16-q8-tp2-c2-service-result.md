# Qwen3.8 Q8 target-only TP2 concurrency-two service result

Status: **reproducible separate service-capacity result; not a single-stream record**.

The accepted Q8 source and binary were launched with two 8K slots
(`--parallel 2 --ctx-size 16384`). Two different raw-completion prompts were
first captured sequentially with fixed slot IDs. Two persistent HTTP
connections were then released through a synchronization barrier and each
generated 256 tokens.

Two independent runs measured `57.398122` and `57.397626 tok/s` aggregate by
the conventional 255-interval-per-request metric. Per-request rates were
`28.699956`/`28.699486` and `28.727575`/`28.700991 tok/s`; aggregate wall rates
were `56.488104` and `56.511198 tok/s`.

Both outputs in both runs were token-ID exact against their same-server
sequential oracle, every request reported `cache_n=0`, and minimum/maximum
request fairness exceeded `0.999`. The lane is target-only Q8_0 with F16 KV:
no MTP, DFlash, draft model, speculation, prompt cache, or response reuse.

This result demonstrates useful throughput above the user's 40 tok/s service
goal, but it must be described as two-request aggregate capacity. It does not
change the primary `36.772932 tok/s` single-request record. An earlier broad
c2 test alternated between two stable greedy-output pairs in both its control
and candidate arms; these two fixed prompts did not reproduce that behavior,
but the broader scheduling caveat is not declared solved.
A later batch-shape sweep strengthened that limitation: `2048/512` was exact
twice for this pair but diverged 0/2 for a disjoint fixed-prompt pair. See the
[broader audit](2026-08-16-q8-c2-batch-shape-audit.md).

The public reproduction is
[`repro/qwen38-27b-q8-tp2-c2-asrock-b70`](../../../repro/qwen38-27b-q8-tp2-c2-asrock-b70/README.md),
and the compact measurements are in
[`2026-08-16-q8-tp2-c2-summary.json`](../data/2026-08-16-q8-tp2-c2-summary.json).
