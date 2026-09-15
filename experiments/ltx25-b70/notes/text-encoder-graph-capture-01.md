# Text encoder graph capture: 1.81 s -> 1.59 s, exact

*2026-09-15, packets 34-38. Landed on `graph-text`; 7 clips, all four raw
oracles bytewise equal on every one.*

## Result

| | control (graph arm) | graph-text | delta |
| --- | ---: | ---: | ---: |
| Text encode (node 364) | 1.810-1.872 s | **1.591-1.670 s** | **-0.23 s** |
| Sampler (344+368) | 1.945-1.997 s | 1.932-2.003 s | unchanged |
| Video decode (374) | 0.580-0.598 s | 0.523-0.542 s | -0.05 s |
| **Clip** | **4.745-4.947 s** | **4.485-4.585 s** | **-0.24 s** |

The decode gain is a side effect of the memory work below, not of the encoder.

## Why the encoder was the target

Text encoding was the largest single node in the clip, 38% of it, and it runs
the same 48 Gemma layers over the same sealed `[1, 1024]` prompt every time. A
Gemma layer holds 546 MB, so 48 layers should read in ~49 ms at the measured
537 GB/s roofline. They took 1.81 s -- **37x roofline**, against 2.2x for the
video transformer's blocks. Graph capture, the lever that gave 1.86x on the
sampler, had never been pointed at it.

Capture is per layer, not per stack: `Gemma4Transformer.forward` collects the
hidden state between layers because LTX consumes all 49 of them, so folding
layers into one graph would drop the collections.

## Three failures, each a real constraint

1. **The layer returns a KV pair even on a cacheless prefill.** Dropping it is
   exact only because its two consumers (gemma4.py:576-582 and 617-619) are both
   gated on `num_kv_shared_layers > 0`, which is 0 on the 12B, and
   `next_key_values` is returned only when a cache was passed in. `stack_of()`
   now asserts that contract rather than trusting it.
2. **The layers are on the CPU at gate time.** ComfyUI moves the encoder to its
   load device lazily, inside the encode. Resolving the device at install
   refused a perfectly capturable encoder; it is resolved at first call now, and
   re-checked on every call so a mid-run move is caught.
3. **Memory, which is the interesting one.** See below.

## The memory trap, and what it cost

The first working capture was **6.5x slower than eager** (1.81 -> 11.8 s) while
staying bitwise exact. The receipts, not the timings, explained it:

| | reserved on xpu:2 | text encode |
| --- | ---: | ---: |
| no capture | 27.58 GB | 1.81 s |
| 48 private pools | **59.17 GB** | 11.85 s |
| one shared pool, a stream per capture | 38.04 GB | 3.52 s |
| one shared pool, **one stream** | **27.03 GB** | **1.59 s** |

The card holds about 32.6 GB. Every `torch.xpu.graph(g)` without `pool=` takes
its own memory pool, so 48 captures reserved 59 GB, the allocator fell back to
paging, and every weight access crossed PCIe. An *eager* encode in the same
process degraded from 1.81 s to 3.6 s, which is what gave it away.

A shared pool alone was not enough: it still cost 0.22 GB per layer, 10.5 GB
over 48, against 0.06 GB per graph for the video blocks. The caching allocator
segregates free blocks **by stream**, and a fresh capture stream per graph stops
layer i+1 reusing what layer i freed, so the pool grew by a whole layer's
transients (~210 MB) every capture. One pool *and* one stream per device settles
it at roughly a single layer's peak -- the final reservation is lower than the
no-capture baseline, which is also why video decode got faster.

## What this measures, and the lever it exposes

With memory healthy, `measure()` replays every captured layer back-to-back:
**1447 ms for the 48 layers, 30.15 ms each.** The node costs 1.59 s, so ~145 ms
is the embedding, final norm, projection and tokenisation, and the rest is
kernel time.

So the encoder was **not** dispatch-bound. Graph capture took the ~0.23 s of
issue overhead that was there and the remaining 1.45 s is real GPU work. The
37x-above-roofline figure was never issue overhead; it is 452 GFLOP per layer
at 1024 tokens running at about **15 TFLOP/s**, where the video transformer's
blocks achieve roughly 55 TFLOP/s on the same hardware. That ~3.7x efficiency
gap, not the dispatch path, is the remaining prize in the text encoder, and it
is the next thing to attribute.
