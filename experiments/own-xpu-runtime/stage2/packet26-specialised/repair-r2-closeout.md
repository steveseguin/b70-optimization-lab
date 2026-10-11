# K1a geometry and CPU validation repair, R2

<!-- campaign-closeout -->

Question: why did K1a fail `expanded dense geometry` after host fixtures passed?
The first dense case is `gdn.qkv.q6`, finite mode 0, packet18/R5 arm, with rows=8,
columns=2560, experts=count=1, span=8, routes=0, BF16 input/output and split=1 (R5 variant 6).
The fixture unconditionally allocated status, including dense matrices. Packet
10 correctly rejects that field. The old CPU twin checked buffer extents only.
The status allocation now exists only for routed expert matrices. No packet 10
source was edited, no device binary was run, and no model arithmetic changed.

The CPU twins compile verbatim validation copied from the device entrypoints,
including geometry, extent, alignment and alias checks. Shared packet 25 and
specialised/adapter validation runs directly. Validation-only K1/K2 traversals
exercise every fixture class and every linked candidate allowed for its format,
using the same argument builders and the complete K2 dimensions. Both host
compilers must reject a deliberately restored dense status buffer. Validation
mode skips computation and does not claim output equality. Ordinary K1 gates
retain byte comparisons.

K2 records each rejected arm with its class, workload, implementation and error,
then continues. Its summary retains the whole class table, excludes failed
candidates and writes dispatch-measured.json even when admission fails. A failed
reference, missing unexcluded coverage or execution budget failure cannot be
waived by excluding a candidate. Execution faults still stop safely. CPU
injections cover failures in the direct, adapter and GEMV halves and require
later classes to run. Summary tests verify unaffected winners and failed-arm
fallbacks, plus rejection when reference coverage is missing.

The wrapper requires its nice value to equal --native-nice (default 19), and
records both values. Hashing, ldd and journal helpers run at nice 19. The wrapper
keeps the native child's inherited priority. WINDOW.md documents W2/W2m/W2c at
nice 0 and K windows at 19; tests mock priority 0, 7 and 19 without raising this
session's priority.

Evidence: [validation gates](validation-gates.json), [wrapper tests](window-tests.json),
[fixture gates](fixture-gates.json), [build receipt](build-receipt.json) and
[the original coordinator failure](evidence/20261011-k1a-a-expanded-dense-geometry/README.md).
The interrupted candidate sweep incorrectly included wide8 on IQ2/IQ3 and
paired_input on IQ4; the all-entry validation caught that test-list error and
its format-specific candidates now match the bridge registry.

Previous-seal K0 and W0 receipts are void. Original build/a-* and build/b-*
evidence is retained. Revisit device qualification only through fresh K0/W0 and
K1a/K1b/K2 `-r2` windows from WINDOW.md, on card 0. No speed or device correctness
claim follows from this CPU repair.

All cheap gates passed: five unit suites, 156 integration cases, four fresh
GNU/Intel fixture processes, 32 sanitizer runs and 61 wrapper/summary tests.
Fixture output bytes retain the previous seal's SHA256. Both validation sweeps
cover all 36 K2 classes and all 17 GEMV workloads (568 K1 and 142 K2 GEMV
entry calls per compiler). Native compilation retains 165 captures, at most
744 bytes; no native executable was run. The two standalone inspection helpers
now keep the inherited 8 GiB hard address-space cap instead of attempting to
raise it to infinity. Final old/new identities are in [reseal-r2.json](reseal-r2.json).

The fresh final-binary CPU replay also passed: 8/8 tokens and 384/384 layer
fixtures match the oracle. The main device binary changed because fixture code
is linked into the same executable; the original model/runtime arithmetic was
not edited. K0 and W0 must be rerun under the new complete artifact set.
