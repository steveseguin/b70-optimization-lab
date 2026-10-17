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

## Engine and CPU gates

The single-card engine now holds all 48 target layers. It packs the full
expert bank into pinned host storage only inside an admitted native window,
with exact production byte layouts. All expert kernels use device pointer
tables for either host memory or the 18 GB device arena. The normal path reads
routes after each complete position; the streamed fallback reads each layer's
routes before use. Both use a dedicated copy-only queue with fenced table
publication. Fill waits are included in token latency; overlap is not claimed.

The cache begins empty and survives requests. A persistent suite loop clears
all mutable model state for each request. CPU comparison of a prompt after a
different prompt matches two fresh processes, including 40 retained files.
Request-reset work is included in TTFT. Cold load/pin time and cache fills are
recorded separately. There is no target prompt/KV/response reuse.

Eight fresh CPU cache/expert runs pass, including ASan/UBSan: randomized LRU
and lifetime fences, generation/ABA rejection, failed fills, and 36 complete
expert cases comparing hit/miss/mixed pointers to frozen production kernels.
The production-submit CPU adapter additionally passes 24 placement comparisons
across the three expert grid formats. GPU pointer accessibility and timings
remain unmeasured.

Independent review fixed an untracked DMA error path, required both queues
to drain before propagating errors, corrected pinned-byte reporting, tightened
prerequisite evidence coverage and prevented sibling-window substitution. K1
uses distinct timed host regions so GPU cache cannot masquerade as PCIe speed.
Both device K1 runs must match the CPU golden hash and one another.

A CPU replay of 403,168 retained packet55 route records supports testing global
LRU: 93.64% decode byte hit versus 92.46% for the fixed layer quotas. The replay
uses two-card/speculative observations and layer-by-layer admission, so neither
number is a measured packet58 hit rate. Fragmentation and empty persistent
placement are retained in CACHE-POLICY.md and its compact JSON.

The new offline submission helper reconstructs the primary 99-interval rate
and exactness from original receipts, using only a matching 1-GPU record floor.
It prepares a payload draft and hash-bound quality attestation after device
gates. It never posts. The 128-token scope has strict_512_gate_passed=false;
a two-card external exception is not silently reused for this new lineage.

MTP is deferred: the initial passive snapshot had only 1,953,649,648 B beyond
the conservative target-only host admission floor, less than the 3,354,364,214 B
draft residency alone would add to the reserved shadow. It needs a new admitted
budget and measured serial-draft benefit. No draft weights were read here.
