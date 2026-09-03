# Qwen3.8 Flash-Next FP8 A64 GDN inner trace: served, jittered, captured nothing

Date: 2026-09-02 20:02--20:20 EDT
Status: procedural negative; the trace question is unanswered; no promotion
claim; protected results unchanged

## What happened

A64 loaded and served (weights 20:14, healthy 20:17) at overlay head
`69f905f1...` and reproduced the depth-8 jitter under the trace build:
eight identical 8-token prefills returned the same top token with a top-1
logprob spread of 0.3575 nats, and the three 128-token repeats produced three
hashes, diverging at token 10. No hang, no kernel GPU fault; one USB UAS
device reset on the external checkpoint drive at 20:10 during shard loading
did not interrupt the load. Teardown exited 143 as in A62/A63.

No `gdn-trace-rank*.json` file was written. The API server environment held
`Q38_REPEATABILITY_TRACE_FILE` but none of the five
`VLLM_XPU_QWEN4_EXP_REPEATABILITY_TRACE_*` settings: the base launcher unsets
inherited `VLLM_*` variables before serving (this is why the trace file path
already had a `Q38_` alias). The trace therefore kept its 4000-position
minimum and rank-0 default and never armed for an 8-token prompt.

## Fix and successor

Overlay commit `c027fe2d12a8002996c5448654ef9d87fb26cdeb` reads every trace
setting through `Q38_REPEATABILITY_TRACE_<NAME>` as well; 11 trace tests
pass. A65 (`tools/rewrite-q38-a64-to-a65-q38-trace.py`) is A64 with that
head and the five settings exported under the alias names. Attempt 65 /
port 19737; names carry `q38trace`. Packet: launcher `202d0f17...`, client
`4620efed...`, supervisor `b39836d0...`, host wrapper `cc411503...`. The A64
prereg's question and reading rules apply unchanged.

Receipt: `.../qwen38-flash-next-fp8-tp4-ep4-gdntrace-mtp0-2304-ple-only-r1-attempt64/a64-logprob-determinism.json`.
