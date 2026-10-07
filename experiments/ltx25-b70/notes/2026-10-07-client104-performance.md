# 104: fewer redundant ledger writes, 6.20% higher throughput in one ordered pair

The unchanged-ledger policy measured **12.7863 generated frames/s**, versus
**12.0398 frames/s** for the control in the same loaded application: an observed
**6.20% throughput increase**, or **5.84% shorter completion intervals**. All ten
original fixtures in each timing block matched their native references exactly
in video latent, audio latent, images and waveform. The campaign also passed
twenty native captures forming ten repeat pairs and ten candidate emissions:
thirty optimized exact clips overall, among 71 completed requests including
setup and unscored fills. The application was retained successfully.

This is one fixed-order comparison, control then candidate, with nine completion
intervals per block. It supports the narrow optimization; it is not a precise
causal effect estimate, cold-request measurement, speed record, general visual
quality assessment or endurance result. Playback remains 24 fps.

[Structured measurements and 171 input hashes](../data/resume-20261007/client104-performance.json)
bind the sealed source, plan, receipts, policy readouts, stage metadata, event logs
and completion snapshots. This analysis reads small metadata only. Independent
full tensor-proof reconstruction is owned by the coordinator.

## What improved

The primary metric is 25 generated frames per clip divided by the mean of nine
server-success intervals between ten scored emissions. Each block has four
excluded fills. The 67.499-second separation between scored blocks includes
verification, phase handling and the next fills; it is excluded, not counted as
steady throughput.

| Measurement | Control: always save | Candidate: save on storage change |
| --- | ---: | ---: |
| Mean completion interval, nine intervals | 2.076444s | 1.955222s |
| Median completion interval | 2.014s | 1.977s |
| Generated frames/s | 12.039812 | 12.786270 |
| Between-request gap, nine intervals | 1.204444s | 0.287556s |
| Successor server execution span, same nine intervals | 0.872000s | 1.667667s |
| Client receive-span excess, ten emissions | 0.979092s | 0.004664s |
| Sampler prompt-node elapsed time, ten emissions | 0.011271s | 0.791556s |
| Matched sampler worker service, ten clips | 3.729050s | 3.759580s |
| Matched decoder worker service, ten clips | 2.831380s | 2.885240s |
| Preview writer service, ten clips | 0.213490s | 0.224720s |

The gap reduction is much larger than the final throughput gain because work
continues asynchronously while the client processes events. With less client
backlog, the next request reaches the sampler earlier and waits there for work
already in flight. The nine-interval arithmetic is explicit: a 0.916889-second
gap reduction is partly offset by a 0.795667-second increase in the successor's
server span, leaving a 0.121222-second interval reduction. Sampler prompt-node
elapsed time rises by roughly 0.78 seconds while matched sampler service stays
near 3.75 seconds. These observations support improved scheduling overlap, not
faster model kernels or removal of a second of GPU idle time per clip.

Worker timings are matched by emitted clip index: sampler request producer+2,
decoder and emitting request producer+4. They are elapsed service times and
include scheduling/transfer effects. The sampler phase clocks span both devices;
they are not per-card busy utilization. Decoder prompt-node time remains about
13 milliseconds. Mean sampler completion spacing falls from 2.1491 to 1.9041
seconds, and decoder completion spacing from 2.1115 to 1.9558 seconds. These are
supporting diagnostics, not replacements for the declared server-success metric.

Receive-span excess subtracts the server start-to-success span from the client's
elapsed interval between receiving those events. It is a signed difference in
spans, not an absolute one-way latency. Individual fast values range from
−32.7 to +20.3 milliseconds because start and success delivery offsets differ.
No clock-origin subtraction or inference of negative network latency is involved.

## Actual durability counters

Across all fourteen requests including fills, control performed **1,284
checkpoint-triggered ledger saves**, with zero skips. The candidate performed
**668 saves and 724 skips across 1,392 checkpoints**: 52.01% of its checkpoint
saves were omitted, and actual checkpoint saves were 47.98% fewer than control.
The ten scored requests alone recorded 934 saves/zero skips versus 501 saves/525
skips across 1,026 checkpoints.

These counters count only calls to `checkpoint()`, not every durable write.
Attempt, prompt-ID and completion ledger mutations still have explicit saves;
every event-log flush/fsync also remains. Every checkpoint still checks source,
process and fault identity, probes free space and enforces the allowance/reserve.
Only an unchanged pair of storage-accounting fields permits skipping a save.
Source-bound per-request readouts were written before durable completion and are
included in the verified receipts. Fast proof depends on a reconstructed control
receipt, rather than trusting its stored success flag.

The number of checkpoints is not identical across arms. The ten scored requests
produced 874 versus 964 recorded events; progress observations depend on timing.
Faster draining can change the event stream and checkpoint count. Therefore 724
skips cannot be multiplied by the earlier synthetic fsync cost to predict the
end-to-end gain. Those synthetic measurements were diagnostic, not measurements
of this timed run.

## Scope, ordering and reliability

Both arms used the same sealed packet, process, serial client, ten-fixture order,
640×384 output, two sampler workers, batch one and unchanged numerical settings.
The sealed runtime manifest is
`49892a00ece1cf4a7d84ce5d03e6a9c2290ffc3af9b2822ba4866e72cfa2e93a`.
The pinned plan declares the only permitted difference as redundant unchanged
client-ledger saves. Control's fourteen requests ran from 18:50:58.496 to
18:51:25.870 UTC; candidate's ran from 18:52:25.798 to 18:52:50.966 UTC.

The coordinator reports that root and agents performed no Git operations, CPU
tests or unrelated file writes during either timing arm after the last commit
around 18:39 UTC. The same passive descriptor observer and sparse journal reads
remained. This removes the known deliberate host-work confound from 103; it is
an operational report, not proof that every host task was idle. The later arm
still differs in runtime age, warmed state, ledger size and preceding proof
filesystem activity. A single ordered pair cannot separate those effects from
the policy effect, and its intervals are not independent trial repetitions.

Completion snapshots show empty execution queues, pipeline tails and preview
queues, with no fault/halt latched. The passive descriptor snapshot contains 506
observations, peak 2,662 and last 2,527, with no alert. Scored-block observations
range 2,567–2,662 for control and 2,585–2,661 for candidate. This establishes no
observed descriptor-limit incident during the finite run, not leak freedom or
long-term stability.

The next useful performance investigation is the sampler service/overlap path
now exposed by faster delivery. Retain the small durability-preserving change
as a promising scoped result; include a quiet reverse-order confirmation when a
necessary successor provides fresh, bounded admission. Do not extend or mutate
the consumed 104 plan merely to collect more favorable timing. Further client
micro-optimizations should justify their likely end-to-end value now that most
of the old delivery gap has become sampler waiting.
