# 105: reversed order confirms the client gain; close this lever

The storage-change-only client was faster when it ran first: **12.6171 generated
frames/s**, versus **12.0981 frames/s** for the control running second, a
**4.29% throughput improvement**. The earlier control-first 104 comparison showed
6.20%. Both orders preserve exact output, so this small optimization has earned
its place; no further confirmation campaign is warranted for this lever. Move
next to sampler service and device-work attribution.

105 completed all 71 requests. Twenty native executions formed ten exact repeat
pairs, and ten candidate plus twenty timed emissions matched video latent, audio
latent, images and waveform tensors exactly. The native tensor inventories also
match 104 for all ten original fixtures. These are same-size 640×384, ten-fixture
claims, not unseen-prompt, longer-video or general visual-quality qualification.
The successful application was retained, with empty queues/tails/previews and no
fault or halt in the completion snapshot.

[Structured comparison and 185 source/evidence hashes](../data/resume-20261007/client105-performance.json)
include the 104 analysis, both source manifests, actual core/client source files,
105 receipts, policy readouts, matched stage metadata, event logs and completion
snapshots. This is metadata analysis; the coordinator owns independent full
tensor-proof reconstruction and lifecycle closeout.

## Same measurement, reversed order

Each row below uses nine server-success intervals between ten scored emissions,
with 25 generated frames per clip. Four fills and the interblock gap are excluded.
The 105 gap between the last fast emission and first control emission is 69.756
seconds, including proof/phase work and new fills; it is not a steady interval.
Playback remains 24 fps.

| Run and order | Control mean interval | Fast mean interval | Control generated FPS | Fast generated FPS | Fast throughput gain |
| --- | ---: | ---: | ---: | ---: | ---: |
| 104: control then fast | 2.076444s | 1.955222s | 12.039812 | 12.786270 | 6.20% |
| 105: fast then control | 2.066444s | 1.981444s | 12.098075 | 12.617058 | 4.29% |

105's fast median is 1.983 seconds versus control's 2.056 seconds. The mean
interval reduction is 85 milliseconds, or 4.11%. Descriptively pooling the two
equally sized blocks per policy gives mean intervals of 2.071444 versus 1.968333
seconds: 12.068873 versus 12.701101 generated FPS, a 5.24% gain. That pooling is
only a compact summary of these two pairs. It is not a new benchmark, confidence
interval, independent-trial replication count or public record. Intervals within
one pipeline run are correlated.

Fast's fourteen requests ran from 19:39:45.433 to 19:40:10.876 UTC; control's from
19:41:11.911 to 19:41:39.230 UTC. The coordinator reports quiet timing with agent
work paused, the same passive descriptor observer and no new driver-accounting
observer. The ordered reversal weakens the explanation that fast only benefited
from always running later. It cannot remove all process/runtime-age, warm-state,
storage or preceding-proof differences between these two short runs.

## The delivery mechanism repeats

Worker and receive means below cover ten scored clips. Gap and successor-server
means cover the nine matching completion intervals.

| 105 measurement | Control | Fast |
| --- | ---: | ---: |
| Between-request gap | 1.205667s | 0.351556s |
| Successor server execution span | 0.860778s | 1.629889s |
| Receive-span excess | 0.976461s | 0.065446s |
| Sampler prompt-node elapsed time | 0.011029s | 0.753723s |
| Matched sampler worker service | 3.893610s | 3.794710s |
| Matched decoder worker service | 2.851950s | 2.900140s |
| Decoder prompt-node elapsed time | 0.014778s | 0.012465s |
| Preview writer service | 0.208470s | 0.218260s |

The client gap falls by 0.854111 seconds while the successor server span grows
by 0.769111 seconds, leaving the measured 0.085-second completion gain. As in 104,
faster event draining lets the next request reach the sampler sooner, where it
waits for already-running work. The model's arithmetic and graph replay path
did not change. Small differences in worker service between arms are not an
isolated kernel-speed measurement; the primary repeated mechanism is reduced
client backlog and more exposed sampler waiting.

Sampler service is matched from producer+2 receipts, decoder service and prompt
elapsed time from producer+4, with emitted-index checks. Same-device phase clocks
span more than active kernels, and stage A/B are denoising stages using both
sampler cards. They cannot identify card imbalance. Receive-span excess is the
signed difference between local receipt start-to-success span and server
start-to-success span, not absolute network latency or removable GPU idle time.
The fast block's remaining delivery variation does not justify another client
micro-optimization campaign.

## Fewer saves with unchanged durability

Across fourteen requests, control made **1,282 checkpoint-triggered saves** and
zero skips. Fast made **667 saves and 705 skips across 1,372 checkpoints**:
51.38% of its checkpoint saves were avoided, and it performed 47.97% fewer such
saves than control. For the ten scored requests alone, the counts were 930 saves
versus 499 saves/509 skips. Scored event counts were 868 versus 948; progress
observations and therefore checkpoint counts change with timing.

These are checkpoint-save counters, not all durable writes. Explicit attempt,
prompt-ID and completion ledger saves and every event-log fsync remain. Every
checkpoint still performs source/process/fault checks, a fresh free-space probe
and reserve/allowance enforcement. Only unchanged storage fields permit a skip.
The second, control receipt reconstructs the first fast receipt before accepting
the result, and both bind each request's source-identified policy readout.

The sealed 105 manifest is
`1ff7bd5ab281dad1a19f8d01aaf8899505168f0606689ba43ccb23cc05311fad`.
Compared with sealed 104, client source changes only the schedule hash and
initialization's fast/control ordering. Every other client method, including
execution, checkpointing and persistence, is AST-identical. Actual graph-capture,
sampler, decoder, encoder pipeline and worker source bytes match. Changed source
files implement new plan identities and reversed phase/proof ordering, not a
numerical optimization. This makes the two-order comparison useful while keeping
its short repeated-workload scope explicit.

The descriptor snapshot has 462 observations, peak 2,663 and final 2,527, with no
alert. Scored fast observations range 2,587–2,663; control ranges 2,581–2,660.
This is finite-run reliability evidence, not leak freedom or long endurance.
Retain the client change and its exactness/durability controls; the next lever is
measuring sampler/device work accurately, with replay-window and transfer timing
kept separate from total device accounting.
