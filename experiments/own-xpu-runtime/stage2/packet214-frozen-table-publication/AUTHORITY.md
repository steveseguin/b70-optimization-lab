# P214 frozen pointer-table publication authority

## Question and identity

Can the production Engine use one publication helper for either 144 ordered
copies or one contiguous upload followed by the unchanged p58v Publish scatter,
while preserving exact destination handles and retaining storage on uncertain
submission failure?

The CPU fixture uses the same `publication.hpp` as native compilation, the
unchanged P205 Host/Device/Arena/CopyEngine, frozen p58 Cache/Pointer/Publish,
and the P213 transition controller. It reuses 23 pinned GNU objects. All payloads
are synthetic; no model, GPU enumeration or native executable is involved.

## Outcome

The designated CPU fixture passed41 checks on its first attempt. Seven read-only
CPU authority checks passed against its retained artifacts and generated Engine
source. The final combined ten-test authority suite passed. Native compilation
and linking succeeded with 104 repository dependencies and 38 reused objects;
the corrected offline inspection verified that same binary without rebuilding
or executing it. The public entry remains a refusal returning64.

The tables have full production extents: 144 destinations, 512 entries per table,
16 bytes per address/generation entry, and 1,179,648 bytes per publication.
Two distinct generations match byte-for-byte across the copy and Publish paths
and an independently constructed expected table. Three actual prepared pointer
consumers also read the expected synthetic payload and generation from live
tables after each publication. Different permutations of the constructor's
layer/projection bindings produce identical canonical destinations; later caller
rebinding to decoy destinations has no effect.

Seven synthetic Host owners close safely with no live bytes or in-flight work.
Resource teardown success does not erase failed publication/controller outcomes.
The fixture retains the original error, keeps the failed helper poisoned, and
requires the P213 cache controller to report an unsuccessful failed close.

## What worked

The copies path records144 logical CopyEngine operations. The kernel path records
one Device.compute call using unchanged p58v Publish. On CPU, Publish performs a
contiguous memcpy and scatter; the native source performs one H2D upload and a
scatter kernel. The CPU proof does not count or measure native DMA operations.

The helper copies its destination bindings and validates actual live owner IDs,
logical layer/projection uniqueness, memory kinds and exact extents. Tests
refuse duplicate/wrong bindings, staging/publication aliases, short storage or
input tables, zero pointers/generations, released storage and active readers.
It refuses capture before issuing Publish. Type-erased compute avoids the
HOST_ONLY `audit_prepare_each` implicit capture route as well.

A tracked pending Host marker blocks restaging, close and raw Arena release;
pinned staging and destination storage remain live. After explicit marker
completion, cleanup can finish. This is a real owner-ledger check using the
inherited simulated completion backend.

For partial publication, a first full table copy changes actual destination
bytes before the second transfer's injected oversized CopyEngine call raises
`copy extent/lifetime`. Remaining destinations retain their old bytes. The
publication helper and actual full-size Cache controller remain poisoned in an
unfinished update; commit and new publication refuse. Full synchronization then
permits failed cleanup, without rollback or a success claim.

The hidden-work case creates an actual Host backend marker outside the Device
ledger inside the helper's uncertain-submission bracket, then throws. Device
reports zero in-flight work, but the real borrowed backend's synchronize method
refuses while that hidden marker is pending. The helper retains its staging,
publication buffer and all144 destinations, rejects restaging and denies its
release gate. Only explicit simulated completion followed by successful full
backend synchronization permits cleanup; the original exception still wins.

## What failed or remains uncertain

There were no failed compile or execution attempts in this CPU proof. Intentional
refusals and partial-failure cases are retained within the successful test result.

The first native offline inspection incorrectly required a standalone
`Publisher::publish` symbol; optimization had inlined the helper into
`Engine::publish_cache_table`. The successful compile/link and failed inspection
are retained in `evidence/build-1792804549364710843`. A corrected inspector
checks the enclosing function disassembly, both copy and type-erased compute
paths, and inherited Publish kernel entries. The final receipt is explicitly
inspection-only and preserves the original compiler commands, helper snapshot,
failed receipt and identical binary/object hashes. No rebuild or native run
was used to correct the inspection.

Hidden-work retention is a helper/Engine guard, not an allocator lease: raw Arena
cannot detect a submission absent from the Device ledger. The test therefore
does not call raw Arena release for the hidden-marker case. Generated Engine
mutation/intake/release guards and settle-first shutdown are checked as source
facts. Failed full synchronization takes the retained-worker path before an
outer Engine reset can release storage.

All Host markers, including the hidden marker, are simulations. Actual CPU bytes
and Cache phases are exercised; native DMA failure, queue completion and
full-model correctness are not. A native Publish may enqueue its upload and then
throw before returning the scatter event. The conservative uncertainty state and
actual-backend synchronization address that source-level lifetime hazard, but
this packet does not claim an executed native fault proof or performance gain.

## Evidence and patches

- [Shared helper](publication.hpp), [CPU fixture](publication_fixture.cpp), and [bounded build helper](build_cpu_fixture.py).
- [CPU build](evidence/cpu-build.json), [41-check result](evidence/publication-proof.json), and [initial seven-test receipt](evidence/cpu-authority-initial.json).
- [Read-only tests](tests/test_authority.py) and [offline native tests](tests/test_native_authority.py).
- [Generated source overlay](source_overlay.py), [native compile-only receipt](evidence/build-compile-only.json), and [final authority receipt](evidence/authority-tests.json).

## When to revisit

After separate native admission, compare same-binary serial-frozen2 and
paired-frozen2 with the publication mode controlled explicitly. Validate native
completion, full outputs/state and safe failure retention before any speed claim.
The disabled compile-only public entry grants no execution permission.
