# Own runtime, IQ3 line: first bit-exact two-card decode, and why it is slow (2026-10-11, 14:24–16:10 UTC)

The owner's instruction at 14:24 UTC was to continue on the GPUs once the fault's cause
was fixed if it was on our side. Device work resumed on the same boot after ending the
parked process and one passing four-card health probe
([incident record](../experiments/own-xpu-runtime/stage2/packet16-decode/evidence/20261011-w2x-two-card-fault/README.md)).
Every window below finished with a clean kernel log.

## Exactness: proven on the cards

| Check | Result |
| --- | --- |
| Packet 17 W-B, one card, two fresh owners | our `exp` and `log` equal the host for all 2^32 inputs each; 72 kernel fixtures: parallel == reference on card, reference on card == reference on host, owners identical |
| Packet 18 W1, one card, full model | 384/384 layer fixtures and 8/8 tokens equal to the v2 CPU oracle (run twice, on two builds) |
| Packet 18 W2, two cards, 64 tokens, frozen GEMV variants | 384/384 layers, 64/64 tokens |
| Packet 18 W3, two cards, 64 tokens, R5 GEMV variants | 384/384 layers, 64/64 tokens |

The cause of the earlier mismatch was the build: Intel's correctly-rounded divide and
square-root options must be on the link command, and the card's own `exp`/`log` are not
the host library's. Identity v2 (deterministic `exp`/`log`, host RoPE table, precise
divide/sqrt) is now reproduced bit for bit by one card and by two.

## Two cards: the morning fault did not recur

The two-card canary (100 verified cross-card round trips, the real per-token crossing
sequence) and both 64-token decodes ran on the same pair, `0000:43:00.0` +
`0000:47:00.0`, that faulted at 09:09 UTC. What changed: both cards are drained on the
host at every crossing, no event of one card's queue is passed to the other, and the
NEO key is not set. Which of the two removed things caused the fault is still unknown.
Without the key the process keeps a host-memory shadow of its device buffers
(GPUActive 53.5 GB with 53.3 GB on the cards), as predicted; MemAvailable stayed at 65 GB.

## Speed: 2.46 and 3.15 tok/s, and most of the time is our own stopwatch

| Run | tok/s (tokens 2–64, wall) | ms per token | GEMV device span | non-GEMV device span | launches | neither |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| W2, frozen GEMV | **2.46** | 406.8 | 92.2 | 46.8 | 2,445 | about 268 |
| W3, R5 GEMV | **3.15** | 315.2 | 61.0 | 47.5 | 2,181 | about 207 |

The reference is 28.49 tok/s. The "neither" column is not the cost of issuing kernels:
the [launch micro-benchmark](../experiments/own-xpu-runtime/stage2/packet20-launch/receipts-card3-20261011-attempt-a/README.md)
measured 3.4–5 µs per launch on the card (9.5 µs with a host wait after each), so 2,445
launches should cost about 10 ms. It is the timing instrumentation: at every drain the
runtime asks the driver for the start and end time of the first and last event of every
launch, about 9,800 queries per token, roughly 27 µs each. The device spans are also
inflated, since each spans the gaps between its kernels.

Earlier projections in this lane (14–16 tok/s, then 5–6, then "30 µs per launch")
were built on those distorted spans. They are withdrawn; the table above is what was
measured.

## Next

1. Packet 23 (Codex, in progress): the fused launch schedule of packet 21 (876 launches)
   with timing reduced to one wall-clock reading per token and profiling off, plus the
   cheaper host submission path. First run that measures the runtime rather than its
   stopwatch.
2. Then the real device time shows what to attack: GEMV variants (expert block at 11%
   of the memory roofline), remaining non-GEMV kernels, and the two-card split inside a
   layer (packet 14's exchanges must be merged first).
3. Command-graph replay (packet 22, stopped at its last CPU gate to free host memory)
   only if issuing still matters after step 1.

## Process notes

- The health probe passed but its Python crashed while exiting; I had sourced oneAPI
  2026.0 around a torch 2.14 venv. No GPU fault line.
- The micro-benchmark and the first canary each stopped on a bug of their own after
  their device work (a profiling query on a queue without profiling; a SYCL object
  outliving the owner's context release). Both processes were idle and were ended by
  PID with a clean kernel log; both bugs are fixed or scoped.
- Packet 18's windows accept only a closed list of environment variables, so they run
  with the oneAPI library path alone, not under `setvars`.
- I started W3 96 s after W2 ended instead of waiting the usual five minutes. Nothing
  happened; noted so the gap is not read as optional.

## Correction, 17:11 UTC: the slow part was a linear scan, not the timing queries

The "neither" column above is not the timing instrumentation. Removing the per-launch
profiling queries in a scratch build changed 315 ms to 300 ms. Phase timers then showed
320 ms per token inside the host's submission loop and 3.4 ms waiting on the cards; a
sampling profile put 83% of the host time in `tp2::Context::location`, which found the
owning card of every kernel pointer by walking all allocations from the start. With an
ordered lookup the same run takes **83.1 ms per token, 11.89 tok/s**, still exact
([evidence](../experiments/own-xpu-runtime/stage2/packet18-decode-v2/evidence/20261011-host-bottleneck-location-scan/README.md)).
I had stated the timing-query explanation as a finding without testing it; the A/B took
three minutes.

GPU time per token by kind of kernel was then measured on cards 0+1 (same file, run
r5e): the largest items are the router softmax/rank (9.8 ms), expert gate/up (8.5 ms),
the two combine+norm steps (7.5 and 7.4 ms), expert down (6.2 ms) and gather (3.8 ms).

## Evening: 12.08, then 17.85 tok/s, and a line that had to be abandoned (18:30–22:30 UTC)

- **The fused line was wrong.** Packets 21, 23 and 24 replaced the per-format GEMV
  kernels by one generic kernel that reads descriptor and pointer tables on the card and
  switches on the format at run time, to cut launches from 2,181 to 876. On the cards it
  is bit-exact (packet 23: 64/64 tokens, 384/384 layers) and 50–100 times slower per
  launch: gdn.qkv 8.8 ms against 0.10 ms, logits 129 ms against 2.1 ms; two-card decode
  4,445 ms per token. I first blamed a per-launch parameter copy, then the timing run on
  the card showed the kernels themselves
  ([measurement](../experiments/own-xpu-runtime/stage2/packet24-kernels/evidence/20261011-k2-c0-generic-kernels-slow/README.md)).
  The design rested on my "30 µs per launch"; a launch costs 3.4–5 µs.
- **Packet 26, the corrected line:** packet 18's specialised kernels, the ordered
  lookup and a leaner host path, new specialised non-GEMV kernels behind a per-class
  dispatch table, and a timing run on the card that picks the faster exact kernel per
  class. Sealed control (packet 18 kernels): 12.08 tok/s, host issue 10.4 ms, 70.6 ms
  waiting on the cards. With the measured selection: **17.85 tok/s** (55.4 ms per token),
  exact, repeated on the other card pair at 17.81 with identical tokens and layer hashes
  ([receipts](../experiments/own-xpu-runtime/stage2/packet26-specialised/receipts-cards01-20261011-native-w2m/README.md)).
  The winners: route+gather 286 → 67 µs per launch, the two combine+norm steps 179 → 17,
  gather 82 → 23, norms 25 → 8. Six new kernels were slower than the old ones and were
  not adopted.
- **Large GEMV candidates (packet 25)** are exact but only 5–20% faster than the
  runtime's own kernels; the harness baseline that made them look 2–4× faster was a
  slower kernel than the one the runtime uses.
- **Where the time is now:** 53.5 ms of GPU work per token: routed experts 14.8 ms,
  about 11 ms in 720 small GEMV launches, gdn.qkv 3.6, route 3.3, attention projections
  3.2, QSA attention 3.2. The reference needs 35 ms. Packet 27 goes after the small
  GEMVs, route, QSA attention and the per-weight work in the large GEMVs.

Process notes for the evening: the packet 23/24/26 device programs each failed once on
something the CPU gates could not see (a kernel-argument limit of 2,048 bytes on the
card, a missing success return in renamed entry functions, an argument check that only
existed in device-only code, a priority rule that contradicted itself). Each was a clean
exit or an idle parked process; none logged a GPU fault. Kernel log clean since 14:26.
