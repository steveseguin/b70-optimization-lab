# Qwen target-Q8/F16 TP1 fa0 graph-port parent sentinel preregistration

State: **preregistered, build identity sealed, and not launched**.

This is the first runtime gate for the focused two-file graph evidence/cache
port on the accepted `fa0f3b25` Qwen optimization base. It asks one question:
does the same newly built graph-enabled binary produce exactly the same 64-token
output with graphs disabled and with persistent graph cache eight enabled, while
the candidate actually records and directly replays graphs without falling back?

The manifest now seals `llama-cli`, `libggml-sycl`, and the 34-library `ldd`
closure. The runner's inert plan and read-only `--check` pass. This does not
authorize execution by itself: the completed packet must be reviewed, committed
on clean `main`, and pushed before the exact acknowledgement works.

## Frozen identity

- model: target-only Unsloth Qwen3.6 27B Q8_0,
  SHA `f93f517f...`;
- source: independent detached tree
  `/home/steve/src/llama.cpp-q38-tp1-graph-port` at base `fa0f3b25`;
- overlay: only the tracked two-file graph port, SHA `1a8589f8...`;
- build: independent AOT `bmg_g31` sibling, graph compiled on, DNN and host-memory
  fallback off;
- both arms: the same new `llama-cli`, model, DSOs, prompt, seed, F16 K/V,
  process lifecycle, and optimization knobs;
- only arm deltas: graph/cache `0/0` versus `1/8`.

The source remains reconstructable even though the independent detached tree is
modified: HEAD, the exact two-path status, post-apply file hashes, tracked patch,
and reverse applicability are all mandatory.

## Pass gates

The graph-off control must emit exactly one device-0 shutdown summary with every
graph/cache/rejection counter zero. The graph-on candidate must report:

- zero compatibility rejection, device unsupported, and cache-full events;
- cache limit eight;
- positive request, miss, record, create, hit, direct-replay, and replay counts;
- `replayed == requested`;
- exact counter conservation: every request is a cache hit or miss, every hit
  is a direct replay, and every miss is one record/create/cache entry with no
  graph update or recreation;
- output bytes and SHA exactly equal to the graph-off control.

Both arms start with fresh process-local home, cache, and temporary directories.
No prompt cache, response reuse, history reuse, unsafe native-recording variable,
or profiler is allowed. Each child owns a process group, reads stdin from
`/dev/null`, has a 900-second watchdog, and is terminated and then killed if it
does not exit.

The sealed DSO closure must also prove that the `libggml-sycl` actually resolved
by `llama-cli` is the same canonical file and SHA as the separately pinned graph
backend, rather than merely proving that both files exist.

That list is explicitly an `ldd` link-time closure. Runtime-loaded Level Zero
and Unified Runtime driver components are outside it; the inherited device and
postflight receipts identify the effective accelerator stack observed during
the run.

## Authority

A pass is only bounded mechanism and exact-output-parity evidence for this exact
binary on TP1. It grants no context-depth cells, website publication, speed
floor, quality upgrade, LocalMaxxing submission, TP2, or TP4 authority. Existing
graph-off measurements and protected featured speeds remain immutable.

Acknowledgement after sealing and review:

```text
RUN qwen36-q8-f16-tp1-fa0-graph-port-sentinel-20260825-r1
```

Create-only root:

```text
/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-fa0-graph-port-sentinel-20260825-r1
```
