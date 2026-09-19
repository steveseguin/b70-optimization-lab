# Packet 82 (server 82b): the NaN is gone, one finite wrong clip remains, 1.622 s/clip (2026-09-19)

Packet 82 ran the whole worker encode on the thread's per-device streams
(the fix for the all-NaN clip of servers 79b-81). Server 82 froze the host
at construction (21:20 UTC, tenth freeze, see the
[freeze note](2026-09-19-freeze-evidence-soft-lockup.md)); server 82b on the
next boot ran the campaign: warm (3 fills, exact), then 30 prompts on the
sharded two-clip arm (`pipe-samp2-tsh`, indices 91000-91029).

## Exactness

| Arm | Prompts | Distinct clips | Exact | Failure |
| --- | --- | --- | --- | --- |
| f82b-warm | 3 | 0 (fills) | 3/3 | none |
| f82b-tsh | 30 | 27 | 26/27 | prompt 05, clip 2 (bird) |

The bird clip at prompt 05 is finite (images in [0, 1], latents with
ordinary statistics) but differs from `speed-oracle-bird` in 100% of latent
elements (video latent max abs 3.5 against a reference std of 1.23) and
matches no other fixture reference (closest of 700 saved validation sets is
99.7% unequal). Bird at clips 12 and 22 was exact. The NaN mode of servers
79b-81 did not recur: the stream fix held. Evidence:
`output/validation/f82b-tsh-05/`.

## Speed (sharded arm, 26 steady intervals)

| | |
| --- | --- |
| Steady mean | 1.622 s/clip |
| p95 | 1.955 s |
| min / max | 1.085 / 2.129 s |
| Histogram (<1.3 / 1.3-1.7 / >1.7 s) | 1 / 16 / 9 |
| Wall per second of video | 1.557 s (15.4 fps equivalent) |
| Packet 74 reference | 1.607 s/clip (15.6 fps equivalent) |

No gain. The encoder shard installed (24 layers on xpu:3, 10.9 GB) and the
encoder is no longer the pacing stage: the pipeline node's sampler stage
took 3.26 s mean (1.80 min, 4.55 max) per clip with two clips in flight,
so the two-clip sampler delivers about 1.63 s/clip regardless of the
encoder. The decode stage averaged 1.21 s (0.28 min, 7.52 max, on xpu:3
beside the shard). Memory at prompt 05: xpu:0 28.1 GB reserved, xpu:1
28.1 GB, xpu:2 18.3 GB, xpu:3 17.0 GB.

## Cause of the residual mismatch

`ltx_graph_text_encoder.py` kept one graph memory pool per device
(`_POOLS[device]`) and one capture stream per device. Both encode workers
captured their 48 layer graphs into the same pool and replayed them
concurrently on their own streams. Sharing a pool is sound only when the
graphs replay in capture order on one stream: the allocator hands graph j
the blocks graph i freed during capture, so two threads' transients alias.
In the fill phase the two workers dispatch back to back (the failing
encode was the first issued after both threads finished capturing); once
the sampler paces them, overlaps are rare, which is why the same fixture
replayed exactly later and why every server lost exactly one early clip.
Packet 83 keys the pool and the capture stream by (device, thread).

## Defects found on the way

- Runner arm order: a `pipe-samp2` control arm cannot follow a sharded arm
  on one server (`only graph-shard arms may follow`), and its refusal
  latches the text encoder node. Runners 78-82 carried this order; 82b was
  stopped by it at 22:12 UTC. Runner 83 drops the control arm (packet 74
  is the control).
- `test-graph-capture-packet-negative.py` accepts the "pinned NA digest
  left stale" case on packets 82 and 83 alike: the checker does not verify
  that pin. Pre-existing; to fix in the checker, not in a runtime packet.
