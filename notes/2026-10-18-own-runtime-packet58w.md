# Packet58w — one-card overlap record chain, CPU preparation

Prepared on the four-card host on October 18, ahead of packet58v's device
bracket. No GPU job, service, queue entry, public submission, host setting or
parent packet was changed by this work. The current record remains
26.22859930943809 tok/s, `cmvdukc200064rf01lqsql9x8`.

The new packet copies packet58p's seven-window chain and reuses packet58v's
five binaries by hash. The native entry accepts `--cache-maintenance overlap`
without a bracket table, so no rebuild was needed. The fixed configuration is
one B70, target-only, tile16, zero-copy misses, host-pinned experts, an 18 GB
immutable device cache and context4096 BF16 KV. Packet49's
`iq3-p49-split32-v1` oracle remains authoritative through its binding and
shared reader. The template has zero symlinks; the copy inventory confirms
that none were flattened or lost.

The exact new service is `packet58-onecard-58w-a`; its fresh output is
`evidence/card0-58w-a`. The command embeds the recorded oneAPI library path.
Only PATH, LD_LIBRARY_PATH and OMP_NUM_THREADS enter Python, which may add its
automatic C.UTF-8 locale. Every window's actual startup path was exercised on
CPU, including the real environment/unit gates, read-only topology and host
admission, parser and native argument assembly. No native device exec occurred.
All seven current host admission snapshots passed; the fixture fallback in the
CPU harness was not used. Both queue and window entries reject the wrong unit
and an extra environment variable, for 28 negative checks.

All 120 Python tests pass. Five full-shape checks exercise the reused engine's
contexts 32 and 4096 and async queue mock. Five real native parser checks and
bad-mode refusals pass. The actual host oracle consumer replays 38 historical
58p requests, including retained layer bytes; those old outputs are not new
overlap quality evidence. K1's zero-copy/mixed/streamed bytes match. The maximum
native CPU child RSS was 348,807,168 bytes, below the 4 GiB ceiling. Full-shape
mocks reserve sparse virtual space, so they use an RSS check rather than a
4 GiB virtual-address cap. All runtime imports preserve resource limits, and
actual pre-exec getrlimit checks retain unlimited address space.

The copied default memory helper still returned the historical plan even
though window admission used the measured plan. The new copy corrects that
inconsistency. Every model window now requires 95,435,761,152 bytes available,
using the frozen packet58u module plus 58v's bounded async allowance. K1 still
requires 12 GiB. The 8 GiB reserve, 4 GiB shadow stop and complete native census
checks stay in place. Initial template-test mismatches are retained in
[the initial test log](../experiments/own-xpu-runtime/ops/packet58w-orchestration/initial-tests.log).
The drain clamp and teardown-before-reporting proof remain enforced.

The preparation seals 635 source/dependency files and five copied binaries.
Build size is 72,924,200 bytes. The passive plan reserves 2,952,790,016 bytes
of chain output; root had 33,201,844,224 bytes free at that check, leaving more
than the required 25 GB after the reservation. No new tracked file reaches
1 MiB. The inherited-literal audit checks twenty live chain files; remaining
58p/58m/58n/58r/58t references are classified historical provenance, CPU
negative controls, the binary's existing parser switch, or documentation.

Readiness reads the exact 58v runner paths under
`evidence/card0-async-a/{smoke,overlap}`. It rehashes complete native closures,
requires clean completed queues and the same build, and compares every token
again with packet49. The 12 × 64 smoke is mandatory. The complete 12 × 128
five-view bracket must have both overlap views at least 0.5% above each serial
control, with control drift at most 3%. Decimal comparisons preserve inclusive
boundaries. The queue repeats this verification at startup; saved flags cannot
bypass it. At the 17:52 UTC check, the smoke was complete and the bracket had
completed its two K1 windows but not its model window. `ready.json` correctly
remained false. The preparer did not launch those parent jobs.

The packet58s-derived submission tool is finished before the chain. It checks
all seven windows, native owners, cold requests, exact output and layer bytes,
then derives WS128's median of six class medians using 99 inter-token intervals.
It records major/minor process faults and zero new GPU fault lines only after
checking the journals. Notes state target-only, host-pinned experts, 18 GB cache,
zero-copy misses, tile16, overlap, BF16 KV and packet49. They remain below 2,000
characters and explicitly retain the 128-token scope,
`realistic_final_gate.passed=false`, and no strict512 claim. WS128x is exactness
only; a second fresh timing run is still missing. The predecessor ID comes from
the hash-pinned prepare-time ledger. Stale public-list wording comes from the
policy file. The shared submission CLI also checks the live ledger before any
later submission. Offline tests use synthetic evidence and forbid network.

Git pull refused because of unrelated dirty orchestration files. Fetch confirmed
HEAD equalled origin/main at the start. Only the new packet, its new orchestration
folder, this note and the current-state entry are included in the preparation
commit. The final readiness marker is written after that commit is pushed and
then committed separately; it binds that preparation commit and the full command
SHA-256. No device readiness or speed win is inferred from the marker.

- [Packet and reproduction](../experiments/own-xpu-runtime/stage2/packet58w-onecard-record/README.md)
- [Entry replay](../experiments/own-xpu-runtime/stage2/packet58w-onecard-record/evidence/argument-gate.json)
- [Build seal](../experiments/own-xpu-runtime/stage2/packet58w-onecard-record/build-receipt.json)
- [CPU closeout](../experiments/own-xpu-runtime/stage2/packet58w-onecard-record/CPU-PREPARATION-CLOSEOUT.md)
- [Final coordinator marker](../experiments/own-xpu-runtime/ops/packet58w-orchestration/READY-FOR-DEVICE.json)
