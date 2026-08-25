# Qwen3.8 27B Q4_K_M TP1 small-context HTTP concurrency preregistration

This campaign fills the package's missing service-concurrency evidence. It is
not the earlier raw-engine `llama-batched-bench` ladder and it is not a
long-context profile.

The frozen deployment uses one B70, 64 server slots, 32K total F16 KV context
(`512` nominal tokens per slot), short prompts, and 128 forced output tokens.
It measures synchronized OpenAI-compatible HTTP batches at
`1,2,4,8,16,32,64` requests, twice. All 64 expanded prompts first receive a
sequential same-server oracle. A curve qualifies only if every measured output
has the full 128 tokens, reports zero cached prompt tokens, and matches its
prompt's oracle hash exactly.

The exact preregistration is
[`2026-08-25-qwen38-q4km-tp1-http-smallctx-r1-prereg.json`](../data/2026-08-25-qwen38-q4km-tp1-http-smallctx-r1-prereg.json),
and the fixed short-prompt suite is
[`2026-08-25-qwen38-q4km-tp1-http-smallctx-suite.json`](../data/2026-08-25-qwen38-q4km-tp1-http-smallctx-suite.json).
The runner preserves a startup, OOM, or support failure as a result boundary;
it does not silently reduce slots, KV precision, or context.

The dense Qwen3.8 27B result must not be compared as if it were the separate
Qwen-derived sparse MoE/NVFP4 result discussed as a roughly 875 tok/s target.
This campaign measures the dense one-card package that users can reproduce.
