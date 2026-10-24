# P214 frozen-table publication control

This additive P213 successor separates **publication mechanism** from cache
maintenance policy. Both `copies` and `kernel` use the same serial/frozen-two-row
policy, Cache transition hooks, fills, route replay and commit boundaries. The
kernel mode reuses the unchanged selected `p58v::Publish`; it does not enable the
P201 overlap protocol or change recency/capacity policy.

The production executable remains compile-only. Its public `main` returns 64
before argument parsing, model loading or device construction. The retained
future entry combines the inherited P213 serial/paired traversal mode with
explicit `--p214-publication copies` or `--p214-publication kernel`. No launch
manifest or operational entry is provided. Frozen parent sources are unchanged.

## One shared implementation

[publication.hpp](publication.hpp) is compiled into both the actual Engine
overlay and the CPU fixture. It validates all 144 destination bindings and their
layer/projection identities, exact 512-entry extents, nonaliasing, allocation
liveness/generation and complete input table before staging. Each table holds
8,192 bytes; the complete table bank and each contiguous staging allocation hold
1,179,648 bytes. Staging is prepared in full before either mechanism issues.

The copies control uses 144 actual CopyEngine transfers. Kernel mode uses one
logical `Device::compute` operation containing **one H2D upload plus one scatter
kernel**. It is not one physical queue command. Both return tracked completion
covering all table writes before the unchanged Cache commit. Existing
`publication_uploads` accounting follows logical publication operations; the new
`p214-publication.jsonl` names that count explicitly. No native timing or traffic
reduction has been measured here.

The native publisher directly calls queue memcpy/submit and does not implement
prepared submission. The helper therefore refuses `Device::capturing()` before
staging and calls the type-erased immediate compute API, bypassing the Host-only
`audit_prepare_each` capture path. It is never inserted into row prepared sites.
Caller binding arrays are copied; fixed owned table handles remain unchanged
across successive staged address/generation values.

## Ownership and failure boundaries

Pinned staging is a raw host pointer inside the inherited operation, outside its
145 device allocation arguments. The Engine retains that staging and every
table/publication allocation. Pending work prevents restaging. Normal completion
is checked before Engine event retirement, so helper-held event IDs are never
silently treated as completed after becoming foreign.

The native operation can enqueue its H2D upload and then throw before returning
a recorded scatter event. An empty Device ledger is therefore **not** evidence
of completion. The helper marks submission uncertainty before issuing, poisons
intake on failure and preserves the first exception. The exact Backend pointer
is retained immediately before its owning unique pointer moves into that same
Device. Only its public `synchronize()` is called through the borrowed reference;
all healthy work submissions still use Device.

For pending, uncertain or poisoned publication, Engine shutdown settles the
helper before ordinary drain callbacks. Cleanup requires positive synchronization
of the exact owned backend, including hidden work, before permitting generic
Device shutdown. If that proof fails, best-effort evidence cannot bypass
`hold_for_supervisor`; the owner is retained before the outer catch can reset it.
After positive close, the helper is reset before Device teardown. Its destructor
never dereferences the borrowed backend.

Engine issue/guard/prepare, protected upload/release/reset, cache-capacity and
fill paths reject publication ownership. These are **helper/Engine protocol
rules**, not a new Arena lease. In particular, raw Arena's event-ledger checks
cannot discover hidden preledger work. The fixture does not claim raw Arena
refuses release in that case; it verifies helper refusal and live retained
storage. Actual tracked pending work separately exercises Arena's release guard.
Partial publication is never rolled back and never permits a Cache commit or
new intake. Safe cleanup of a poisoned owner remains failure, not success.

## CPU evidence

The first designated [CPU fixture](publication_fixture.cpp) run passed
[41 checks](evidence/publication-proof.json) across seven Host owners. It uses the
actual inherited Host/Device/Arena/CopyEngine and unchanged Host `p58v::Publish`,
with full 144×512 production table geometry, two distinct generations, permuted
constructor maps and caller-side decoys. All address/generation bytes and actual
prepared pointer-consumer outputs match between copies and kernel modes.

The proof includes malformed extents, aliases, stale/released allocations,
reader/capture refusal, tracked pending retention, a real changed first table
followed by a second-copy extent refusal, and a hidden Host backend marker absent
from Device's ledger. Actual Host synchronize fails until that hidden marker is
completed; staging, allocations, failure and poison persist in the meantime.
The marker models unrecorded backend work, not a native partial-DMA fault. Host
bytes/copies are real; its event/context/queue model remains simulated.

[CPU build evidence](evidence/cpu-build.json) retains exact sources, objects,
commands and logs in `evidence/cpu-1792804485930175347`. No failed CPU attempt or
native owner run is hidden by this result.

## Native compile-only boundary

The [native receipt](evidence/build-compile-only.json) passes after one successful
compile/link and a corrected **offline-only reinspection of that same binary**.
The initial attempt's extra inspector incorrectly required an out-of-line
`Publisher::publish` symbol; the compiler had inlined it into
`Engine::publish_cache_table`. That failed assertion and exact compiler
recipe/source/commands remain in
`evidence/build-1792804549364710843/receipt.json`. No native code failed and no
recompile or native execution followed.

The reviewed inspector now checks the enclosing Engine function's disassembly
for both actual CopyEngine and type-erased Device compute calls plus binding
validation, alongside both paired kernels and the inherited Publish scatter
image. The [publisher disassembly](evidence/build-1792804797257672834/publisher-disassembly.log)
and [public-main disassembly](evidence/build-1792804797257672834/public-main-disassembly.log)
are retained. The latter prints refusal then returns 64. The final receipt
separates the changed inspector from the exact earlier compilation provenance
and binds 104 compiler dependencies and 38 inherited objects.

[Build preparation](evidence/build-preparation.json) binds generated Engine
source, parent inputs, 38 inherited native objects and the exact selected backend
source-to-object lineage. [build_native.py](build_native.py) preserves each
attempt before generation, reserves 768 MiB while maintaining a fresh 27 GB root
floor, and uses the compiler-turn lock, nice 19, cores 8–15/24–31, two
OMP/BLAS/MKL threads and a 4 GiB compiler address-space limit.

The recipe compiles/links and inspects symbols, the disabled public-main
instructions and SYCL kernel image entries offline. It never invokes the native
artifact. No GPU enumeration, model work, service/queue operation or settings
change is included. Ignored build artifacts remain hash-bound to the retained
recipe and compact attempt records.

The next native gate is still separately admitted selected correctness: copies
versus the inherited publisher at a real drained boundary, then complete
same-binary Engine output/state/cache-policy comparisons across the existing
serial/paired controls. Native hidden-submission failure handling and performance
remain unqualified by the CPU proof or compiler success alone.
