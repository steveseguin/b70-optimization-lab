# Xe2 Q4_0 x Q8_1 multi-token verifier experiment

This is an isolated, unintegrated experiment for the target verifier's real
`M=4/8` widths. It does not change llama.cpp dispatch. It compares one XMX/DPAS
kernel against a repeated vector-style kernel using the same packed weights,
activations, scales, output shape, and device-event timing.

The kernel maps one Q4_0/Q8_1 block directly onto one DPAS operation:

- `A`: row-major `M x 32` signed INT8 Q8_1 values;
- `B`: VNNI `32 x 16` signed INT4 values;
- accumulator: signed INT32 `M x 16`;
- epilogue: multiply each block accumulator by its Q8_1 row scale and Q4_0
  output-channel scale, then accumulate FP32 across K blocks.

Offline weight layout is
`[K/32 block][N/16 tile][K/8 group][N lane][8 signed nibbles]`. Each
`32 x 16` tile is exactly 256 bytes and can be loaded as 64 dwords. Because
DPAS `s4` expects two's-complement nibbles while ordinary Q4_0 means
`stored_nibble - 8`, the packer flips bit 3 (`stored_nibble ^ 8`) while
transposing into VNNI order. A production packer must perform this conversion
once at model load or on disk, never during decode.

Run only on an explicitly reserved card:

```bash
ZE_AFFINITY_MASK=3 ./build-and-run.sh
```

Compile without touching a GPU:

```bash
XE2_COMPILE_ONLY=1 ./build-and-run.sh
```

The executable compares all DPAS outputs against the repeated-vector kernel and
checks the first 64 output columns against an independent CPU reference (a
full-size CPU reference would dominate experiment time). A shape passes only
if all maximum absolute errors are at most `2e-3` and median DPAS kernel time is
at least `1.5x` faster than the repeated-vector kernel. Exit `2` means
correctness failure, including an incorrect VNNI packing assumption; exit `3`
means the performance gate failed. Both M=4 and M=8 must pass before any
llama.cpp integration is considered.

This experiment intentionally measures the verifier projection itself. It does
not include activation quantization, command submission, graph replay, state
commit, or sampling, so passing is necessary but not sufficient for an
end-to-end MTP win.

## Result and disposition

The original one-work-item-per-N-tile kernel was correctness-exact but only
`0.30x` the repeated-vector speed. A bounded rescue split the 160-block K chain
across 4 and 8 ESIMD work-items and reduced their FP32 partials in a second
kernel. That recovered most of the loss, but still missed the required gate:

| Width | Best split | Combined event time | Wall time | Vector wall | Speedup |
|---|---:|---:|---:|---:|---:|
| M=4 | 4 | 124.270 us | 132.499 us | 147.086 us | 1.110x |
| M=8 | 8 | 246.249 us | 254.097 us | 277.911 us | 1.094x |

All original, split-4, split-8, vector, and CPU-reference correctness checks
reported zero maximum absolute difference. That one-N-tile mapping is closed.

A second mapping changed ownership rather than merely tuning split count. One
ESIMD work-item now owns two adjacent N16 tiles, loads each Q8 activation vector
and activation scale once, executes two DPAS operations, and applies the 16
weight scales as an ESIMD vector epilogue. It retains the exact same offline
VNNI pack and split-8 partial layout, so it does not introduce runtime repacking
or a second weight artifact. This crossed the gate decisively:

| Shape KxN | Width | Joint-2 wall | Vector wall | Speedup |
|---|---:|---:|---:|---:|
| 5120x5120 | M=4 | 22.733 us | 148.109 us | 6.515x |
| 5120x5120 | M=8 | 21.290 us | 278.353 us | 13.074x |
| 5120x17408 | M=4 | 117.771 us | 569.770 us | 4.838x |
| 5120x17408 | M=8 | 126.257 us | 874.503 us | 6.926x |
| 17408x5120 | M=4 | 97.173 us | 557.437 us | 5.737x |
| 17408x5120 | M=8 | 101.039 us | 929.305 us | 9.197x |

Every joint-2 and joint-4 comparison against that synthetic repeated-vector
control had maximum absolute difference `0.000`. Joint-2 beat joint-4 on those
tests, but the control is weaker than production: llama.cpp's reordered
`ncols<4/8>` MMVQ shares weight loads across verifier rows.

The corrected production-kernel comparator closes integration: total M=4
speedups were `1.407x` (5120x5120) and `1.374x` (5120x17408), below the `1.5x`
gate; the one `1.662x` M=4 down-projection result also missed the correctness
criterion. M=8 square passed at `1.925x`, but M=8 is not the MTP3 production
floor. This experiment must not be integrated on the synthetic speedups.

The 30-iteration run log is outside Git at
`/mnt/fast-ai/bench-results/qwen27-xe2-verifier/run-20260712T200914Z.log`.
