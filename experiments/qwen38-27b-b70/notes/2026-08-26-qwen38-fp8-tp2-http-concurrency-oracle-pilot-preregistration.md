# Qwen3.8 official FP8 TP2 HTTP concurrency oracle pilot

Status: **preregistered; not launched; pilot rates are non-publishable**.

This pilot freezes a sequential 128-token-ID oracle for 64 distinct expanded
prompts on the exact official-FP8 TP2 package. The server has four active
sequence slots, so concurrency points above four deliberately include queueing.
The retained latency rows distinguish request TTFT and end-to-end latency; they
must never be described as unqueued latency.

The pilot passes only if every sequential response contains 128 complete raw
token IDs and reports zero cached prompt tokens. Its concurrent batches exist
only because the frozen harness performs them after oracle generation; none of
the pilot rates or latencies may be published. On pass, only compact prompt and
token-ID digests advance to a separately committed two-fresh-server protocol.

No point may be interpolated or extrapolated. Semantic quality remains covered
by the package's separate quality gate.

See the [machine-readable contract](../data/2026-08-26-qwen38-fp8-tp2-http-concurrency-oracle-pilot-r1-prereg.json).
