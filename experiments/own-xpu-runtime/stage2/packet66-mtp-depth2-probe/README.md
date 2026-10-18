# Packet 66: discarded second-token draft probe

This CPU-prepared diagnostic copies packet61x. The coordinator runs the next
lane-B screen; no GPU was used during preparation. Acceptance and device
quality remain **unmeasured**. Packet61x's 51.03 tok/s record is unchanged.

The second pass reuses the official MTP layer with its own first-pass hidden
streams and the embedding of d1. It proposes d2 and discards it. It never sends
d2 to the controller, target verifier, target KV, or emitted-token stream.
The existing rank1 placement, 23/25 split, BF16 KV, draft prefix, target kernels,
dispatch and packet49 oracle remain in place.

The architectural idea is recursive reuse of Qwen's MTP layer, as specified in
the owner's packet66 brief. Credit the Qwen team for the MTP architecture.
The existing official draft provenance is revision
`bcd9f01ddc9cff2316eb84281bebcd5b058bddce`, described in
[packet36](../packet36-draft/README.md). This probe code was written in the lab;
no external runtime code was used.

Only [build_engine.py](build_engine.py), [cpu_gate.py](cpu_gate.py),
[seal_and_plan.py](seal_and_plan.py), and the [coordinator command](WINDOW.md)
are this packet's preparation/launch entry points. Other copied scripts retain
source dependencies and history; they are not a full-chain recipe for packet66.

## State and timing

The normal draft publishes d1 through the unchanged completion callback. The
callback only queues the diagnostic token. The next draft command runs the
probe before replacing the private first-pass streams. Reset/final dump flush
the last queued probe. This avoids recursive queue drains inside Engine::wait.
No target computation or callback runs during the second pass.

The probe snapshots every mutable draft allocation, including KV, pooled/raw
indexer data, intermediates, scratch, error/active/position and head workspace.
It uses one private device backup, capped at 32 MiB. After the second pass it
restores the bytes, host position/disabled flag, exact attention extent and
prepared attention commands. Immutable weights are shared. Target allocations
are never the destination of probe copies or kernels.

The existing memory admission remains at 30 GiB arena and 1.5 GB free. The
updated rank1 ledger reserves the full 32 MiB bound, leaving **55,809,888 bytes**
of arena headroom and **2,084,624,224 bytes** free. It supports only the requested
23/25, rank1, 4096-position screen configuration. See [memory audit](evidence/memory.json).

Each request's `rank1/depth2-probe.jsonl` records absolute d1/d2 token positions,
both guesses, rank, extra-pass wall time, summed existing compute-event GPU
time, snapshot/restore time, total probe time and snapshot bytes. Extra-pass
wall time includes its embedding read/upload, command issue, synchronization,
head readback and any attention recapture. GPU time is the sum of compute
events, excluding copies. Neither includes snapshot/restore. Probe timing is
diagnostic and perturbs overlap; the screen's decode speed is not a record.

## CPU gates

[The byte fixture](fixture/receipt.json) compares the candidate with a fixture
compiled against packet61x's original `mtp.hpp`. The reference gets only test
accessors; its draft computation is unchanged. No target model is run.

Each of two fresh candidate runs contains two reset-separated requests and
68 tiny synthetic draft steps. The check compares original d1 proposals,
all mutable draft/target-buffer state fingerprints at every step, and raw
final-state bytes. It covers sync/async execution, a completion callback
inside Engine::wait, deferred probes, pooled-KV boundaries, and extent 32→64.
The callback explicitly asserts that it submits no probe work. The discarded
d2 proposals also repeat exactly across the two runs.

The production-shape HC fixture exercises both target sides and independent
rows, then compares raw output to packet61x's retained fixture. All **136**
copied target C++/header files are byte-identical. The retained raw byte pair
also includes that target fixture. These are CPU proofs; the required next
device gate is all 12 prompts exact against packet49.

## Measuring conditional acceptance

[analyze.py](analyze.py) joins each d1 to the controller's actual `guess_rows`
entry by absolute token position. It requires that d1 was accepted and that
the next emitted token exists, then compares d2 with that token. Missed d1s
and end-of-request censored positions are reported separately. Missing,
duplicate or shifted probe rows refuse. The incident64 warm-up is excluded.

It reports the numerator/denominator and a2 per prompt, pooled within each
prompt class, pooled across the suite, and an equal-class mean. It also reports
per-prompt and cycle-weighted suite means of the extra-pass wall/GPU times.
All 12 exact, cache-zero screen receipts are required. After the screen it
automatically produces the measured-a2 and ±0.05 projection table.

## Cost and build decision

**Do not build a depth-2 engine yet.** The ≥10% bar has not been established.
The prepared screen supplies the missing acceptance and extra-pass timing.

There is a correction to the motivating premise: the actual
[native controller](native_controller.hpp) emits one token per pipeline
iteration. It overlaps two separately scheduled rank halves; it does not have
a batched M=2 target verifier. The older
[packet49 note](../packet49-integrate/README.md) states the same distinction.
The retained receipts contain no matched M=1→M=2 GDN increment. Consequently
there is no measured M=3 cost or defensible measured-a2 rate forecast yet.

[cost-model.json](cost-model.json) retains a useful, explicitly conditional
partial-cost model from existing receipts. Packet55 routes provide the extra
expert demand; packet57 supplies per-site time. Serial kernels read another
456.960 MB on rank0 and 492.800 MB on rank1 per added row. Hypothetical perfect
reuse across three observed adjacent rows reduces the newly unique payload
to 281.129 / 261.734 MB on average; no current kernel realizes that reuse.

Observed effective expert bandwidth is 153.227 / 150.665 GB/s. The GDN serial
work proxy is conv + recurrence + gated: 48.594 / 47.657 microseconds per layer,
18 GDN layers per rank. Thus extra expert reads plus this GDN work cost
3.857 / 4.129 ms per rank. Full rank overlap gives **4.129 ms**; serial rank
execution gives **7.986 ms**. These omit additional dense/QSA/HC/shared-expert,
rollback and scheduling costs. They are estimates, not M=3 measurements.

For the illustrative table, the old control's 1.90634 ms median draft wall
time is the extra-pass assumption. Its measured compute-event median is
1.641719 ms and is not substituted for wall time. Define an equivalent
depth1 cycle `C1 = 1000 × (1 + 0.787) / 51.03 = 35.018617 ms`; this is a
normalization of the record, not a measured engine cycle. Then
`rate = 1000 × (1 + 0.787 + 0.787 × a2) / (C1 + D2 + extra_verify)`.

| Assumed a2 (not measured) | Projected tok/s, full rank overlap | Change from 51.03 |
| ---: | ---: | ---: |
| 0.55 | 54.07 | +5.96% |
| 0.60 | 55.03 | +7.84% |
| 0.65 | 55.99 | +9.72% |

Even this optimistic partial model requires a2 ≥ **0.658** for +10%. The JSON
also retains the slower serial-rank sensitivity and three explicitly null rows
for measured a2 and ±0.05. Nothing here qualifies as a measured speed claim.

See [CPU closeout](CPU-CLOSEOUT.md), [retention/rebuild](RETENTION.md),
[do-not-repeat notes](DO-NOT-REPEAT.md), and
[task note](../../../../notes/2026-10-17-own-runtime-packet66.md).
