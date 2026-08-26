# Qwen3.8 Q5_K_S F16-KV TP1 graph cache-20 8K sentinel R2

The failed cache-8 sentinel identified a bounded capacity-ordering mechanism,
not a correctness failure. Its one server lifetime issued 146 graph requests:
18 occurred before the 128 generated tokens, so the eight-entry cache was full
before the recurrent decode shape could be retained. The candidate consequently
reported zero hits, 138 cache-full fallthroughs, and only eight initial
record/replays.

R2 changes no source, binary, model, request, batching, KV, fit, TP, MTP, or
quality selector. It repeats the exact graph-off 8K control and changes the
candidate graph cache from 8 to 20. Twenty is frozen from the 18 observed
warmup/prefill requests plus the two recurrent decode shapes in the qualified
same-architecture Qwen3.6 nonzero-depth evidence. The source supports up to 64,
but this packet forbids automatic escalation.

Passing requires exact token-ID, text, usage, returned-prompt, and cache-zero
parity with graph off. The candidate must report exactly 146 requests, no
cache-full/reject/unsupported/update/recreate events, at least 120 cache hits
and direct replays, every request replayed, and strict counter conservation.
This distinguishes real recurrent decode engagement from merely recording a
larger set of one-shot prefill graphs.

A pass authorizes only a separate reviewed full-curve preregistration. It
creates no site cell, quality claim, speed floor, protected-value replacement,
or submission authority. If cache 20 fills, capacity must not be raised inside
the run; the next design must use phase-aware eviction or partitioning. If hits
remain absent without cache-full, signature-field instrumentation is required
before relaxing equality.

Static check (inert):

```bash
python3 -B experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-q5ks-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r2.py --check
```

The create-only launch, after the normal clean/pushed-main and idle-device
gates, requires the exact acknowledgement printed by `--check`.
