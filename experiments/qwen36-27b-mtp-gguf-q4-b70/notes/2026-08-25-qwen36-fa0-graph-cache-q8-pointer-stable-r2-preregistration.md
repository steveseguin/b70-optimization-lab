# fa0 persistent-graph Q8 pointer-stability r2 preregistration

Date: 2026-08-25

Status: **incremental patch prepared and statically gated; not built or run by
this packet. No GPU, curve, or publication authority.**

## Why this bounded change exists

The clean fa0 graph-port r1 parent sentinel passed its graph-off arm and then
failed in the graph-on/cache-eight arm during graph compute three. Two earlier
computes had completed record and replay. The exception said that `wait`
cannot be called on a queue while it is recording a command graph.

Source reachability makes the Q8 dedup memo resize wait the strongest diagnosis:
the Q8 door was enabled; verification, cross-device, and host-destination waits
were unreachable in this TP1/MMVQ arm; and MMVQ itself contains no wait. This
is a preregistered diagnosis, not retroactive causal proof.

The r2 patch makes Q8 memo allocations pointer-stable only when both SYCL graph
mode and a positive persistent graph-cache size are active. It chooses the
smallest stale slot that is already large enough, preserving larger stable
allocations for later requests. Otherwise a fresh bounded slot is appended.
Exhausting all 320 stable slots or failing a new stable allocation aborts
closed. An allocated slot may not enter the existing wait/free/resize block in
this mode, because previously finalized executable graphs can retain its
address. Teardown drains submitted work, then clears both persistent-cache and
legacy executable graphs before context destruction frees memo allocations.

Simply deleting the wait was rejected: freeing or resizing the allocation
without synchronization could leave cached graphs with dangling pointers.

## Exact source chain

Apply in this order to clean llama.cpp
`fa0f3b25a47f346858a4d0d169f5181aa424b110`:

1. `llamacpp-fa0-graph-cache-evidence-port-20260825.patch`, SHA-256
   `1a8589f894fde7d87aac35c59bc81e3701bf7f6d9ba54f35808ae262325d7892`;
2. `llamacpp-fa0-graph-cache-q8-pointer-stable-r2-20260825.patch`, SHA-256
   `1575acc5ee07b37eb98186a09d201a895d36501c223dc114110a43ee08f4e0a3`.

The incremental patch requires `ggml-sycl.cpp` preimage SHA-256
`024fda2f9e667aa82cfdac64c079b5cb932e6a40e90031ad16cfd142bec93544`
and produces
`f0c4bda8beb3c0b06c72edc202fcc074d72e031433a4eacd8a91b8acf5f468a0`.
It changes no other file.

The machine-readable contract is
[`2026-08-25-qwen36-fa0-graph-cache-q8-pointer-stable-r2-prereg.json`](../data/2026-08-25-qwen36-fa0-graph-cache-q8-pointer-stable-r2-prereg.json).

## Preserved graph-off behavior

The new condition is false unless graph mode is enabled with a positive cache.
With it false, the stale-slot predicate reduces exactly to the old
`generation != gen` predicate. The existing bounded append, live-entry ring
eviction, queue wait, free, reallocation, and OOM fallback remain in place.
The default environment therefore follows the prior accepted graph-off path.

The CPU-only static test reconstructs clean fa0, applies the parent port, checks
the exact preimage, applies r2, checks the exact postimage, and exercises the
graph-off predicate truth table:

```bash
python3 experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/test_fa0_graph_cache_q8_pointer_stable_r2_patch.py \
  --source /home/steve/src/llama.cpp-q38-tp1-lane
```

## Frozen next gate

After independent review and a sealed rebuild, the only authorized GPU work is
fresh campaign
`qwen36-q8-f16-tp1-fa0-graph-port-sentinel-20260825-r2`: graph off/cache zero,
then graph on/cache eight in a fresh process using the same new binary and all
other inputs unchanged. Both arms must complete, clean up, pass the existing
canary, and produce byte-identical output. The candidate must show positive
record/create/direct-replay counts, `replayed == requested`, and no rejection,
cache-full, or stable-slot-exhaustion event.

Any later failure is still failure and must be preserved before another code
change. A pass establishes only TP1 parent mechanism and parity. It does not
measure an exact-depth cell, authorize TP2/TP4, replace any graph-off speed, or
grant website, record, or submission authority.
