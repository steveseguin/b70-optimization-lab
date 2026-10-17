# Packet53: production-order expert GEMV

CPU preparation is complete: GNU/Intel proof repeats, complete production-shape
M1/M2 host comparisons, sanitizer checks, wrapper/parser tests and device
compilation all pass. No device program ran and no speed gain is claimed.
The coordinator's E1/E2 and T1/T2 are pending.

Persistent workgroups amortize IQ2 codebook staging. Virtual logical lanes add
independent work while preserving every production chain and adjacent tree.
Five gate/up arms and three down arms are frozen in the
[candidate manifest](manifest.json) and [preregistration](PREREGISTRATION.md).
The common selection must save at least 30 microseconds per ordinary M1 layer
in both timing owners. All regressions and serial M2 results are reported.

Production controls are packet48b's expert kernels used by packet49c. The
existing packet49 oracles remain unchanged. The model record, production
engine, packet49 oracle unit and packet49c chain were not changed.

- [Kernel design](KERNEL-DESIGN.md) and [CPU identity argument](CPU-PROOF.md)
- [CPU build/gate commands](CPU-BUILD.md), [CPU receipt](cpu-gates.json),
  [Python receipt](python-gates.json), [independent review](REVIEW.md)
- [Coordinator window commands and estimates](WINDOW.md)
- [CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md),
  [findings not to repeat](DO-NOT-REPEAT.md), [retention](RETENTION.md)
- [Task note](../../../../notes/2026-10-17-own-runtime-packet53.md)

The seal binds source, compiled binaries and passing CPU evidence. A passing
seal is preparation evidence; it does not certify device execution or speed.
