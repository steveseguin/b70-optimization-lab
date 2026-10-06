# Packet 97 results: the second decode worker on card 2 (2026-10-06)

Packet `prepared-encoder-place-97` (manifest `6e232f72…`), runner `scripts/run-campaign-97.sh`, launch chain
`/home/steve/b70-host-diagnostics/run-97/chain-97.sh`. All servers: `NEOReadDebugKeys=1 EnableDeferBacking=0`,
shared graph pool on, two-card block layout (23/25), measurement client polling only the next 8 prompts.
Build: [packet 97 build](2026-10-05-packet-97-build.md). Previous results: [packet 96](2026-10-04-packet-96-results.md).

## In plain words

Until now the second decode worker (a copy of the video and audio decoders) sat on card 1, the busiest sampler
card, while card 2 was two-thirds idle. Packet 97 lets it sit on card 2. The decoder's output there is checked
byte for byte against the native decoder before any clip is accepted, and every clip is still checked against
its reference.

- **With today's references (batch 1): 1.308 s per clip, 126 of 126 exact.** The best figure that needs no
  ruling (was 1.348).
- **With batch 2 (two jobs): 0.927 s per clip, 27.0 fps equivalent, 133 of 133 exact** against the batch-2
  references. The best figure so far; it counts only if the owner accepts batch-2 clips.
- Three jobs instead of two gave nothing more (0.935). Card 0 is now the busiest at about 90 %.

## Runs

| Run | Batch | Jobs | Checked against | Clips | Exact | Seconds per clip (mean) | Compute seconds per clip, cards 0-3 |
| --- | ---: | ---: | --- | ---: | ---: | ---: | --- |
| `two-way-w2-b1-p1-dxpu2` | 1 | 2 | today's (`w93c`) | 126 | 126 | **1.308** | 1.21 / 0.96 / 0.88 / 0.84 |
| `two-way-w2-b2-p1-dxpu2` | 2 | 2 | batch-2 | 133 | 133 | **0.927** (27.0 fps) | 0.83 / 0.67 / 0.73 / 0.79 |
| `two-way-w3-b2-p1-dxpu2` | 2 | 3 | batch-2 | 131 | 131 | 0.935 (26.7 fps) | 0.86 / 0.68 / 0.76 / 0.82 |
| `two-way-w3-b2-p1-dxpu1xpu2` (three decode workers) | 2 | 3 | batch-2 | 131 | 131 | 0.959 (26.1 fps) | 0.85 / 0.90 / 0.56 / 0.57 |

- A third decode worker (replicas on cards 1 and 2) did not help: it puts decode work back on card 1, which
  rises to 0.90 s per clip, and the stream is slower (0.959). Two decode workers, native on card 3 and the
  replica on card 2, is the right placement for this layout.
- Each run's proof arms (other neighbours, swapped slots) passed 10/10 and 10/10 before the timed arm; the
  decode-replica probe on card 2 passed before the freeze in every run.
- The load is now spread 0.67-0.86 s per clip over the four cards; total compute is about 3.0 GPU-seconds per
  clip, so about 0.75 s per clip is the even-balance floor for this work. The gap from 0.93 to that is
  mostly the serial chain (a two-clip sampler job takes 3.6 s with two in flight) and uneven arrival.
- No GPU fault, no lockup. Zero of either on kernel 7.0.0-39 since the reboot (now about 36 hours).
