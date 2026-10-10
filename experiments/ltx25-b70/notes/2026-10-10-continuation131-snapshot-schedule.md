# Packet 131: the saved cost of the snapshot schedule option

The three snapshots before sampler A now cost about **0.12 seconds per chunk**
with the digest cache. `a-xpu3-sync` cannot remove that cost: it keeps every
inspection and only omits selected card barriers. The timed memory portion of
the two affected inspections totals **1.73–1.79 ms** in the matched windows.
The controller's earlier barriers have no separate timer. There is no measured
candidate speed here and no evidence for a 0.12-second schedule saving.

The owner decision is whether reduced synchronization is worth a separate
qualification for a likely small saving. Keep `full` in packet 131's recommended
configuration. No option was enabled and no live request or device operation
was performed. The current GC60 and digest-cache scopes also require `full`,
so changing only `LTX_SNAPSHOT_SCHEDULE` would be refused; a future combined
candidate needs an explicitly reviewed scope change and all its gates.

## Measurements

The [analysis script](../data/resume-20261008/continuation131-snapshot-analysis.py)
reads saved JSON only. Its [hash-bound result](../data/resume-20261008/continuation131-snapshot-evidence.json)
captures four client manifests once, matches receipts by server identity, and
records all source paths and hashes. No run or client directory is written.

Use the common window **stream sequences 10–49** in each session. Each contains
40 chunks, including the two mandatory dual-walk chunks 20 and 40; “ordinary”
has 38 chunks. Values below are milliseconds. Sums are computed within each
receipt before taking the median, not by adding component medians.

| Session | Request-before median | A-before median | A-after median | Three-snapshot median / mean, all 40 | Ordinary three-snapshot median | Ordinary A-pair memory median |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 127, GC60, digest1 | 41.235 | 38.864 | 37.358 | 120.782 / 139.911 | 118.060 | 1.789 |
| 128, idle, GC10, digest1 | 43.713 | 39.451 | 37.777 | 124.793 / 138.826 | 122.815 | 1.785 |
| 128, idle, GC60, digest1 | 42.216 | 39.149 | 39.688 | 122.071 / 135.001 | 121.702 | 1.729 |
| 129, idle, GC60, digest1 | 43.639 | 39.819 | 36.901 | 122.408 / 134.406 | 121.260 | 1.778 |

These are the first three on-chain snapshots, not the only snapshots in the
chain. B-before, B-after and request-after remain too. All six together have
matched-window medians **242.142 / 248.522 / 246.062 / 246.339 ms**, respectively.
The mandatory dual chunks have three-snapshot medians
**331.357 / 379.599 / 359.372 / 331.539 ms** and cannot use reduced barriers.

Complete captured prefixes provide 418 chunk receipts / 2,508 snapshots:

| Session | Captured sequence range | Chunk count | Three-snapshot median / mean (ms) | Ordinary / dual chunks |
| --- | --- | ---: | ---: | ---: |
| s127-live01 | 10–95 | 86 | 123.220 / 134.770 | 82 / 4 |
| s128-live01 | 10–69 | 60 | 121.370 / 140.159 | 57 / 3 |
| s128-gc60-live01 | 10–70 | 61 | 121.629 / 133.180 | 58 / 3 |
| s129-live01 | 10–220 | 211 | 118.972 / 133.100 | 200 / 11 |

The 129 prefix is frozen at this analysis read, not a claim about the live
session's final length. The last complete receipt counts for snapshot timing
even when its successor was not yet in the captured client manifest. Thus its
snapshot count is one greater than its consecutive-period count.

Ordinary 129 first-three component medians are 22.984 ms state, 82.008 ms
fresh tensor facts, 10.375 ms residence, and 2.854 ms memory. The option retains
the state/facts/residence work. The affected A-before/A-after pair itself costs
76.895 ms, of which just 1.778 ms is its measured memory section. That section
also retains xpu:3 synchronization and all four cards' counters, so even its
entire time is not removable.

## Exactly what changes

The inherited implementation is
[SnapshotInspector](../recovery/20261010-continuation130-stream/snapshot_fingerprint.py),
with the unmodified controller's initial barrier loop in
[CandidateSafety](../recovery/20261010-continuation130-stream/candidate_safety.py).
The native adapter's `_free()` performs a second barrier loop before readings.

On an ordinary streaming fingerprint chunk, only at `A-before` and `A-after`,
the option omits `synchronize(xpu:0)`, `synchronize(xpu:1)` and
`synchronize(xpu:2)` from both barrier loops. This removes **12 card barrier
calls per eligible chunk**, keeps both xpu:3 barriers at each site, and leaves
the request-before, B-before, B-after and request-after barriers unchanged.
The 1.73–1.79 ms memory figures time the inspector's loop and memory readings;
they do not include the controller's earlier loop. Receipts cannot isolate that
earlier loop's waits, so a total schedule saving cannot be measured from these
files alone.

No state, identity, route, ownership, placement, text, VAE binding, fault-flag,
tensor-fact, physical-free, allocation/peak, floor or byte-equality predicate is
dropped. All four cards' readings remain fresh. What is dropped is the guarantee
that queued work on cards 0/1/2 has finished at those two observation sites.
Consequently the memory readings are not a drained-device observation there,
and errors that surface on synchronization may surface at a later full barrier.
This is a synchronization/safety trade even though arithmetic is unchanged.

Setup, qualification, every twentieth streaming chunk, an unavailable ledger,
and a previously detected near-floor condition retain full barriers. A new
reading within 0.5 GiB of a pre-request floor immediately escalates that
snapshot to the full dual-walk path, then keeps the remainder of the request
full. The decode guard keeps its own barriers and always-dual residence checks.

The [inherited CPU tests](../recovery/20261010-continuation130-stream/test_snapshot_schedule.py)
exercise all-card readings/floors, unsynchronized-card residence changes,
near-floor escalation, qualification and periodic full barriers. They do not
measure native speed or prove that asynchronous readings have identical timing
semantics. Actual speed, error timing and combined-scope qualification remain
unclosed. Do not advertise a measured schedule improvement.

## Reproduction and limits

Run the analysis at nice 19 with `OMP_NUM_THREADS=2` and
`/home/steve/.venvs/ltx25-baseline/bin/python -B`. Its output is create-only;
replay elsewhere requires choosing a new output filename. It creates no `/tmp`
directory and imports no runtime or GPU library. Recorded receipt durations
are wall times measured by the original runtime, not new CPU microbenchmarks.
The saved file audit is CPU-only and does not adopt any schedule option.
