# Packet 58: one-card IQ3 engine

## Scope and starting state

Implement a separate packet from packet 56 for one-card target-only greedy
inference with an 18 GB expert LRU cache and exact host-backed misses.
The coordinator runs all GPU windows. CPU preparation runs on steve-b70s,
nice 19, cores 4–15/20–31. Full pinning, GPU measurements, MTP and full-model
exactness remain pending until their gates run.

Initial `git pull --rebase` refused because packet57-attribution had a dirty
README. It was not stashed, edited or committed by this task. `git fetch
origin main` then showed HEAD and origin/main identical (0 ahead, 0 behind).
Root free bytes were 13,573,136,384. This task has a 1.5 GB build ceiling;
no other job's artifacts may be removed. The current memory-fence contract
requires blocks 54/56 offline and records 53/55/57 as best-effort margins.

Parallel assignments cover host memory/window admission, cache and lifetime
CPU gates, and kernel/engine integration. Root owns integration, submission
preparation, review and focused commits. No GPU, service, sudo, model payload
read or host-setting change was made while writing this entry.

The submission ledger has only 2-card own-runtime records for this IQ3
model, no matching submitted 1-card record. Packet 58 uses a new lineage;
no two-card speed threshold is inherited. Strict 512-cap promotion remains
false for the requested 128-token comparison scope.

Credit Niko1221 / Strata for the hot-expert cache idea, without adopting any
external code. See the packet README for the implementation boundary.

## Memory and coordinator admission prepared

The census charges 48,627,712,000 B of pinned experts. The target-only device
bound is 26,409,219,600 B, including the 18 GB cache, expanded nonexpert
weights, full 4K BF16 KV/state, tables and workspace/transfer allowances.
This leaves 4,090,780,400 B beyond the required 1.5 GB reserve against the
conservative 32 GB card capacity. No draft is included.

Host admission requires 118,308,908,048 B available, including a full device
allocation shadow, file-backed nonexperts/lookup tables and an 8 GiB reserve.
The passive CPU snapshot passed; it is not permission to rely on that old
headroom at launch. Window admission checks it again just before starting.
No pinned allocation or model-payload read was made.

Six accounting and twelve window tests pass. Guards retain the failing-memory
54/56 contract, record margin blocks, use PF_EXITING-aware process sensors,
reject future fault-review boundaries, preserve faults and admit one chosen
card only. K1 gets two fresh processes. Full-model windows require both K1
receipts and the preceding successful gate. Each full-suite window has a
one-hour graceful watchdog, never an automatic retry. Commands are in
`experiments/own-xpu-runtime/stage2/packet58-onecard/WINDOW.md`.
