# Qwen target-Q8/F16 TP1 fa0 graph-port parent sentinel R2 preregistration

State: **preregistered, sealed, inert, and not launched**.

R2 asks only whether the incremental pointer-stable Q8 memo repair closes the
exact parent-boundary failure preserved by R1. It does not retry a curve. It
uses a distinct campaign ID and create-only output root. The rebuilt runtime,
incremental patch, source manifest, build receipts, and complete 34-library DSO
closure are sealed in the machine-readable preregistration. The captured R1
result root remains immutable.

## Frozen boundary

- target-only Qwen3.6 27B Q8_0, TP1, MTP0, F16 K/V;
- the accepted `fa0f3b25` base and focused graph-port overlay remain pinned;
- `common.hpp` must remain byte-identical at `ce4c8541...`;
- post-R2 `ggml-sycl.cpp` must be exactly `f0c4bda8...`;
- the incremental memo patch and reconstruction manifest hashes are sealed;
- rebuilt `llama-cli`, `libggml-sycl`, CMake receipts, and all 34 effective DSO
  identities are sealed;
- both arms generate exactly 64 tokens from the same rebuilt binary, model,
  prompt, seed, runtime knobs, libraries, and fresh process-local caches;
- the only arm delta is graph/cache `0/0` versus `1/8`.

The repair contract is narrower than “dedup works.” A graph-enabled lookup may
not wait for, free, or resize storage whose address can remain embedded in a
cached executable graph. Reuse requires sufficient existing capacity; no-fit
behavior appends fresh bounded stable storage, while exhaustion or allocation
failure aborts closed. Graph-off semantics are outside the patch.

## Fail-closed gates

The graph-off arm must report one all-zero graph summary. The graph-on arm must
have positive request/miss/record/create/hit/direct-replay/replay counts; zero
rejection, unsupported, cache-full, update, and recreation counts; cache limit
eight; and all of these equalities:

- `requested == cache_hit + cache_miss`;
- `cache_hit == direct_replay`;
- `cache_miss == recorded == created == cache_entries`;
- `replayed == requested`.

The 64 generated output bytes and SHA must match exactly across arms. A failure
remains a failure; no partial rows can be promoted.

## Authority

Even a pass grants parent-sentinel mechanism/parity evidence only. It grants no
curve, website publication, speed claim, quality grade, record submission,
TP2, or TP4 authority. It cannot replace any protected graph-off value.

The sealed runner requires this exact acknowledgement before execution:

```text
RUN qwen36-q8-f16-tp1-fa0-graph-port-sentinel-20260825-r2
```

Create-only root:

```text
/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-fa0-graph-port-sentinel-20260825-r2
```
