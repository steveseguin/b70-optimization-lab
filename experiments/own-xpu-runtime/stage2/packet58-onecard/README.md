# Packet 58: one-card IQ3 engine

Target-only greedy decode on one selected B70, with all 48 target layers,
head, full BF16 KV and recurrent state on that card. This is a separate source
copy of packet56 with the unchanged `iq3-p49-split32-v1` arithmetic/oracle.
CPU qualification and both builds pass; device correctness, fit and speed are pending.
MTP is not included in this first milestone.

Experts are packed once into 48,627,712,000 bytes of pinned host memory.
An 18 decimal GB global LRU arena caches immutable expert weights. Every
production expert kernel resolves its weight pointer from a device table;
its arithmetic and summation order are unchanged. The cache starts empty,
persists across requests and never retains prompt, KV or response state.
[Independent route replay](CACHE-POLICY.md) supports testing global LRU but
does not predict the new engine's hit rate.

The zero-copy path reads misses directly from pinned host memory. After each
position completes, the host reads all routes, updates LRU, fills victim
slots on a dedicated copy-only queue and publishes the table behind fences.
The next position cannot see an old table with overwritten slots. These waits
are charged to timing; copy/compute overlap is not yet claimed. The streamed
fallback reads each layer's routes, copies missing experts before use and
executes the same expert kernels. Two fresh small K1 windows select the path.

- [Exact memory budget and admission](MEMORY.md).
- [CPU cache, lifetime and expert gates](CACHE-CPU-GATES.md).
- [Build commands and final CPU checks](CPU-BUILD.md).
- [CPU preparation closeout and remaining risks](CPU-PREPARATION-CLOSEOUT.md).
- [Independent cache/queue review](REVIEW-CACHE.md).
- [Coordinator window commands and durations](WINDOW.md).
- [One-GPU submission tooling and remaining scope gate](SUBMISSION.md).
- [Build and source retention](ARTIFACT-RETENTION.md).
- [Task notes](../../../../notes/2026-10-17-own-runtime-packet58.md).

Preparation is CPU-only, nice 19 on cores 4–15/20–31, Python -B, serial builds
under 1.5 GB, no model payload reads or large pins. Full pinning and every GPU
window belong to the coordinator. Blocks 54/56 must remain offline; margin
blocks are recorded. Sealed packets and packet57 remain untouched.

Credit Niko1221 / Strata for the hot-expert cache idea. This implementation is
independently written lab code; no external runtime source was imported.
