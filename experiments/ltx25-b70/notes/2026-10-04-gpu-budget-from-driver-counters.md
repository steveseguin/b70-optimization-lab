# The GPU budget, measured by the driver: 5.0-5.2 GPU-seconds per clip; the cards are 61-95 % busy (2026-10-04)

Campaign 91c: a repeat of 91b on the same packet (`prepared-encoder-decode-91b`,
manifest `c9ed69b7...`), server `encoder-server-decode-91c`, kernel 7.0.0-38,
`LTX_BUSY_WINDOWS=0`, runner `scripts/run-campaign-91c.sh` (warm 3 @215089,
probe, control 80 @215189, replica 120 @215289). Alongside it,
`scripts/sample-gpu-engine-busy.py` read the xe driver's per-client engine
counters from `/proc/<pid>/fdinfo` every two seconds. Receipts, the raw
samples and `engine-busy-summary.json` are in `data/decode-91c/`.

## Exactness and speed

| Arm | Clips exact | Interval median / mean |
| --- | ---: | ---: |
| control (decode on xpu:3) | 77/77 | 1.579 / 1.678 s |
| replica (decode on xpu:3 and xpu:1) | 116/116 | 1.520 / 1.605 s |

Probe `replica-exact`. No fault. The server did not exit on the runner's
SIGINT (see "Stop" below).

## Engine utilisation over each arm's generation window

Compute engine (`ccs`) and copy engine (`bcs`), busy time divided by wall
time, and busy seconds per clip. PCI order is assumed to be `xpu:0..3`.

| Card | Role | Control: compute | Control: copy | Replica: compute | Replica: copy |
| --- | --- | ---: | ---: | ---: | ---: |
| 0000:23 (xpu:0) | transformer first half, upsampler | 80.1 % (1.32 s/clip) | 65.2 % | 86.4 % (1.35) | 69.3 % |
| 0000:27 (xpu:1) | transformer shard (+ decode replica) | 61.1 % (1.01) | 53.1 % | 86.8 % (1.36) | 58.3 % |
| 0000:43 (xpu:2) | text encoder first half | 68.9 % (1.14) | 60.5 % | 73.0 % (1.14) | 64.2 % |
| 0000:47 (xpu:3) | text shard, VAEs | **95.0 %** (1.57) | 50.7 % | 84.3 % (1.32) | 51.4 % |
| Total compute per clip | | **5.04 GPU-s** | | **5.16 GPU-s** | |
| Perfectly balanced over four cards | | 1.26 s/clip | | 1.29 s/clip | |

Windows: control 122 s over 74 prompts (1.650 s/prompt), replica 178 s over
114 prompts (1.561 s/prompt), each starting at the sixth completed prompt.

## What this settles

1. **The pipeline is GPU-bound.** In the control placement xpu:3 is 95 % busy
   and sets the pace. This agrees with the `perf` profile (threads waiting on
   GPU events) and with the September capacity note, and it retires the
   packet 90c busy-window figure (41-45 %): those timers bracketed only the
   graph replays and missed the rest of each card's work.
2. **The decode replica does what it was built for**: it moves about 0.25 s
   per clip of compute from xpu:3 to xpu:1 and evens the cards out at
   73-87 %. The stream gains about 5 % (1.650 to 1.561 s per prompt in these
   windows), because the cards were already close to full.
3. **A clip costs about 5.1 GPU-seconds of compute.** Four cards at 100 % and
   perfectly balanced would give 1.26-1.29 s per clip (19.4-19.8 fps
   equivalent). Today's 1.56 s is 83 % of that. **24 fps needs 4.17 GPU-s per
   clip or less: at least 18 % of the compute has to go**, on top of perfect
   balance. Placement and process changes alone cannot reach it.
4. By role, approximately: sampler 2.3 GPU-s (xpu:0 + xpu:1), text encoding
   2.0 GPU-s (xpu:2 + the text share of xpu:3), decode 0.6-0.7 GPU-s. **Text
   encoding is about 40 % of the GPU work of a clip.**
5. The copy engine is busy 51-69 % of the time on every card, 0.8-1.1 s per
   clip each. It overlaps with compute, but copies that sit between two
   kernels are on the critical path. Nothing in the lane has budgeted them.

## Levers this points to

| Lever | What it could remove | Exactness risk | Status |
| --- | --- | --- | --- |
| Reuse the text encoding while the prompt is unchanged (continuous scene) | about 2.0 GPU-s per clip whenever the prompt repeats | none for the clip (same conditioning bytes); it is a different workload from "fresh prompt every clip" and must be reported as such | needs the user's ruling: PLAN.md lists it as a separate measure, the stop-hook wording says caching is cheating |
| Two independent two-card sampler pipelines once xpu:2/xpu:3 are free of the encoder | doubles sampler capacity | none (same graphs, other cards; cross-card exactness already shown for the VAE) | only possible with the lever above |
| Shorter text-encoder sequence (skip padded positions) | a large share of the 2.0 GPU-s if prompts are padded | high: changes GEMM shapes; needs the kernel invariance census and a masked-position proof | not investigated |
| Remove copies from the critical path | part of 0.8-1.1 s/clip/card of copy-engine time | low if copies are elided, not reordered | not investigated; needs attribution of what the copies are |
| Fused kernels (adaLN proven, norms) | 0.05 s proven, about 0.8 s candidate pool | low, per-kernel proof | as in the September notes |
| Decode in its own process (packet 92b) | nothing, if GPU-bound | - | built, low priority |

## Stop

The 91c server ignored the runner's SIGINT and stayed up, idle, for two and a
half hours. It had been launched from inside a shell script with `&`; a
non-interactive shell starts background commands with SIGINT ignored, and
Python then never installs its handler (`SigIgn` showed bit 2 set). Earlier
servers were launched directly and stopped normally. It was stopped cleanly
by restoring the handler through `gdb` (`signal.signal(SIGINT,
default_int_handler)` on the main thread) and sending one SIGINT; it exited
in 15 s with no GPU fault. Launch servers from scripts with
`env --default-signal=INT ...` so the handler is installed.
