# What bounds a GEMV on a B70: a bounding study (coordinator, 2026-10-11 22:59–23:02 UTC, card 0)

Small SYCL programs, not part of the runtime and not an exactness gate. They run the
runtime's row structure (one sub-group of 32 lanes per row, 8 consecutive weights per
lane per 256-weight tile, sequential per-lane accumulation of `(scale*code)*x`, tree
over 32 lanes) with simple weight encodings at four of the model's shapes. GPU
execution time from event timestamps, median of 15. Variants that must agree produce
identical bytes.

**Use [bound-clean.cpp](bound-clean.cpp) and [its output](run-clean-card0.txt).** In the
first two programs (`bound.cpp`, `bound-mixed-v2.cpp`) the variant was a run-time value
inside one kernel, which let variants slow each other (the same variant measured 69 µs
in one build and 33 µs in the other); their absolute numbers are not to be quoted. In
the clean program every variant is its own compiled kernel.

| µs per launch | expert gate/up 12,800 × 2,560 | expert down 25,600 × 640 | gdn.qkv 10,240 × 2,560 | gdn.z 6,144 × 2,560 |
| --- | ---: | ---: | ---: | ---: |
| int8 codes × FP32 block scale, scale read once per 8 weights | 99.2 | 43.8 | **48.1** | **21.9** |
| the same, scale read for every weight | 479.8 | 124.7 | 209.0 | 96.5 |
| 4-bit codes + 16-entry table × scale, scale once per 8 | 190.5 | **71.2** | 79.2 | 38.3 |
| the same, scale per weight | 245.9 | 86.8 | 99.9 | 48.3 |
| float32 weights | 251.5 | 113.6 | 190.0 | 115.4 |
| **the runtime's kernel, measured in the model** | 178 (IQ2_S) | **130** (IQ4_NL) | **101** (expanded Q6) | **62** (expanded Q6) |

Four rows per work-group instead of one changes little (±10%).

Readings:

1. **The expanded dense kernels can be about twice as fast with the same arithmetic.**
   The runtime's expanded Q6 format is exactly "int8 code × FP32 scale per 16 weights".
   Reading the scale once for the lane's 8 weights instead of per weight gives 48 µs at
   the gdn.qkv shape and 22 µs at gdn.z, against 101 and 62 in the model, with
   bit-identical results between the two spellings. Worth about 7 ms per token across
   gdn.qkv, gdn.z, qsa.qgate, the attention projections and logits.
2. **The IQ4_NL expert-down kernel has the same headroom:** a 4-bit code with a
   16-entry table and the block scale read once per 8 weights takes 71 µs at that shape
   against 130. About 2.8 ms per token.
3. **IQ2_S expert gate/up is near its bound** as a packed format (a 4-bit-plus-table
   stand-in costs 164–190 µs; the runtime's kernel 178). Only an int8 expansion would
   halve it (99 µs), and that needs 3.2 times the bytes.
4. **Per-weight work that is not the product dominates:** fetching a scale per weight
   costs 2–5 times the whole kernel. 64-bit integer loads and shifts are slower than
   byte loads on this GPU (first program), so wide loads and register-held tables are
   the wrong direction. float32 weights are memory-bound and slow.

## Addendum, 23:14 UTC: the 2.5-bit grid format (expert gate/up)

[bound-grid.cpp](bound-grid.cpp) ([output](run-grid-card0.txt)) uses a stand-in for
IQ2_S: a 10-bit index per 8 weights into a 1,024-entry table of 8 magnitudes, 8 sign
bits, and a block scale, all fetched once per lane-tile, at the 12,800 × 2,560 shape.
It takes **126–128 µs** whether the grid entry is a 64-bit word shifted per weight or
eight byte loads; the runtime's IQ2_S kernel takes 178 µs in the model. So the packed
gate/up kernel has about 1.4 times of headroom as well (about 2.5 ms per token), not
the "near its bound" stated in reading 3 above, which came from the 4-bit stand-in.

Summed over the classes, kernels that do only this per-weight work would take the
large GEMVs from about 27 ms to about 15 ms per token.

## Correction, 23:40 UTC: the dense numbers above are warm-cache numbers

Three in-model checks with a scratch copy of the runtime's expanded dense kernel
(`in-model-scratch/`, patch included; two-card decode on cards 2+3, exact against the
v2 oracle each time, per-class GPU time):

| Change to the expanded dense kernel | gdn.qkv | gdn.z | qsa.qgate | logits |
| --- | ---: | ---: | ---: | ---: |
| as in the runtime | 100.6 µs | 61.9 | 118.2 | 2,137 |
| block scale read once per 8 weights (run r5i) | 92.2 | 56.7 | 108.1 | 1,892 |
| plus a kernel body with no barrier and no local memory (run r5m) | 87.3 | 53.3 | 102.5 | 1,828 |
| four-part arithmetic in one sub-group, for the split-4 classes (run r5k) | slower: attention 62 → 81, hc.low 18 → 57 | | | |

So hoisting the scale and removing the barrier are exact and worth about 13% on the big
dense classes, not the factor of two the table at the top suggests. The reason is the
benchmark, not the kernels: it reads the same 26–33 MB of weights 15 times, so they
stay cached, and it finishes below the card's streaming-read time for that many bytes
(32.7 MB at 590 GB/s is 55 µs; the benchmark reports 48). In the model every layer
reads different memory once per token. For the expanded dense classes the honest bound
is the streaming roofline: about 55 µs for gdn.qkv (now 87), 33 for gdn.z (now 53), 67
for qsa.qgate (now 102), 1,350 for logits (now 1,830), about 2 ms per token in total.

The expert results stand better: a routed launch reads only 9–10.5 MB, so those kernels
are bound by per-weight work, where the benchmark's 71 µs (4-bit + table) against 130
and 126 µs (grid) against 178 are meaningful, though still measured on cached data.

Rule for timing harnesses: a class whose payload is large must be timed on full-size
buffers that are not re-read between repetitions (rotate across several layers' worth
of memory), or its result is an upper bound on speed, not a prediction.
