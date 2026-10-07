# 101c performance: use a second sampler worker next

The next useful lever is **two sampler workers, batch one, at the same 640×384
shape and arithmetic**. The completed single-worker run is dominated by sampling:
its ten emitted clips took a mean 2.878 seconds each on the sampler worker, almost
the same as the 2.870-second completion interval. Decoder work is already spread
over two slots and its output is available well before the delayed emission.
This supports testing overlap before spending a campaign on host copies.

[Structured measurements and input SHA256 bindings](../data/resume-20261007/resolution101c-performance.json)
retain the exact run identity and receipt selection. This is a three-fixture,
serial-client screen, not a speed record, fresh-request latency claim, or broad
video-quality qualification. The native BF16 model, 25 frames, original 8+3
schedule, encoder window 64 and 23/25 split are unchanged. Six native references
formed three exact repeat pairs; three candidate and ten timed emissions matched
all four reference tensors. The optimized arithmetic therefore passes this
limited same-size gate, without qualifying unseen prompts or longer clips.

## What was measured

The ten scored emissions are timed requests 03–12, which emit clips
99901200–99901209. Sampler receipts 01–10 describe those same clip indices;
decoder receipts 03–12 describe them. Joining on emitted index avoids comparing
a request with the later clip it has just launched. Three fill requests are not
scored; un-emitted completed tails are not extra quality-qualified outputs.

| Observation | Mean | Scope |
| --- | ---: | --- |
| Server-success completion interval | 2.8702 s | Nine intervals between ten scored emissions |
| Sampler worker elapsed time | 2.8780 s | Ten matched clips, including worker bookkeeping |
| Sampling stage A | 1.7274 s | Eight-step phase wall span |
| Sampling stage B | 1.1122 s | Three-step phase wall span |
| Latent upsample phase | 0.0346 s | Same ten clips |
| Decoder worker elapsed time | 2.3613 s | Two rotating slots |
| Native decoder worker | 2.2948 s | Five clips on xpu:3 |
| Replica decoder worker | 2.4277 s | Five clips on xpu:2 |
| Decoder node on prompt thread | 0.0129 s | Collect/enqueue path, not decoder compute |
| Preview encode/save | 0.2121 s | Separate writer, ten matched clips |
| Gap from success to next execution start | 0.3387 s | Nine serial-client gaps |

The generated rate is **8.7101 frames/s**, computed as 25 divided by the mean
completion interval; its median interval is 2.802 seconds. Playback remains
24 fps. Mean server request duration for the ten emitting requests is 2.5271
seconds; this is pipeline request time, not latency from a new prompt to its own
video. Matched previews were finished a mean 3.295 seconds before emission,
reflecting the configured three-request pipeline delay.

The roughly 0.339-second client gaps are worth reducing eventually, but sampling
and decoding can continue across them. They are not 0.339 seconds of proven GPU
idleness. Likewise, sampler `xpu0_ms` and `xpu1_ms` record events spanning an
entire phase containing work and dependencies on both devices. They do not give
per-card active kernel time. `route_busy_ms` explicitly says tracing was disabled.
No GPU utilization percentage or measured per-card throughput ceiling follows
from this run.

## Memory and expected value

After capture, replica setup and freeze, physical free memory was
**7.63 / 12.34 / 9.74 / 14.74 GiB** on cards 0–3. The sampler cards lost only
0.496 / 0.434 GiB of physical free memory between the pre-capture admission
reading and post-freeze reading. That is a useful sizing hint, not an isolated
capture-allocation measure or a W2 peak bound. The same interval includes decoder
replica setup on card 2, so its 2.096-GiB change is not sampler growth.

During the thirteen timed requests, sampled allocator reserved maxima were
23.21 / 18.93 / 23.90 / 18.88 GiB. These are allocator observations, not physical
free memory or peak-live bounds. An added sampler worker shares weights but owns
static buffers/graphs and concurrent activations. Preserve the actual-memory
admission, resident-owner checks, unchanged load state, no-fallback guard and
post-capture floor when qualifying it. The existing W1 observations do not
preauthorize W2 allocation.

For prioritization only, perfect doubling of unchanged sampler-worker capacity
would imply 17.37 generated frames/s; two strictly alternating decoder slots at
the slower slot's current mean would imply 20.60 frames/s. **These are arithmetic
thought experiments, not achievable-speed forecasts, measured ceilings or results.**
The two sampler workers share cards, while decoders share cards with the encoder;
contention, transfer dependencies and host work can sharply reduce those numbers.
Even so, this lever can plausibly move more than a percent or two and deserves a
bounded exact-output screen. It cannot promise 24 generated frames/s at this shape.

Keep batch one, the same precision and the same step count. Qualify both workers'
complete graph chains and deterministic four-tensor outputs against the preserved
same-size native references. Compare W1 and W2 under the same client delivery
method before attributing a gain to worker overlap. Queue or delivery changes are
a separate lever; qualify them against W1 first or include a matched control.
Host copy instrumentation comes next only if the W2 receipts show it on the
critical path. No runtime or GPU action was performed for this analysis.
