# Third sampler worker: decision pending packet 100b

At this review, corrected packet 100b is running its single 20/28, W2, B1,
shared-pool control. Its completed quality, timing, occupancy and memory results
are not yet available. No W3 implementation, runtime preparation or GPU request
was performed for this review. A successful 100b result must precede selecting
its source/layout as the next base; failed packet 100 is not qualification.

## Current evidence

The qualified [99b summary](../data/upstream-99b/two-way-w2-b1-p1-dxpu2-s256x256/summary.json)
reports 1.3156 seconds per clip (steady interval mean), 1.994 sampler jobs in
flight, and a 2.5384-second sampler-job median. Card 0 is busiest at 1.2217 CCS
seconds per clip, or 0.9286 utilization; cards 1–3 report 0.9697 / 0.8935 / 0.7890
CCS seconds per clip. Completely removing card 0's apparent idle gap would imply
only about 7.1% less time per clip, before additional contention. This is an
optimistic projection, not a measured W3 gain or a strict physical bound: engine
counters can include waits, and timing summaries use different statistics.

Historical negatives remain relevant:

- [Packet 97 results](2026-10-06-packet-97-results.md): two-way W3 B2 with the
  card-2 decoder took 0.935 seconds per clip versus W2 B2 at 0.927. Adding a
  third decoder was worse again at 0.959. These are different batch arithmetic
  and references, not proof of the B1 result, but argue against assuming that
  another worker improves throughput.
- [Packet 95 results](2026-10-04-host-ram-shadow-of-vram.md): W3 spread layouts
  were exact but slower than the two-card W2 control (1.387 / 1.470 versus
  1.358 seconds per clip). Two-card W3 B1 was not run because private graph
  pools did not fit its memory allowance. Shared pools subsequently changed
  that constraint; B1 two-card W3 remains a narrow unmeasured possibility.
  The earlier host-memory failure is historical evidence, not permission to
  change host settings.

## Go/no-go rule

Default: **do not proceed from 99b evidence alone**. First require complete
100b exact-reference qualification, healthy completion, valid freeze and
matching full run identity. Then assess the mean throughput and CCS/BCS evidence
together, not the paired-output interval median alone.

One W3 screen is worth considering only if a concrete estimate exceeds a 5%
time-per-clip improvement with margin. Prefer roughly 10% apparent capacity
remaining on the busiest sampler card (`CCS seconds per clip / mean interval`
at most about 0.90), sustained sampler occupancy near two, and evidence that
encoder starvation or decoder capacity does not explain the gap. These are
screening heuristics, not a speed guarantee. If the busiest card is already
around 0.95 utilization, the plausible gain is only 1–2%, or only a theoretical
5–7% ceiling remains before contention, stop this lever. Do not open a worker,
batch, topology or decoder grid.

Memory is a separate admission requirement. The
[99b freeze](../data/upstream-99b/two-way-w2-b1-p1-dxpu2-s256x256/sampler-capture-freeze-f99b-twowayw2b1p1dxpu2s256x256-freeze.json)
has about 7.534 / 12.319 / 9.741 / 14.548 GiB free on cards 0–3. Its
[second-worker calibration](../data/upstream-99b/two-way-w2-b1-p1-dxpu2-s256x256/pool-calibration.json)
measured only 0.2664 / 0.2281 GiB incremental use on cards 0/1; do not treat
that measurement as a W3 upper bound. The conservative private-pool charge for
an additional 20/28 worker is 2.50 / 3.36 GiB. Applying the existing conservative
99b-to-100b card-1 debit of 3.16 GiB, with no card-0 credit, would leave about
5.034 / 5.799 GiB on cards 0/1 after that extra worker. This supports plausibility,
not admission. Require the actual successful 100b freeze and a fresh live check
before the third capture, retaining the 2 GiB floor and decoder probe reserve.
No first-worker 100b receipt was available during the bounded initial review.
Do not change power, swap or page-cache settings to make W3 fit.

## Minimal successor changes, only if the decision is go

The current source already allows 1–4 sampler workers and dynamically checks
capture coverage and chains for the worker identities. No numerical-source
change is indicated. The existing graph
`graphs/graph-capture-all48-pipe-samp2-tsh-rep-wlean-s3.json` differs from the W2
timed graph only in node 428's sampler depth, 2 to 3. Decoder depth remains 2.
The `range(2)` stream loops address two sampler devices, not two workers; retain
them.

A separate immutable successor would need:

- A W3-only launcher environment, run name and manifest control identity,
  retaining the exact parent source, process-local RoPE compatibility, health,
  fault-halt, progress-lock, file-limit and storage gates.
- A runner restricted to the selected layout, W3 B1, shared pool and card-2
  decoder, with a new packet/output prefix and explicitly disjoint index range
  below the existing 100,000,000 ceiling. Its serial capture loop already
  accommodates three workers; self-check prompts become `WORKERS + 4 = 7`.
- A new admission helper accepting the actual successor's W3 identity, retaining
  the successful W2 parent as the qualification/memory basis rather than
  relabeling it W3. The current calibration parser hardcodes last worker index
  1; a W3 run uses index 2. Check live capacity before each additional capture.
- The same exact w93c reference set and complete context/ownership/chain gates.
  At 120 timed prompts, sampler depth 3 plus decoder depth 2 yields **115 timed
  clips**, rather than W2's 116. The placement probe still checks 10 clips:
  **125 exact clips is the W3 probe-plus-timed target**, not 126. Three workers
  require all three worker capture identities and six card/worker chain checks.

Do not prepare or launch that successor until the actual 100b evidence satisfies
both the performance rationale and memory admission above.
