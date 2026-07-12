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
reported zero maximum absolute difference. This particular block-scaled DPAS
layout is **closed**: it cannot amortize the per-Q4_0-block FP32 scale epilogue
and partial reduction enough to reach `1.5x`. Do not integrate it into
llama.cpp. A materially different verifier would need to change the
quantization/scale granularity or fuse enough downstream work to alter the
economics; further split-count tuning is outside this experiment.

The 30-iteration run log is outside Git at
`/mnt/fast-ai/bench-results/qwen27-xe2-verifier/run-20260712T160845Z.log`.
