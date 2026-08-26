# Qwen3.8 Q8_0 TP1 HTTP p64 fit closure

The preregistered `qwen38-q8-tp1-http-concurrency-oracle-pilot-20260825-r1`
profile is **unsupported on one 32 GiB Arc Pro B70**. The exact Q8_0 model,
accepted TP1 server, 64 slots, 32,768 total context tokens, and F16 KV reached
device allocation and then failed with
`UR_RESULT_ERROR_OUT_OF_DEVICE_MEMORY` while clearing the recurrent-state
allocation. The HTTP endpoint never became healthy, so the attempt produced no
request or speed row.

This is a fit boundary, not a benchmark result. It must not be displayed as
zero throughput and it does not authorize extrapolating a 64-user rate from a
smaller profile.

The preregistered follow-up is
`2026-08-25-qwen38-q8-tp1-http-capacity-oracle-pilot-r2-prereg.json`: an ordered
32/16/8-slot F16-KV ladder that keeps the nominal context budget at 512 tokens
per slot and stops at the first output-qualified fit. Capacity-discovery rates
remain non-publishable until a compact oracle and two fresh-server publication
attempts are sealed.
