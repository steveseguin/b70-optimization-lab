# P213 matched traversal and cache-transition authority

## Question and identity

Can one compiled production helper select either an all-original serial two-row
control or paired traversal under the same frozen-cache policy, and can its
cleanup controller follow the actual Cache phase through failures?

This packet uses the same `production_control.hpp` and `cache_transition.hpp`
in the CPU fixtures and production native compilation. The schedule input is the
unchanged P212 extraction of the actual P201 48-layer plan. The transition
fixture calls the frozen p58 Cache and uses the unchanged P205 Host, Device,
Arena and CopyEngine with 23 pinned GNU objects. Its allocations and payloads
are tiny synthetic data; no model or production native executable runs.

## Outcome

The final fixtures passed 101 checks: 38 schedule checks and 63 transition checks.
Nine subsequent read-only authority tests passed. The native compile-only build
also passed with 103 repository dependencies and 38 unchanged parent objects.
Offline inspection confirms both paired projection kernel entries and a public
`main` that refuses and returns64 without calling the future entry.

The serial control emits 2,958 original logical steps, all of row0 then all of
row1. The paired path emits 2,888 steps including 70 paired calls replacing
140 original row sites. Both preserve each row's exact 1,479-site nonfinal
chain, empty fused followers, prepared-command multiplicity and the same 960
chronological route identities. Final/head/argmax/commit sites are excluded.
The paired sequence also equals the frozen P212 shared traversal exactly.

Ten synthetic Host owners close safely with zero live bytes and zero in-flight
work. These owner teardown receipts describe resource safety. They do not turn
an intentionally failed cache operation into a successful operation: the shared
controller remains poisoned, retains the original exception and reports
`successful_close()==false` for every failure scenario.

## What worked

The controller wraps the actual Cache transitions. Its phase changes occur
immediately after successful calls through nonthrowing scalar hooks; the Plan
move constructor and assignment are statically required to be nonthrowing.
Generated ordinary-position begin/finish and shared `fill_cache` prepare/commit
calls use these wrappers, alongside chunk intervals. A success fixture advances
three actual epochs, representing chunk, ordinary tail and next chunk.

Failure cases cover an exception before prepare, actual out-of-range prepare
refusal leaving `ready`, actual copy and publication-commit refusals leaving
`updating`, and an injected statistics-save exception after commit leaving
`idle`. They preserve the first exception despite later cleanup errors, reject
new intake, and close only after drain. The prepare/commit automatic-poison
assertions run before the fixture applies any surrounding explicit poison.

The partial-fill case performs a valid first32-byte projection copy, then an
oversized second copy refuses. It verifies that the first projection changed,
the other projection bytes and published old table did not, and cleanup closes
the failed update without rollback or reopening intake. Additional cases cover
an external failure while readers are active and actual `finish(false)` refusal.

A real Host pending marker prevents close and release. The device arena and
table are directly bound to the operation; the pinned payload is protected by
the owner's actual global in-flight release guard. Both allocations remain live
until explicit simulated marker completion, after which safe cleanup preserves
the failure. CPU payload and pointer-table copies are checked byte-for-byte.

## What failed or remains uncertain

The first fixture compile failed because the new schedule fixture omitted
`<algorithm>`. No fixture executable ran in that attempt. The second attempt
passed scheduling and closed six transition owners, then its pending-marker
setup incorrectly supplied a pinned allocation to Device.compute, which only
accepts device allocations. With automatic marker completion disabled, failed
fixture unwinding retained a final marker and aborted. This is retained as a
fixture setup failure, not a Cache-controller failure. The correction binds the
actual device arena and table; pinned storage remains covered by the owner-wide
in-flight guard.

The corrected initial proof passed88 checks. Root then requested nonvacuous
partial-fill and readers-phase cases; that successful proof is retained under
`lineage/before-partial-readers-gates` and its original attempt. The final101
checks supersede its coverage without deleting it. Every attempt retains exact
fixture/header/build-helper sources, compiler output, run output and receipt.

The Host backend performs real CPU byte operations but inherits simulated
completion markers and context lifetime bookkeeping. It does not prove native
queue completion, native partial failure, full-model arithmetic or speed.
The generated integration hooks and disabled entry are source/offline gates;
the full production Engine has not executed. P212's cleanup phase mismatch is
addressed by this shared controller and CPU evidence, while actual native
qualification remains a separate admitted experiment.

## Evidence and patches

- [Shared controller](cache_transition.hpp) and [mode traversal](production_control.hpp).
- [Schedule fixture](schedule_control_fixture.cpp) and [actual Cache/Host fixture](cache_transition_fixture.cpp).
- [CPU build/attempt receipt](evidence/cpu-build.json), [38-check schedule result](evidence/schedule-proof.json), and [63-check transition result](evidence/transition-proof.json).
- [Authority tests](tests/test_authority.py), [offline native tests](tests/test_native_authority.py), and [nine-test receipt](evidence/authority-tests.json).
- [Native compile-only receipt](evidence/build-compile-only.json) and [authority input pins](authority-inputs.json).

## When to revisit

Use the same new binary's serial-frozen2 control when native qualification is
separately admitted. Validate full model outputs and state, native pointer/copy
completion and failure retention before considering any performance claim.
The compile-only artifact itself grants no permission to execute it.
