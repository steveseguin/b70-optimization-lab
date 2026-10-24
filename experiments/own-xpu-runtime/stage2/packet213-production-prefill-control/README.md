# P213 matched prefill control and cache transitions

This additive P212 successor provides a row-serial control for the same
frozen-two-row cache policy and closes the cache phase bookkeeping gaps found
in P212. The production executable remains compile-only: public `main` always
returns 64 before option parsing, model access or device construction. Both
modes exist in one retained future-entry body, not an operational launcher.
Frozen P198/P201/P208/P212 sources are unchanged.

## One policy, two traversals

[production_control.hpp](production_control.hpp) is consumed by the Engine and
the CPU schedule fixture. `serial_frozen2` executes every original nonfinal
site for row 0, then every site for row 1. `paired_frozen2` uses the unchanged
P212 layer-major schedule: 70 selected Q6 pair commands replace 140 original
projections across 35 GDN layers; layer 2 Q8 and all 12 QSA layers keep their
original operators. Empty fused followers remain logical slots.

Both modes use identical private row buffers, shared persistent state, retained
960 expert route records, chronological route replay, frozen interval boundaries
and final canonical publication. They preserve ordinary final-prompt/decode and
same-generation resume behavior. Neither mode inserts a final head/sampler or
per-row canonical commit into the two nonfinal rows. Shared matrix/capture
construction and mode-specific chunk receipts make the intended control explicit;
CPU metadata cannot establish native arithmetic equality.

The future entry requires `--p213-future-prefill serial-frozen2` or
`--p213-future-prefill paired-frozen2` plus the exact P212 production admission.
These arguments do not make public `main` executable. Both policies differ from
P201 overlap maintenance: serial publication still uses 144 CopyEngine transfers,
and no performance improvement is claimed.

## Precise cache completion bookkeeping

[cache_transition.hpp](cache_transition.hpp) wraps the actual pinned Cache calls.
Successful begin/finish/prepare/commit calls are immediately followed by
`noexcept` scalar state stores. The exact `p58::Plan` type is statically required
to be nothrow move constructible and move assignable, so returning a prepared
plan cannot introduce a throwing gap after Cache enters updating. The commit
wrapper records idle before counters, logs or statistics saving can throw.

The [overlay](source_overlay.py) routes ordinary single-row begin/finish through
the same controller as chunk intervals. This includes tails, final prompt,
decode and the serial stream-layer helper; otherwise their epochs would make the
shared fill/commit tracking stale. Resetting cache capacity does not advance the
pinned Cache epoch. Overlap/bracket paths remain outside the admitted mode.

Exceptions poison intake and preserve the first exception pointer. Cleanup never
clears it or turns a failed request into success. Once actual owner completion
is proved, cleanup uses `close()` for ready/idle, `finish_position` then `close()`
for active readers, and `close_failed(true)` for an unfinished update. Before
completion, `close(false)` leaves Cache untouched and returns false. There is no
rollback of overwritten victims or partially published tables. Prepared issue
is admitted only in idle/readers, never ready/updating/closed. Transition state
is bookkeeping under exclusive wrapper use, not a new public Cache phase query.

Consequently, refusal before successful prepare remains ready; failure after
prepare remains updating; and failure in statistics saving after successful
commit remains idle. Actual queue completion and resource retention remain the
Engine's responsibility. The CPU fixture uses the existing Host backend's
simulated events with real memory copies; it does not qualify native DMA faults.

## Evidence and build scope

The [CPU schedule proof](evidence/schedule-proof.json) passed 38 checks; the
[transition proof](evidence/transition-proof.json) passed 63 checks across ten
tiny Host owners. The latter uses actual Cache calls and real CopyEngine bytes
with simulated completion markers, including incomplete-marker retention and
post-commit evidence failure. It also checks a real first 32-byte projection
copy followed by a second-copy extent refusal: the changed bytes remain changed,
old table bytes remain unpublished, cleanup stays failed, and intake cannot
resume. Reader-phase external failure and actual `finish_position(...,false)`
refusal cover failed cleanup from an active interval. [CPU build evidence](evidence/cpu-build.json)
retains the corrected run. Earlier attempts are preserved: a missing standard
`<algorithm>` include refused compilation, then a marker fixture incorrectly
bound a pinned allocation to a device-only compute operation. The corrected
marker fixture binds device cache/table storage and retains its pinned source
under the actual owner's pending-work lifetime guard. Neither failure was a
native device or model result. The earlier passing 88-check checkpoint is
retained under `lineage/before-partial-readers-gates` and its original attempt;
the final 101-check CPU run is retained at
`evidence/cpu-1792803596603678486`. These are fixture corrections/extensions,
not retries of a model or native device owner.


The single native compile/link/offline inspection passed. Its
[receipt](evidence/build-compile-only.json) binds 103 compiler dependencies and
38 inherited objects. Both serial/paired mode bodies are compiled in the same
future Engine entry, and both Q6 paired kernel entries are present in the SYCL
image. [Public-main disassembly](evidence/build-1792803527629726162/public-main-disassembly.log)
shows refusal output then return 64. The resulting native artifact was never
invoked. This is compilation and image-presence evidence, not executed
same-binary serial/paired equivalence.

[Build preparation](evidence/build-preparation.json) retains generated source,
source and parent pins, the precise single-device source-to-object lineage and
38 inherited native objects. The [build helper](build_native.py) preserves each
attempt before generation, checks a fresh 27 GB root floor after a 768 MiB
reservation, and uses nice 19, cores 8–15/24–31, two OMP/BLAS/MKL threads, a
4 GiB compiler address-space limit and the existing compile-turn lock.

Native compilation followed the reviewed source/build checkpoint and passing
CPU fixtures; the final CPU extensions changed no compiled native source. The helper only compiles, links and inspects ELF/SYCL artifacts
offline. It never invokes the resulting binary. Device enumeration, native
owner execution, model loading, service/queue actions and settings changes are
outside this work. Ignored binaries/images are bound by recipe and hashes;
retained attempts include exact sources, commands, logs and compact receipts.

The next gate remains separately admitted native correctness: first the selected
paired-kernel reference comparison, then same-new-binary serial/paired Engine
output and complete state comparisons with these matched policies, including
append/pending-token handling and failure retention. No timing claim follows
from compilation or CPU metadata checks alone.
