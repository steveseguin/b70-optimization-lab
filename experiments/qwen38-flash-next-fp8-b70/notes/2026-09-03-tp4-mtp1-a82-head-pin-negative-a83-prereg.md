# Qwen3.8 Flash-Next FP8 A82 pre-check negative and A83 preregistration

Date: 2026-09-03 10:52--10:54 EDT

A82 (eager MTP1 on the deterministic line at 4352 tokens, derived from the
eager A66 packet) never served: its launcher inherited A66's overlay head
pin `805cde59...` and the pre-check stopped with `FAIL: vLLM overlay head
changed`, because the overlay has been at `2169dbfe...` (the V2-runner
graph-dispatch receipt on top of 805cde59) since A72. No GPU work ran.

A83 is the A82 packet at attempt 83 / port 19755 with the launcher's two
head literals moved to `2169dbfe38c2954edc5ae50e94f68d45be071b79`; the
question, design, driver and reading are those of the A82 preregistration.
`tools/rewrite-q38-a82-to-a83-head-pin.py`; packet: launcher `10b794de...`,
client `47f3b116...`, supervisor `757a0a16...`, host wrapper `9f182538...`.
