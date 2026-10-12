# Packet38 K2 repair, 2026-10-12

The six timing lengths are **88, 104, 120, 136, 152, 256**. K1 still checks all
66 lengths (88 through 152 and 256); the coordinator's prior fresh K1a/K1b
runs each took about 100 seconds, so this exactness coverage is inexpensive.
No device binary was executed during this repair. New device qualification is
pending K0b, K1ab, K1bb and K2b. See [exact commands](../../WINDOW.md).

## Why one shape took 3.6 minutes

The recorded kernel event sums omitted most harness wall work. Each of four
paired candidate comparisons preuploaded **400 independent states**, each with
19 slots. That makes **1,600 states, 30,400 synchronous uploads and 60,800 USM
allocations per shape**, before output download allocations. Every state also
uploaded the full 524,288-byte RoPE table although attention does not use it.
`Arena::allocate` scans the complete historical ledger for names and totals;
`Arena::release` scans it again to mark a single row dead. The ledger never
shrinks. This adds quadratic host bookkeeping as the grid advances. The timing
loop also copied the whole host fixture for every invocation. None of that was
represented by the 0.1–1 ms kernel event sums.

The small repair keeps one resident QSA binding set per arm (two instead of
400 per paired comparison), reuses pinned output readback, removes that host
fixture copy, and checks exact output/status after **every repetition**. QSA
inputs are immutable and each group overwrites the outputs it consumes; no
state reset is needed. Other stateful operator fixtures retain their independent
states and heavy GEMV rotation is unchanged. The CPU-only smoke runs the same
resident loop three times per arm at all six lengths, with 144 comparisons per
compiler (GNU, Intel host, and ASan/UBSan): **432 exact comparisons**.

The source establishes these avoidable costs; the stopped run did not record a
wall-time breakdown, so their individual share of the 216 seconds is unknown.
No improved device wall duration is invented. The conservative K2 expectation
is **6 × 216 + 300 = 1596 seconds**, plus a 17-second startup allowance:
**1613 seconds, or 26 minutes 53 seconds**. The GEMV/remaining-work allowance is
about five minutes from packet37. See [DEADLINES.md](../../DEADLINES.md) for all
windows, evidence versus estimates, and the enforced quarter-watchdog rule.

## Incumbent and selection

The harness and in-model packet18 path both call the same `ng::submit` score,
softmax and value kernels (`native.cpp`, via `adapter.cpp` in the model), with
capacity256, budget2048 and one token. The old harness used fresh allocations
and waited after each stage; the model uses resident buffers and chains stages.
The repaired harness now matches that residency and chains the group with one
final wait. Kernel arithmetic, precision and the model adapter are unchanged.
The old ~1 ms row is non-representative of model residency. The separate ~265 us
model observation is not a matched control, and the exact numerical discrepancy
remains unmeasured here. K2b must establish the corrected same-run baseline.

Every new QSA event carries `state_storage=resident-overwrite`; the summary
refuses absent/wrong labels and wrong incumbent kernel identities. It does not
reuse the partial timing as selection evidence. Each candidate must pass exact
checks and beat **90% of the resident packet18 median at every one of the six
timed lengths**. A single loss, missing length, missing repetition or wrong
storage identity prevents selection. These are diagnostic operator timings;
they are not a model benchmark or a claim about unmeasured context lengths.

## Rebuild, gates and receipt validity

All 17 executables that link `fixture_driver.cpp` were rebuilt/relinked. The
previous cleanup removed compiler objects, so unchanged dependencies had to be
regenerated for linking. The four `build-*.json` receipts compare their bytes
with `../regenerable-object-hashes.jsonl.gz`: only `entry-k2_fixture.cpp.o` and
`entry-nongemv_fixture.cpp.o` differ; model/kernel/owner objects and ordered link
commands are unchanged. [Changed binaries](CHANGED-BINARIES.md) lists every new
hash; [JSON](changed-binaries.json) retains both identities. Regenerable object
files were removed after recording this proof to stay below the build budget.

Rerun: full fixture arithmetic (two fresh processes per host compiler, unchanged
output hash), linked dense fixtures (GNU/Intel/ASan), argument/poison/continuation
validation, 432 resident QSA comparisons, all K2 selection tests, wrapper tests,
window CPU fixture/model rehearsals, storage and draft-cleanup regressions,
bootstrap and no-launch seal admission. The coordinator's amended
`draft_window.py` exited-child fix stays intact; KD additionally validates the
explicit relink proof before accepting the retained CPU capture hash. Tampered
proofs/mappings/current hashes are refused, and its cleanup gate was rerun.
`coordinator_amendments` is preserved and `cpu_tests_sha256` is generated by seal.

The earlier expensive model CPU runs remain historical executions under their
original binary hashes. [The carry-forward proof](model-gate-carry-forward.json)
explicitly binds them to the unchanged model/kernel object bytes across this
fixture-only relink. It does **not** claim that the full-model suite ran on the
new binary. New miniature wrapper/model checks did execute the relinked GNU
host binary. Kernel arithmetic/source gates whose inputs did not change remain
valid. [The prior seal and gates](prior-seal-and-gates.json.gz) retain original
receipt bytes, including the coordinator amendments.

**No earlier device window admits the new seal.** K0/K1a/K1b remain passing
historical evidence for the previous binaries; K1's exact output hash is
unchanged. K2 remains an incomplete, cooperatively stopped diagnostic. The
wrapper's full source/artifact/seal identity requires the entire K0b → K1ab →
K1bb → K2b chain. W names are unchanged because those windows did not run.

The stopped K2's 872,118,400-byte raw output is retained locally as byte-verified
gzip outside `build/`; [retention receipt](stopped-k2-output-retention.json)
records its original and compressed hashes and restoration path. It is ignored
by Git, like the original raw output. No original bytes were discarded.
The partial timing and stop evidence remain in the original sibling folder.

Build and CPU reproduction commands: [CPU-COMMANDS.md](CPU-COMMANDS.md).
