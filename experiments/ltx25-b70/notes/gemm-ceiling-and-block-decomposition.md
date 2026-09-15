# The B70 GEMM ceiling, and what the sampler is actually made of

*2026-09-15, offline probe on the idle xpu:3
([`scripts/gemm-peak-probe.py`](../scripts/gemm-peak-probe.py)) plus restore-time
attribution from `encoder-server-graph-capture-38`.*

## The hardware

| Measurement | Value |
| --- | ---: |
| Device copy roofline | **527.8 GB/s** |
| bf16 GEMM peak (4096^3, 8192^3) | **145-156 TFLOP/s** |

## The GEMMs on the critical path are already at their floor

The sampler runs 64 or 256 video tokens and **26 audio tokens**. At those token
counts a GEMM cannot be compute-bound; it is bound by reading its weights. So
the number that matters is the achieved weight-read rate against the 527.8 GB/s
copy roofline, not TFLOP/s:

| Shape (M,K,N) | Time | TFLOP/s | Weight read | vs roofline |
| --- | ---: | ---: | ---: | ---: |
| 256, 4096, 4096 | 0.071 ms | 121.1 | 473.0 GB/s | 90% |
| 256, 4096, 16384 | 0.266 ms | 129.0 | 503.8 GB/s | 95% |
| 256, 16384, 4096 | 0.387 ms | 88.9 | 347.2 GB/s | 66% |
| **26, 4096, 4096** | 0.054 ms | 16.1 | **619.8 GB/s** | **117%** |

The audio stream's GEMMs, the ones that looked pathological at 16 TFLOP/s, are
reading weights *faster than a plain device copy*. There is nothing to win
there. The 16 TFLOP/s was never a sign of inefficiency; at 26 tokens a GEMM is
a weight read with a little arithmetic attached.

This also explains why
[QKV fusion was neutral](graph-capture-21-results.md) and why the
[column partition was retired](column-parallel-retired.md): both attack GEMM
issue and GEMM shape, and the GEMMs are not the cost.

## So what is the cost?

Summing the isolated GEMM times for one video block's linear layers at 256
tokens gives roughly **1.2-1.4 ms**. The block measures **3.602 ms**. So about
**60% of a block is not GEMM at all** -- it is the six attentions, the RMS
norms, RoPE, the ada-scale/gate elementwise chains and the casts.

The same decomposition is far starker in the text encoder. Isolated GEMMs for
one Gemma layer's exact shapes at 1024 tokens:

| Projection | Shape | Time |
| --- | --- | ---: |
| q, o | 1024, 3840, 3840 | 0.307 ms each |
| k, v | 1024, 3840, 1920 | ~0.15 ms each |
| gate, up | 1024, 3840, 15360 | 0.819 ms each |
| down | 1024, 15360, 3840 | 1.156 ms |

That is about **3.7 ms of GEMM** in a layer that measures **30.15 ms**. Roughly
**26 ms per layer, 1.25 s per clip, is non-GEMM work** in the text encoder.

## What this redirects

Every remaining lossless lever has to attack non-GEMM kernels, because the GEMMs
are at the bandwidth roofline and their arithmetic may not change anyway --
a different GEMM algorithm reorders the reduction and breaks bytewise identity,
so GEMM "efficiency" was never an admissible lever under this lane's rules.

It also sharpens the audio-stream question. The audio stream costs 0.78-0.88 ms
per block (24-29%) on **26 tokens**, and its GEMMs are at the roofline, so its
cost is the *number* of small kernels around them, each paying a fixed launch
floor even inside a graph. That is consistent with
[elementwise/norm fusion measuring only 2.1%](graph-capture-19-results.md):
fusing a handful of ops out of ~150 changes little. Winning there needs a large
fraction of the kernel count collapsed, not a few.

## Limitation

The GEMM probe used synthetic bf16 weights of the checkpoint's shapes on an idle
card, and times isolated calls rather than in-model sequences; the block
decomposition subtracts those isolated times from an in-model measurement, so
"60% non-GEMM" is an estimate, not an attribution. Attributing the non-GEMM time
directly is the next step.
