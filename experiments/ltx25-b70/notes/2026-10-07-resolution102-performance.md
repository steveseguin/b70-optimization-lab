# 640×384: two workers improve the short screen by 41%

Packet 102 emitted the same ten scored clips at **12.2817 generated frames/s**,
versus 101c's 8.7101. Mean completion interval fell from 2.8702 to 2.0356 seconds;
median fell from 2.802 to 2.014. That is a **41.00% throughput increase**, or
29.08% shorter intervals, in this three-fixture serial-client screen. All three
candidate clips and ten timed clips matched the same-size native references in
all four tensors. This is a material result worth extending, not a record or
full-suite/endurance qualification. Playback remains 24 fps.

[Measurements and source/input hashes](../data/resume-20261007/resolution102-performance.json)
bind the two manifests, plans, identities, quality receipts, stage records and
client event logs. This analysis compared preserved proof records; it did not
rerun the tensor verifier or issue model requests.

## Comparison and controls

Both arms use nine server-success intervals between ten scored emissions, with
the same boat/marble/bird order, prompts, seeds, native BF16 model, 640×384 shape,
25 frames, original 8+3 steps, encoder window 64, 23/25 sampler layout and decoder
rotation. The six native captures and ten scored output tensor inventories also
match across arms. Sampler workers/depth changed from 1/1 to 2/2, with four fills
instead of three. Fills and completed un-emitted tails are excluded.

Core sampler, decoder, encoder pipeline, graph-capture, lean-conditioning,
pipeline-worker and native VAE source files are byte-identical. Torch/runtime,
model verification, source commit, GPU identities, boot and application file
limits match. Graphs differ only in run/index/qualification labels and sampler
depth. The client retains its serial delivery loop: its source changes concern
plan identity, phase counts and request budgets, not queueing. Setup/admission and
verification code changed for two workers, and success now retains the application.
These are separate processes with different run caches; this is not a randomized
same-process comparison or repeated significance test.

## Where the gain comes from

| Matched ten-clip observation | W1 | W2 |
| --- | ---: | ---: |
| Completion interval, mean | 2.8702 s | 2.0356 s |
| Sampler worker elapsed time | 2.8780 s | 3.7159 s |
| Decoder worker elapsed time | 2.3613 s | 2.8010 s |
| Sampler collect/enqueue node | 1.6960 s | 0.0228 s |
| Decoder collect/enqueue node | 0.0129 s | 0.0120 s |
| Preview encode/save | 0.2121 s | 0.2309 s |
| Success to next server execution start | 0.3387 s | 1.1480 s |

Individual clips take longer on their workers under concurrency, while completion
throughput improves because the work overlaps. Do not describe this as faster
per-clip kernels or lower fresh-prompt latency. W2 sampler stage A averages
2.4774 seconds and stage B 1.1678; upsampling is only 0.0312 seconds. Decoder slots
average 2.7614 seconds native and 2.8406 replica. Event spans spanning both sampler
cards are not per-card busy time, so they still establish no GPU utilization
percentage or reliable performance ceiling.

The client is now a meaningful next profiling target. Its received
execution-start-to-success span exceeds the server timestamps' span by a mean
**0.926 seconds**, versus 0.057 seconds for W1. W2 logs 85–89 events per scored
request. Before each receive, the unchanged client loop rechecks pinned sources
and evidence, checks storage and durably rewrites its state; each recorded event
also flushes and fsyncs. This is a concrete mechanism to measure, not proof that
all 1.148 seconds between requests is removable. GPU workers continue during
those gaps. A future bounded client change must retain source/fault/identity
checks, one-submit/no-retry semantics and durable evidence, and needs its own
matched delivery control before claiming additional speed.

## Memory and next action

Post-freeze physical free memory was **7.20 / 11.99 / 9.74 / 14.74 GiB** on cards
0–3. Sampled allocator reserved maxima during timing were
23.85 / 19.26 / 23.90 / 18.88 GiB. The readings support this completed screen;
they are not peak bounds or admission for larger shapes or more workers. This
analysis did not assess descriptor stability, long-run memory growth or kernel
fault history.

Keep the W2 direction. Next establish same-size references for all ten original
fixtures and compare every output, then run a bounded continuity extension before
optimizing client overhead. Preserve 101c as the matched short-screen control and
keep successful applications available under their admitted plans. New requests
still need a sealed admission path; retaining a process does not allow bypassing
its consumed request identities. The [follow-up design](2026-10-07-resolution-followup-design.md)
explains the required controlled application reload and future reuse options.
