# Packet119 continuation client contract

CPU-built successor of sealed118b, parent manifest
`248e762de49d21b02a4f95d3791dbd9da7504b731f1a88cb5a930a78448db1f1`.
The [118b contract](../20261009-continuation118b-stream/CONTRACT.md) remains the
baseline except for the explicit changes below. No GPU qualification follows
from this document. [Design and predictions](../../notes/2026-10-10-continuation119-stream-design.md).

## Identity and unchanged request form

Packet id is integer **119**; prefix `stream119-`; comparison mode
`stream-candidate-119-v1`; clip bases11900000/11901000. Existing wire schemas and
node classes remain118, as118b did. All132 numerical contracts and qualification
ids remain118b's; the new plan binds the renamed request graphs. New settings
are launch-only, never client-supplied request graph inputs. Frame/cone defaults,
49/97/121 geometries, sampler layout, text reuse, strict serial chain/reset,
predecessor hashes, bounded storage and old latch names remain binding.

## Three new launch settings

| Environment | Status/receipt option | Values (first is default/off) |
|---|---|---|
| LTX_DISPLAY_SCHEDULE | display_schedule | sampler-a, eager-display, sampler-b |
| LTX_ANCHOR_READ_AHEAD | anchor_read_ahead | 0, 1 |
| LTX_SNAPSHOT_SCHEDULE | snapshot_schedule | full, a-xpu3-sync |

`server_options` now contains exactly these three fields plus `snapshot_mode`
and `decoder_graph_pool_cap_bytes`. The client binds status, verdict and every
receipt to the same five values. Invalid settings refuse. Nondefault display
requires frame/cone; read-ahead requires frame; reduced barriers require
fingerprint. dg0 eager-display has no decode arithmetic effect. Snapshot
`a-xpu3-sync` is an owner-level safety trade, never the default.

All-off `sampler-a/0/full` preserves118b's call path. With any new option selected,
the run name appends `-ds<display>-ra<0|1>-ss<snapshot>` to the inherited119 name.
Names still collide deliberately across runs; the coordinator handles archives
under the existing no-reuse rules. A new packet never clears an old refusal latch.

Client expectations:

```text
--packet 119 --expect-frames 121 --expect-placement two-way20-28
--expect-text-reuse 1 --expect-anchor frame --expect-decoder-graph 1
--expect-anchor-decode cone --expect-bencode-overlap 1 --expect-prep-ahead 1
--expect-snapshot-mode fingerprint --expect-pool-cap-gb 1.0
--expect-display-schedule eager-display --expect-anchor-read-ahead 1
--expect-snapshot-schedule full
```

## Decode order and proof records

The cone still publishes the same checked frame before the next chunk. Optional
read-ahead follows receipt commit, then the inherited stage-A encode prep,
sampler-A go wait and stage-B precompute. `sampler-a` starts display here.
`eager-display` starts it here using uncached eager decode while the cone uses
the configured graph. `sampler-b` adds a source-run/hash-bound successor-B wait.
Both waits share a3-second deadline; expiration is recorded and display proceeds.
Gated qualification records `gated-no-wait` because waiting for a future request
would deadlock. Audio, output hashes, decode record and preview follow unchanged.

Decode `schedule` adds `display_schedule`, `display_release` (reason, event,
waited_s, released_ns), and optional `anchor_read_ahead` preparation metadata.
Receipt `anchor_read_source` is native, verified-read-ahead, native-miss or
native-file-changed (null for no frame consumer). Cached bytes remain immutable
and per-consumption SHA/file identity checks remain. No successor text is guessed.

Every display still checks its last frame byte-for-byte against the cone.
Graph qualification still compares full images to an uncached eager reference.
For eager-display dg1/cone, expected decoder signatures are pre-diffusion1 and
diff-step0, exactly one captured method; the unused diff step is neither captured
nor capped. Other display modes keep118b's two-method captured/capped gate.
Read-ahead qualification must actually hit on each anchored graph/repeat chunk.

## Snapshot schedule and live gate

All snapshots now record `synchronized` and `memory_cards`. Default full preserves
four-card barriers. Reduced barriers skip only xpu:0/1/2 completion barriers at
A-before/A-after on nondual stream chunks. All four fresh memory readings, floors,
residence/ownership checks, phase/route/fault checks and VAE bindings stay.
Request and B snapshots remain full; setup, qualification, every twentieth chunk
and near-floor escalation stay full. The design note maps P1–P8 and the precise
lost guarantee. No memory floor is reduced and no stale sample is substituted.

Qualification binds all receipt options and requires four-card snapshot scopes.
It does not exercise the asynchronous B wait or reduced stream barriers.
`stream_schedule_gate.py --run <completed-run> --first 10 --last 109`
reads saved files only and checks live proof records; `--control-run <matched-run>`
also checks image/waveform/anchor bytes by hash, with seeds/prompts bound.
Select interior chunks with a successor; terminal bound fallback is expected for
sampler-b but cannot count as a successful speed sample. Output hashes alone do
not establish throughput; measure actual submit timestamps separately.
