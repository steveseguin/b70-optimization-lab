# 103: all ten fixtures exact; late completion drift needs a quiet-host control

The larger qualification passed: **20 native captures formed ten exact repeat
pairs; all ten candidate clips and all forty timed/continuity clips matched their
native references in video latent, audio latent, images and waveform**. This
extends W2's exact-output evidence to all ten original fixtures at 640×384. It
does not qualify unseen prompts, longer videos or general visual-quality claims.
The successful application was retained for controlled reuse.

The initial ten-emission screen measured **11.9968 generated frames/s** from nine
completion intervals averaging 2.0839 seconds. The subsequent thirty emissions
averaged **11.0316 generated frames/s** over 29 intervals. The 2.241-second interval
between blocks is excluded from both. These are separate short-screen and bounded
continuity measurements, not a combined speed headline or a long endurance claim.
Playback remains 24 fps.

[Structured measurements, forty matched emissions and source hashes](../data/resume-20261007/resolution103-performance.json)
bind 202 inputs, including the immutable source packets, receipts, event logs and
completion-log snapshots. Raw tensor proof reconstruction is separately owned by
the coordinator; this analysis compares the preserved verifier records.

## The late drift is in delivery, with an unresolved host-work confound

Each diagnostic pass below contains the original ten fixtures in the same order.
Completion and gap means use the nine intervals within that pass; worker/server
and receive-lag means cover its ten emissions. The three later pass rows help
locate drift; they do not replace the declared 29-interval continuity metric.

| Pass | Completion interval | Sampler worker | Decoder worker | Server request | Client receive-span excess | Between-request gap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 2.0839s | 3.7696s | 2.8106s | 0.8754s | 0.9850s | 1.2106s |
| 2 | 2.0591s | 3.8537s | 2.8045s | 0.8684s | 0.9853s | 1.2017s |
| 3 | 2.0851s | 3.9734s | 2.8414s | 0.8941s | 0.9673s | 1.1986s |
| 4 | 2.6606s | 3.7037s | 2.4282s | 0.7266s | 1.6272s | 1.9622s |

Completion intervals rise to roughly 2.63–3.05 seconds for the final eight emissions.
Client receive lag begins increasing around timed request 35 at 17:54:40 UTC, and
next-request gaps rise at request 36 around 17:54:43 UTC. Meanwhile the final-pass
sampler and decoder durations generally fall. This is evidence of a delivery
slowdown, not evidence that model kernels became slower. GPU worker activity can
continue during client gaps; the gaps are not a measurement of removable GPU idle
time. These phase timings also do not measure per-card kernel utilization.

**The host was not kept quiet during timing.** Git commit
`6bb69057432dfc9ce73c5fdfa95ad007afd86dd8` is timestamped 17:54:33 UTC, inside the
timed interval. The coordinator reported the accompanying push and concurrent
agent preparation. The 104 plan and schedule file mtimes are 17:54:11 UTC, also
inside timing. Its CPU-validation receipt was written at 17:57:12 UTC, after the
last timed emission, so that mtime alone cannot locate when its tests ran. These
observations establish concurrent host work as a confound; they do not prove it
caused the late jump.

Ledger growth is likewise unproven as the cause. The completed ledger is 11,829
bytes. Reconstructing its list lengths with final numeric-field widths gives
about 10.8 KiB near the jump, with smooth growth and no obvious 8/12/16 KiB boundary
there. These are approximate historical serialized sizes, not preserved allocation
or fsync measurements. The earlier synthetic persistence profile identifies a
plausible cost to optimize; it does not assign this run's slowdown to that cost.

## Source and quality controls

Both 102 and 103 use W2/B1, the same native BF16 model, 25 frames, 8+3 steps, encoder
window 64, 23/25 sampler split and decoder placement. Core sampling, decoding,
encoder pipeline, graph capture, conditioning and native VAE source bytes match.
The client submission, receive, checkpoint, durability and process-check method
ASTs are identical. 103 widens the plan from three fixtures to ten and increases
its native/candidate/timing counts and explicit disk allowance. Its larger pinned
plan and growing ledger may affect client cost even without an algorithm change.
The first three native tensor inventories match 102's oracle as well.

102's 12.2817 FPS three-fixture result remains useful context, but it is **not a
matched ten-fixture regression control**.103's new workload, separate process and
host activity prevent assigning their small timing difference to a model change.

## Memory, descriptors and next measurement

Post-freeze physical free memory was 7.20/11.99/9.74/14.74 GiB across cards 0–3.
These are point readings, not worst-case peak bounds. The passive FD snapshot
contains 562 observations: peak 2663 open descriptors, last 2528, with no alert.
During scored timing the 44 observations ranged 2544–2663. This finite snapshot
shows no descriptor-limit incident; it does not prove no leak or prolonged
stability. No power, memory, swap, driver or host restart change is implied.

The next comparison should hold the exact ten-fixture graphs and serial delivery
constant while testing the small unchanged-ledger-write proposal. **Suspend Git
operations, CPU tests, builds and agent file writes throughout both timed arms**;
retain only the same passive FD observer. Preserve all source/fault/process and
storage checks, explicit durable state transitions and every event-log fsync.
Measure the initial ten emissions of each arm under identical definitions. Keep
quality checks and an independent scope label for any continuity repetitions.
The present result supports the broader quality claim and identifies where to
measure next; it does not yet establish the cause or size of a client speed gain.
