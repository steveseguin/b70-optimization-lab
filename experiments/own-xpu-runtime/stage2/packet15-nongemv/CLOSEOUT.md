# Packet15 arithmetic-authority correction — closeout

<!-- campaign-closeout -->

## Question and identity

Does the parallel candidate reproduce frozen runtime arithmetic identity v1,
using the unchanged [Packet 4 core](../packet4/core.hpp), on all 72 original
synthetic fixtures? CPU-only, October 11, 2026; GNU13.3 and IntelLLVM2026.0;
Flash-Next/IQ3 geometry at M=1/3/87 plus boundary/protocol cases. No model
weights, live Packet 13 files, GPU, server, device node, port or unit touched.

The [arithmetic authority decision](../../../../notes/2026-10-11-iq3-arithmetic-authority-decision.md),
[rebased oracle](../../../qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/README.md)
and [48/48 CPU hash comparison](../../../../notes/2026-10-11-first-token-correctness.md)
establish why Packet 1b Torch bytes are secondary diagnostics. This does not
change the core, model, reduction trees, rounding identity or tolerance.

## Outcome

Before: **60/72** against the superseded Torch reference, **18/18** protocol.
After: **72/72** against Packet 4 in **two fresh processes per compiler**;
**18/18** protocol tests for each compiler build; SYCL compile/link passes.
Each run compares 79,551,248 output bytes. **No remaining core-gate failures.**
The original 12 Torch differences remain visible per case in the
[build receipt](build-receipt.json). Native exactness, timing, model integration
and full-model quality remain pending. No device ran and no speedup is claimed.

## Useful mechanisms

[reference.hpp](reference.hpp) calls the real core, row by row, with stored
gain, FP32 stored decay, packed `h%16`, and original BF16/F32 weight semantics.
The original fixture inputs/diagnostics are unchanged. Separate hash-bound
core-output files are generated under each compiler. The parallel expressions
now match core operand order, max semantics, FP32 literals and square-root
division, preserving every BF16 boundary. The historical single-task backend
remains the arithmetic control, not a performance target.

[The native adapter](native.cpp) also compiles this core as a single_task on
the same device. The prepared window compares every candidate byte against
that result after restoring inputs. Both fresh owners must produce identical
core hashes. Host/device differences are separately reported; the reference
census is excluded from candidate timings. Full native core coverage and
retained hashes are required for timing admission.

## Failures and uncertainty

GNU/glibc and Intel scalar libm core outputs differ by 1 byte for attention
M=3 and 26 bytes for M=87. The candidates match their respective compiled
cores in every case; cross-compiler equality is not claimed. CPU/device
exp/log identity remains open, as does parallel-versus-single_task device
lowering. The native window is prepared, not validated by compilation.

The original failed arm is retained at commit `144f904ff4`, including its
60/72 receipt. Its scalar-reciprocal experiment remains a rejected historical
patch. It is not evidence that reciprocal rewriting belongs in runtime v1.

## Retained evidence and cleanup

- [Build receipt](build-receipt.json): source and per-compiler expected-byte
  hashes, all case diagnostic columns, compiler commands and protocol output.
- [Parallel kernels](kernels.hpp), [core adapter](reference.hpp),
  [runner](runner.cpp), [original fixture generator](fixtures.py).
- [Window](device_window.py), [18 protocol tests](test_window.py),
  [math census](math-probe.json), [rejected patch](rejected-scalar-reciprocal.patch)
  and [historical rejected receipt](rejected-scalar-reciprocal.json).
- Ignored `build/` holds reproducible CPU fixtures, core outputs and coordinator
  binaries. Restore using `build.py`; no unique native evidence exists here.
  This task's scratch files are deleted after validation.

## Next gate and revisit conditions

After separate coordinator admission, run the exact card-3 command in
[README](README.md#reproduce-and-coordinator-commands). It compares with the
Packet 4 core on the same card in two fresh owners. Only after that proof may
native timing run. Any differing bytes require localization, not tolerance
changes or an oracle edit. The existing live run and SCOREBOARD.md remain
outside this task's writes.
