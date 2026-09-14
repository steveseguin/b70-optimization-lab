# Decoder cache confirmation: exact outputs, consistent decoder gain

2026-09-14. All18 balanced confirmation clips passed the original four-output
raw oracle, following11 passing screen clips on the same packet10 process.
The axis cache reduces the decoder event interval consistently. Whole-preview
timings remain variable, so this result qualifies a local decoder improvement,
not an overall speed promotion or the continuous24fps goal.

The preregistered schedule contains six triples, reversing original/cache order
once for each fixture. O means scoped original and C means axis-cache. For OCO,
the effect is C minus mean(O,O); for COC, mean(C,C) minus O. Negative means faster.

| Fixture and order | Preview effect | Decoder effect |
| --- | ---: | ---: |
| boat OCO | −98.998 ms | −72.102 ms |
| marble COC | +293.147 ms | −82.653 ms |
| bird OCO | −270.777 ms | −86.834 ms |
| bird COC | +19.276 ms | −76.329 ms |
| marble OCO | −87.905 ms | −83.810 ms |
| boat COC | +3.973 ms | −89.962 ms |

All six decoder effects favor the cache; median −83.231ms, mean −81.948ms.
Original decoder intervals span0.622135–0.660419s; cache0.548689–0.572938s.
Whole-preview effects split three wins/three losses: median −41.966ms, mean
−23.547ms. Fixture-mean preview effects are boat−47.512ms, marble+102.621ms,
bird−125.751ms. Original and cache preview medians are6.409214s and6.396357s.
Neither the best clip nor the original screening gain is promoted over these
balanced results. Client-event intervals include diagnostics and are not kernel
timings or lossless delivery latency. No new timing requests followed.

[Offline event attribution](../data/na-axis-confirm-timing-attribution-01.json)
binds37 saved input files and reproduces all six signed effects. The marble
COC preview loss includes+292.9ms in the encoder and+89.7ms in the first sampler,
despite−82.7ms decoding. The bird OCO preview gain includes−164.9ms encoder and
−48.5ms miscellaneous intervals, so it overstates the decoder contribution.
Submission-to-execution-start is only3.24–5.21ms and capture19.9–25.0ms.
Some small-node event intervals exceed100ms, and some terminal delays occur
after preview availability. These events cannot separate scheduling/delivery
delays from actual node work; they contain no GC marker. Do not attribute the
variation to GC or treat the full last-node interval as encoding cost.

Every new clip was actually compared against its protected original fixture
before deleting its redundant raw archive. The18 scoped decodes retain the same
24 ordered NA calls, VAE/component ownership, checkpoint config, BF16 placement,
kernel/causal/scale arguments, deterministic mode and full F32 output hashes.
Images, video latent, audio latent and waveform all match byte for byte. Across
the screen and confirmation,29/29 clips pass, including12 axis-cache clips.
The recipe remains256×256,25frames at24fps, native BF16,8+3 sampler steps and
original transformer dispatch. No prompt/output reuse or precision reduction.

Admission revalidated161 saved evidence files from the completed screen, its
exact11-request schedule, all four-output comparisons and nine scoped decoder
receipts. Prior raw tensors had already been pruned; the client explicitly
checks their durable comparison/hash receipts without pretending to reread
those deleted archives. The new clips still perform actual raw comparisons.
[Client and admission](na-axis-confirm-client-01.md).

Client exec31882 exited0. At16:57UTC, packet10 PID84255 (exec33936) remains idle
and healthy at`http://127.0.0.1:8188`, same computer boot, four render devices
owned only by that PID, queue empty and no kernel fault or FAULT latch. The
transformer and default NA dispatch remain original; the private axis-cache
mode stays available for further work. No application reload was needed for
the18 confirmation requests. Three confirmation previews remain (169,496bytes);
they are lossy review files, not the lossless oracle. Protected originals remain.

The [terminal export](../data/na-axis-confirm-01-export/summary.json) preserves
674 text files in a2,334,602-byte archive, SHA
`525b426c3b298e51d56639288ad7954dd197717ae3d2acd00e8ce6616feb4f15`.
It includes all new and admitted prior receipts, source closure, prior archive
identity, graph profiles, startup and postflight evidence. Root reviewed its
source;32 stdlib checks passed. Exporting does not rerun native qualification.
The final progress SHA is
`fa77ffc44624f4223d89966e7a3bb7cb91c5a9aae121920f3420c3030d7ed8ee`.
Packet/server identities are unchanged from the [screen](na-axis-screen-01-results.md).

Next: retain the exact decoder cache as a measured local improvement, attribute
the encoder/sampler variation from saved events, and pursue the remaining
encoder/transformer costs. Original node-event medians are about1.817s text
encoding and2.536s+1.004s for the two sampler stages; those dominate the remaining
clip latency. They are attribution intervals, not isolated kernel measurements.
The separate C++ boundary lane needs an explicit
CPU-only import policy before its guarded compile gate; its blocked import is
not a video fault and warrants no service action. No continuous streaming,
subsecond clip generation or overall speed record is claimed.
