# What bounds a GEMV on a B70: a small bounding study (coordinator, 2026-10-11 22:59 UTC, card 0)

One SYCL program ([bound.cpp](bound.cpp)), not part of the runtime and not an exactness
gate. It runs the runtime's row structure (one sub-group of 32 lanes per row, 8
consecutive weights per lane per 256-weight tile, sequential per-lane accumulation,
tree over 32 lanes) with deliberately simple weight encodings, at three of the model's
shapes. GPU execution time from event timestamps, median of 12; variants that must agree
produce identical bytes ([output](run-card0.txt)).

| Encoding and load style | 12,800 × 2,560 (expert gate/up) | 25,600 × 640 (expert down) | 10,240 × 2,560 (gdn.qkv) |
| --- | ---: | ---: | ---: |
| int8 codes, byte loads | 84.7 µs | 69.2 µs | 57.8 µs |
| int8 codes, one 64-bit load per 8 codes | 137.2 | 97.7 | 99.4 |
| int8 codes, 64-bit loads for codes and inputs | 146.1 | 102.5 | 106.2 |
| 4-bit codes, byte loads, 16-entry table in memory | 159.8 | 113.5 | 120.6 |
| 4-bit codes, 64-bit load, table in registers | 254.3 | 157.6 | 183.8 |
| float32 weights | 254.2 | 123.5 | 201.8 |
| the runtime's kernel at this shape, measured in the model | 178 (IQ2_S) | 130 (IQ4_NL) | 101 (expanded Q6) |

Readings:

1. **64-bit integer work is slow on this GPU; byte loads are cheap.** Loading eight
   codes as one 64-bit word and shifting is 1.4–1.7 times slower than eight byte loads.
   "Wide loads" and register-held tables are the wrong direction here.
2. **The expanded dense kernels have about 1.75× of removable overhead.** A minimal int8
   kernel does the gdn.qkv shape in 57.8 µs; the runtime's expanded Q6 kernel takes 101
   (best packet 25 candidate 85). The difference is per-weight work that is not the
   product itself: the block scale fetched and assembled for every weight, the
   exceptional-scale test per weight, format branches.
3. **The packed expert kernels are close to what their formats allow.** A 4-bit code with
   a 16-entry table costs 113.5 µs at the expert-down shape (the runtime's IQ4_NL kernel:
   130) and 160 µs at the gate/up shape (the runtime's IQ2_S kernel: 178). Only an int8
   expansion would be about twice as fast (69 and 85 µs), and that needs 3.2 times the
   bytes for gate/up and 1.8 times for down, which two cards do not have.
4. float32 weights are memory-bound (about 520 GB/s) and slower than int8 codes.
