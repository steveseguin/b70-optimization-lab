# Packet15 initial parallel candidate — closeout

<!-- campaign-closeout -->

## Question and identity

Can the real-model scalar non-GEMV interpreter be replaced with parallel
kernels without changing packet1b output/state bytes? October 11, 2026,
Flash-Next/IQ3 model geometry, synthetic BF16 tensors, M=1/3/87. CPU-only
GNU13.3 and IntelLLVM2026.0 builds on steve-b70s; two-card/four-card model
qualification is outside this packet. No model weights downloaded or read.
The [build receipt](build-receipt.json) pins reference, sources, fixtures,
compiler commands and binaries. The prior live card3 run was read only.

## Outcome

**Unqualified candidate; requested bit-exact replacement is incomplete.**
SYCL compile/link passes. 60/72 CPU cases pass; twelve fail under both compilers.
Two fresh GNU runs agree on the gate outcome and passing bytes. 18 mocked
protocol tests pass. No native exactness, timing, model integration or speed
claim. Native timing refuses the failed CPU gate.

## What worked

The [live-prefix evidence](before-snapshot.json) identifies one serial
`single_task` per recurrence site, averaging 1,048.596 ms device time in the
captured prefix. Parallel group/lane scheduling removes the scalar interpreter,
FP32 arena copies and per-dot allocations. The source preserves chronological
scan, dot128 tree, BF16 inter-row state, selected-order reductions, pooling,
stable routes, and materialized HC rounding boundaries. The candidate has no
wait/readback in its owner-managed submit function. CPU passing cases cover
all conv shapes, norms, combine/norm, route/gather, nonlinear activations,
GDN gated norm, MoE combine, QSA prepare/pool/select, and short attention.

## What failed or remains uncertain

GDN source, packed and packed-FP32-weight fixtures fail at M1/M3/M87; the 87-row HC mix and
M3/M87 attention fixtures fail. M3 attention's final BF16 result passes, but
its F32 probability buffer fails. **Do not hide intermediate differences.**
The [elementary census](math-probe.json) proves CPU library bit differences
for some primitive inputs. It does not completely localize every output
mismatch or prove native behavior. Explicit scalar-to-reciprocal rewrites
failed to fix GDN and increased its M87 first-output-buffer mismatches from
162 to 190 bytes on the initial 50-case suite; that change was reverted.

Prompt attention is deliberately straightforward and could still be slow.
All native performance ranges in README are hypotheses. No graph capture,
full-layer integration, rollback transaction, resident-weight routing,
long-context performance or full-model quality gate has passed here.

## Evidence and patches

- [Kernel source](kernels.hpp), [SYCL owner adapter](native.cpp),
  [test/timing runner](runner.cpp).
- [Independent fixture generator](fixtures.py), [build receipt](build-receipt.json),
  [elementary probe source](math_probe.cpp), [probe driver](math_probe.py).
- [Rejected reciprocal patch](rejected-scalar-reciprocal.patch) and
  [actual initial-suite receipt](rejected-scalar-reciprocal.json).
- [Window guards](device_window.py), [18 CPU protocol tests](test_window.py).
- Ignored `build/` retains compiled coordinator executables, deterministic
  fixtures, detailed build output and hash-bound preparation manifest. Restore
  with `build.py` using the pinned reference and installed torch build. These
  generated files contain no unique device evidence. Transient `scratch/` was
  removed; the rejected experiment's patch/receipt remain tracked above.

## When to revisit

Resolve the elementary arithmetic mismatch against the unchanged packet1b
reference and rerun the entire operator census. A different oracle or tolerance
requires an explicit owner decision and would not satisfy this packet's task.
Then run two fresh coordinator-owned card3 exactness windows and the gated
M1/M87 timing command before proposing integration. Preserve packet13's
currently running experiment and its byte identity throughout.
