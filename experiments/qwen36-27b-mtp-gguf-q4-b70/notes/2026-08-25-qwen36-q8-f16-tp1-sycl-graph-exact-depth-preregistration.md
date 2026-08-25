# Qwen3.6 target Q8/F16 TP1 SYCL-graph exact-depth preregistration

Date: 2026-08-25. Status: **drafted, inert, and deliberately unsealed**.

This packet is the first possible seven-cell expansion after the focused fa0
graph-port parent sentinel. It covers exactly one child-artifact slice:

- revision `qwen3.6-27b`;
- artifact `qwen36-27b-unsloth-q8-0-82d411a`;
- Q8_0 target weights with no embedded MTP tensors;
- llama.cpp SYCL, TP1, MTP0, F16 K/V;
- SYCL graph on with cache size 8;
- exact active contexts `0, 2048, 4096, 8192, 16384, 24576, 32768`.

The machine-readable preregistration is
[`../data/2026-08-25-qwen36-q8-f16-tp1-sycl-graph-exact-depth-prereg.json`](../data/2026-08-25-qwen36-q8-f16-tp1-sycl-graph-exact-depth-prereg.json).
The inert runner is
[`../scripts/run-20260825-qwen36-q8-f16-tp1-sycl-graph-exact-depth-r1.py`](../scripts/run-20260825-qwen36-q8-f16-tp1-sycl-graph-exact-depth-r1.py).

## Why it cannot launch yet

The manifest intentionally contains placeholders for:

- the new graph-enabled `llama-bench` size and SHA-256;
- the exact `libggml-sycl` size and SHA-256;
- the complete 32-row effective DSO closure;
- the frozen parent preregistration and runner hashes;
- the parent result, terminal-receipt, and parity-receipt hashes.

Default invocation only prints an inert plan. `--check` and `--execute` reject
the packet while any placeholder remains. `--execute` also requires the exact
acknowledgement and a clean pushed `main`; it is not a back door around the
parent.

The parent must finish as `passed-parent-sentinel-only`, with cleanup, the same
new binary within its own graph-off/on comparison, exact output bytes, and
bounded mechanism authority. Its exact graph backend must match this curve's
backend. The historical dirty-binary R5 sentinel cannot fill these placeholders.

## Per-cell graph evidence

Positive aggregate counters are insufficient for this curve. The runner uses
one isolated five-repetition `llama-bench` process per context and requires an
accepted graph summary from every process. Every context must independently
show:

- positive requested, recorded, created, cache-hit, direct-replay, and replayed
  counts;
- replayed equals requested;
- zero compatibility rejection, device unsupported, and cache-full counts;
- device 0 and cache limit 8.

The seven raw JSON arrays are retained separately, then combined for the exact
depth parser. The per-context stderr hashes and summaries are preserved in
`graph-evidence.json` and in the parser metadata. A context without positive
capture and replay fills no cell. Graph estimates are forbidden.

## Claim boundary

A complete run can create seven raw-engine graph-on performance cells only. It
does not authorize site publication, a quality claim, a record, or a submission.
The exact graph tuple still needs its service quality battery before publication.

The existing graph-off series
`q36-unsloth-q8-tp1-kv-f16-context` is protected evidence. This graph-on packet
adds a separate selector and must never overwrite, lower, relabel, or replace
any graph-off value or any featured speed.
