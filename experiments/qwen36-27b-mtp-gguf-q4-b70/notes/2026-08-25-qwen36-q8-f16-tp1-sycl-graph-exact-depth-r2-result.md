# Qwen target-Q8/F16 TP1 SYCL graph exact-depth R2 result

State: **failed at depth 0 multi-summary parsing; cleanup passed**.

Verbose mode exposed complete graph telemetry. `llama-bench` emitted two
positive summaries because it benchmarks prompt processing and token generation
with separate backend context lifecycles. Both independently passed strict
capture/replay conservation:

- prompt: 24 requests = 16 hits + 8 misses; 8 records/creates; 24 replays;
- generation: 641 requests = 638 hits + 3 misses; 3 records/creates; 641 replays.

Both had zero compatibility rejection, device rejection, cache-full, update, or
recreation counts. The R2 parser deliberately rejected the unexpected summary
count rather than selecting one.

The immutable R2 root grants no cell. The valid R3 evidence rule is to require
every summary emitted for a context to pass independently, then aggregate their
counters. No runtime, source, model, build, DSO, context, or performance setting
needs to change, and protected graph-off values remain untouched.
