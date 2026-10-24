# Original-FP8 draft experts: exact on target, acceptance unchanged (2026-10-24)

**Question.** Does running the official MTP draft's routed experts from their original E4M3 codes and BF16 128×128
block scales raise MTP acceptance? Those weights are decoded exactly to F32 in the kernel. The service default instead
re-quantizes them to INT8 with per-16 F32 scales.

**Build.** [Build receipt](build-receipt.json): binary `17c3c5c2…`, built on service binary `a6da826f…`, with
`--draft-experts int8|fp8` (default int8).
- Two objects were rebuilt: `entry.o` and the draft-kernel unit `16.o`. Recompiling the unchanged draft unit
  reproduces the original `16.o` byte-for-byte.
- 39 of the 53 device images are identical. 13 differ only in SPIR-V type-name numbering (1–5 bytes). One image, the
  draft `mtp36::Dense` kernels, gains the FP8 instantiations.
- [`test_fp8_decode.cpp`](test_fp8_decode.cpp): all 254 finite E4M3 codes decode bit-identically to the engine's
  host decoder and to an independent formula.

**Device gate (B0).** The one-time service gate passed against engine 5926: tokens identical on the selftest and on
the incident prompt with 512 outputs, target-only and MTP. The confirmed-token stream equals the result, and the full
target state is byte-identical on both ranks. Draft device memory fell from 4,193,685,814 to 3,643,183,414 bytes
(−550 MB on rank 0).

**Acceptance.** Frozen 12-prompt realistic suite (`stage2/suite-inputs-20261012`), one cold request each, 512 cap,
through the live service. These are service observations, not certified benchmarks.

| | INT8 draft (`a6da826f`) | FP8 draft (`17c3c5c2`) |
|---|---:|---:|
| Pooled acceptance | 77.62% (4614/5944) | 77.52% |
| Median decode tok/s | 24.58 | 24.04 |
| Output text identical | | 12/12 |

Raw data: [int8-suite.json](suite/int8-suite.json), [fp8-suite.json](suite/fp8-suite.json).

**Conclusion.** The INT8 requantization was not what limits acceptance. As a speed lever this is closed: neutral, with
−2% median decode, within this host's 1–3% drift. The FP8 build stays in the service anyway. It is the more faithful
draft, it is exact on output, and it frees 550 MB of rank-0 memory that the batched-prefill and precision work need.
The likely acceptance ceiling is the mismatch between the official draft, which was trained on the original FP8
model's hidden states, and this quantized, abliterated target. Remaining MTP ideas (F32 draft router/logits, a k=2
recurrent draft) are not cheap levers.
