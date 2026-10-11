# What bounds a GEMV on a B70: a bounding study (coordinator, 2026-10-11 23:00–23:10 UTC, card 0)

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
