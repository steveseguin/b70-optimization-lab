# Independent queue, switch and storage review

Reviewed on 2026-10-17 with CPU-only reads and mocked tests. No GPU, service,
oracle output or packet49b file was changed. Packet49c storage and switch
regressions were added in its new tree; compilation and integration are
reviewed separately.

## STOP and claims

The sealed packet49b queue holds only a file lock on its own chain's
`queue.lock`. Before the oracle is complete, it has no child device process.
It polls STOP while waiting and again immediately before launch. Its exception
handler records a STOP reason and process exit releases the lock. Stale
`queue.lock`, `running.json` and `waiting.json` files are retained records;
their existence is not a global device claim and is not consulted by the
packet49c queue.

`test_p49c_switch.py` imports the unchanged predecessor queue and mocks the
oracle, journal and launcher. It proves STOP during the oracle wait launches
no child, creates no KD directory, preserves completed early state and
releases the chain lock. A second case proves STOP still wins when oracle
readiness changes before the final prelaunch check. These are CPU control-flow
tests, not evidence of an actual coordinator stop.

The coordinator must write STOP only while the old model queue is still
waiting, wait for its process to exit, and verify no KD directory or model
child appeared. An ordinary unsuccessful unit status is expected from the
STOP exception. Preserve its STOP and all receipts; do not clear it, delete
the chain, remove a lock file or restart that queue.

## Cross-chain admission

Window admission samples DRM engine counters through `/proc/*/fdinfo` and
rejects foreign engine activity. It does not reject a sleeping queue merely
because its process name or chain directory exists. Each packet has its own
build path, receipts and local fault latch. Packet49c cannot reuse packet49b's
early receipts: the new binary/build identity requires its own full early
chain.

There is no shared atomic device lock across the two queue implementations.
If the oracle completes during packet49c early work, packet49b can attempt KD.
The foreign-engine check normally refuses overlap, but is not an atomic
cross-queue scheduling guarantee. The coordinator must schedule an exclusive
early window and manage this timing boundary. This preparation does not grant
permission to alter, freeze or stop the existing queue in advance.

## Storage

The immutable predecessor seal is separately bound in
`storage-parent-binding.json`. Packet49b keeps its complete 5,818,804,480-byte
pending model allowance until qualifying completed receipts release the
individual writes. STOP does not release any reserve. The 8 GB root floor
and 500 MB oracle-growth allowance remain.

The 650 MB retained-build cap gives a 20,915,608,960-byte initial requirement
for both requested chains. A 2.5 GB retained build would need
22,765,608,960 bytes and did not fit initial free space. CPU builds have a
separate 2.5 GB peak ceiling and must shrink their own scratch before final
admission. Final measured fit is established by the sealed task's final
storage receipt, not by this preliminary arithmetic.

Packet49b's older sealed admission still reserves packet49 in addition to
itself. The new two-chain budget does not alter that historical policy or
promise that all three queues can resume. No existing scratch was removed.
In particular, packet17's 14.64 GB `wa-reference` tree is explicitly retained
numerical input evidence and is not a disposable-space suggestion.

## Remaining device and timing gates

The actual-engine CPU adapter was also inspected. Its explicit baseline uses
the existing route42 submitter, the SPEED6 `p33.dense.segment` HC gate path,
and P39 HC-low/attention epilogues. Other operations use the same engine.
It compares producer outputs, logical state and every mutable allocation
over both layer types and both separately scheduled M=2 rows. The two fresh
processes and compiler objects are hash-bound. Its `legacy=true` setting
exercises actual `execute_site` dispatch, not prepared-command replay or the
complete two-rank MTP schedule. Those remain device/model qualifications.

Preparation does not establish merged device byte equality, same-oracle
full-model agreement, deterministic fresh-device repeats or a speed gain.
The independent CPU oracle is still required. The coordinator owns early
device gates, the conditional clean switch and the record-scope model chain.

## Seal code review

The new seal binds current compiler source mirrors, compile/link commands,
each executable, native fixture receipts and actual output files. Round2
requires its schema, card, scratch-exclusion scope, four distinct output
directories and clean teardown. The engine gate requires two distinct fresh
outputs, repeats 0/1, the declared arithmetic and CPU-only schema, 5,472
comparisons per process and two clean owner teardowns. Removed compiler
objects remain bound through the explicit cleanup receipt; retained binaries
and their sources still validate. The packet51 selected-kernel provenance
pins both the source header and final local kernel hash.

The initial device build failed at compile time because the prepared-submit
overlay hoisted a launch extent beyond a block-local `wg=256` declaration.
Replacing that constant with literal 256 leaves all geometry and arithmetic
unchanged. The failed source/mirror/log and earlier CPU passes remain under
`evidence/device-compile-refusal`; final qualification must use rebuilt modes.

Storage readiness is separate from CPU arithmetic qualification. The seal
records and checks the immutable precheck's internally consistent status,
including an explicit false readiness if space is unavailable. It does not
claim a future disk snapshot is stable. The live queue repeats admission and
refuses a failed storage check before creating or launching a chain.
