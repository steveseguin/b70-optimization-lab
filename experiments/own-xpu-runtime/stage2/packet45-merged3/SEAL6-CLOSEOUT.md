# Packet45 seal 6 closeout

The owner authorized one ASAN rebuild and a narrow qualification amendment on
2026-10-15. No other compiler build, real-model CPU run or device execution ran.
GNU host, Intel host and all five device binaries keep their fix6 handoff hashes.
Five ASAN programs changed; the other 36 compiled artifacts and the ABI did not.

Rule: `packet45.fix6.device-oracle-authority.2026-10-15`.
The directive was “6 hours for these slow useless CPU runs is a BAD IDEA”.
The production change is exactly the pinned `main.cpp` grouping repair from
fix6. The recorded change set also identifies its plan gate, mutation harness,
build helper and evidence. All qualification implementation files are separately
hash-bound in [the amendment](seal6-amendment.json). Any other production source
change refuses this reuse path, including arithmetic, ownership and ABI headers.

Fix6 is production code. Its 48/48 plan/dispatch rows cover both measured tables
and the forced-fusion table, target ranks 0/1, KD and draft plans, both draft
placements and contexts 4096/32768. Nine malformed-group checks retain strict
validation. [Fix6 evidence and table](FIX6-CLOSEOUT.md).

The retained six CPU real-model cases are historical evidence, not a claim that
fix6 passed real-model exactness. The coordinator's W2m, WS, WSs and WS128x
windows are the real-model authority: they compare every emitted token with the
immutable arithmetic-v2-detmath oracle. Speed publication must cite hash-bound,
passing, nondiagnostic device receipts for those windows on the same artifacts.
The publication helper rejects CPU, failed, diagnostic, missing and mismatched
artifact receipts. Device qualification remains pending in this CPU-produced seal.

Every other gate remains present. Retained fixtures keep their executed binary
hashes and outputs; their entry points do not execute Engine grouping. Historical
compiler, sanitizer, mini, copy, capacity, memory, storage and owner results are
revalidated under that explicit scope. Intel host stays the prior build and is
labelled historical; GNU host, ASAN and device builds bind current production
sources. Current admission always hashes the actual artifacts. Boot fault latch,
watchdogs, teardown, affinity, memory/storage admission, prerequisites and all
oracle/token comparisons retain their checks.

The evidence is under [evidence/seal6](evidence/seal6). The archive preserves the
preceding 39 receipts exactly (2.75 MB compressed, retained to recover the original
source/binary and gate identities). Restore text members by decoding the
`file`/`chunk`/`end` JSONL stream described by `storage.archive_files`; the
retention receipt binds its SHA256. The premature seal refusal while ASAN was still
building is retained as `seal.log`. The completed seal is bound separately to
the blocked-launch admission receipt. No incident directory was modified.

Reproduction, without another build or model execution:

```sh
taskset -c 4-15,20-31 nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B seal45.py
taskset -c 4-15,20-31 nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B test_window_seal_admission.py
taskset -c 4-15,20-31 nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B -c 'import seal45; seal45.verify_window_admission()'
```

Revisit this amendment on any further production-source change. It grants no
general waiver and no speed or exactness verdict before the device windows pass.

Final gates: 33 retained/new receipts; 48/48 plan rows and 9 grouping checks;
7 reuse, 10 amendment/publication, 8 audit and 45 seal-binding tests;
88/88 blocked-launch admission checks. Zero new real-model CPU cases.

| Seal artifact | SHA256 |
|---|---|
| build-receipt.json | `85f1100617612698dc73d50162c309605a6ce976faf71ca9f6bb711c458fe585` |
| cpu-tests.json | `c8ad346e3a108754dc085dd32e5bf68d05954873fb7f5cce2b5ca0bb11051211` |
| window-seal-admission-gates.json | `41fa7d994b7fecbb8e3ff16937ea5b757666922c4afa1f5fd011402d1fd969ac` |
| window-seal-binding.json | `223cac929493c0fe01201dd3431566c8eba697eb60784c54a25e251cd2653d17` |
| seal6-amendment.json | `b7c3d690672c77b1f98e1c74bc2621b539905b936fef17110836c4305013d188` |
