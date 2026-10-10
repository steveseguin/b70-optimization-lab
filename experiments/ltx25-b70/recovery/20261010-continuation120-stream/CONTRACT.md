# Packet 120 continuation contract

Parent is sealed119, manifest
`d4b99d333f8193fc74041290b3cc3ebc7309b73836323997d14271a9aa246890`.
The [119 contract](../20261010-continuation119-stream/CONTRACT.md) remains binding
except for the changes here. [Design and evidence](../../notes/2026-10-10-continuation120-stream-design.md).
This is a CPU-built candidate, not an XPU-qualified result.

## Identity

Packet id120; prefix `stream120-`; comparison `stream-candidate-120-v1`;
qualification clip base12000000. The 132 numerical contracts/ids stay119's.
The plan binds renamed fixed graphs and launch-only settings. Frame49/97/121,
all anchor kinds, resets, strict predecessor hashes, storage limits and existing
latches remain. New display placement is restricted to121/frame/cone/eager-display.

Plan SHA256: `585d6da602b87cc3f8d1440a19255c91b458f326efb2b1d2e97d6cc752072031`.

## Launch-only option

`LTX_DISPLAY_DEVICE=xpu:3|xpu:2` (default/off **xpu:3**). The status and
`server_options` add `display_device` to119's five fields: snapshot_mode,
decoder_graph_pool_cap_bytes, display_schedule, anchor_read_ahead and
snapshot_schedule. Status, receipts and qualification must all agree with the
client's `--expect-display-device`. Decode records bind actual display placement
and the replica proof. Eager control output remains xpu:3; all other selected
replica output is xpu:2. Selecting xpu:2 appends `-ddxpu2` to the run name.
The older `LTX_DECODE_REPLICA_DEVICE=xpu:2` compatibility variable does not select
this option; it retains the inherited meaning.

Off uses119's native display path. New placement copies decoder/statistics before
graph/cone installation, checks tensor bytes, excludes encoder, bypasses model
manager eviction and adds no graph pool. One decode thread and the native
arithmetic order remain. xpu:3 retains cone, encoder and native VAE ownership.

Before install require actual free xpu:2 >= copied bytes +4GiB transient
reservation +2GiB floor. Before decode require4GiB+2GiB; afterwards require2GiB.
Check immutable replica tensor facts/residence and record budgets. Record allocated,
reserved and unreset device-global peak allocation before/after. Refuse observed
peak-over-start or reserved growth above4GiB; historical peaks may conservatively
refuse a run. These counters do not prove continuous physical-free headroom. This reservation
is evidence-based planning, not a proven transient bound. Full runtime peaks are
an outstanding qualification item. No native OOM fallback, tiling, automatic
restart or alternative-device fallback is admitted.

## Exactness and failure

Every chunk of each of the three qualification chains compares full xpu:2 frames
against an uncached eager xpu:3 decode of the same latent. Shape, dtype, SHA256 and
byte identity must agree. Eager-chain output remains the original xpu:3 control;
the replica is additionally checked. Existing across-chain latent/image/waveform/
anchor checks remain. Every live cone anchor must equal the last xpu:2 display
frame. No hash-only sampling of selected qualification frames substitutes for
full-image equality.

Any replica mismatch, unsupported policy, changed residence or memory refusal
halts and writes `display-replica-120-refused.json`; new launches selecting the
replica refuse that latch. Existing graph/cone/precompute/snapshot latches remain
shared and are never cleared by the builder. Missing or inconsistent proof fails
qualification and client admission. CPU fake passes are not cross-card proof.

## Recommended expectations

```text
--packet 120 --expect-frames 121 --expect-placement two-way20-28
--expect-text-reuse 1 --expect-anchor frame --expect-decoder-graph 1
--expect-anchor-decode cone --expect-bencode-overlap 1 --expect-prep-ahead 1
--expect-snapshot-mode fingerprint --expect-pool-cap-gb 1.0
--expect-display-schedule eager-display --expect-anchor-read-ahead 0
--expect-snapshot-schedule full --expect-display-device xpu:2
```

Read-ahead is dropped from the proposed launch; its119 path is preserved for
explicit comparisons. No scheduling or snapshot reduction is newly introduced.
The matched receipts attribute119's loss to extra dual safety inspections, not
a slow upsampler or synchronous HTTP read-ahead. Full safety checks stay enabled.

## CPU preparation

`run_tests_120.py` runs the complete recovery suite with guarded children; render
device opens, signals and live-network addresses are blocked. The client suite
uses `stream/tests/run_cpu_suites.py` with the same device-open protection and
cooperative fake-child lifecycle. All use the fingerprinted `bin/python -B`,
OMP/MKL threads<=4, new temporary paths and no bytecode. The builder recursively
verifies sealed119 and its ancestors, copies into an exclusive new packet and
binds all changed sources while preserving predecessor bytes in provenance.
See [build receipt](../../data/resume-20261008/continuation120-build.json) for
exact counts and final manifest, and [launch reference](LAUNCH.md) for text only.
