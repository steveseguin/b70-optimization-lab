# Empty-binding K0 repair — closeout

<!-- campaign-closeout -->

## Question and identity

Packet42's first coordinator K0 on B70 card 2, October 12 at 14:25:36 UTC,
failed before kernel execution. This CPU-only repair checks every native
window's argument/binding path against the unchanged chained runtime owner.
No model weights or kernel arithmetic changed.

## Outcome

Floor and tiny's shared empty-binding compile-smoke submission is removed.
All six programs use the bundle-only K0 helper. The sealed real-owner CPU
gate covers six K0 paths, floor T1, and all five K2 components; nine rejection
controls and all 16 protocol tests pass. No device run or speed is claimed.

## What worked

Compiling the real native mains and submitters as plain C++ exposes the same
owner and submission validators without running a kernel. Full repetition
and buffer-rotation coverage closes the gap left by the protocol-only mock.
Recorded kernel module bytes remain present in the rebuilt binaries.

## What failed or remains uncertain

The previous mock could not reject the native empty-binding call. The failed
K0 is a host admission error, with no reported kernel fault and no fault latch.
The compiler's host-only SYCL flag still embedded device images; inspection
rejected that output before execution, and the gate now uses plain C++.
Device bundle compilation, on-card output equality and timing remain pending
under the coordinator's next admission. CPU binding success cannot establish
any of those results.

## Evidence and patches

- [Original K0 and superseded seal](evidence/20261012-k0-empty-bindings/README.md).
- [Gate method and exact coverage](BINDING-GATE.md), [sealed CPU receipt](binding-gates.json).
- [Updated build seal](build-receipt.json), [binary hashes](BINARIES.sha256),
  [unchanged kernel module proof](repair-module-proof.json).
- [Wrapper tests](protocol-tests.json) and [native smoke fix](launch_native.hpp).

All changes are inside this packet. Shared owners/backends were read and
compiled, never edited. No device binary, discovery, sudo or host setting
change was used. Build output remains below the two-billion-byte limit.

## When to revisit

After coordinator admission, run the new `k0b`, `t1b`, `k2b` sequence in
[WINDOW.md](WINDOW.md). A changed native argument builder, validator or owner
requires rerunning the sealed binding gate before another device window.
