# Expert-cache ownership for a prompt chunk

This is a source-derived integration contract, not an implemented cache policy
or device admission. [Pinned inputs](cache-source-review.json) identify the
unchanged p198 engine and inherited cache state machines. The proposed first
chunk policy is deliberately conservative: resolve old maintenance, freeze the
published pointer table and all referenced storage, execute the complete chunk,
then collect routes and allow the next maintenance decision.

## Existing behavior that must remain explicit

The current overlapping path calls `cache_boundary()` before a position, then
marks the maintenance protocol running. Planning may use the previous position's
routes while the current kernels execute, but actual victim revocation, fills
and table publication happen at drained boundaries. A late fill remains
unpublished with safe host pointers. The protocol's boolean completion arguments
must come from actual native events/drains; the CPU state machine cannot supply
those facts itself.

After a position, the engine drains, ends its read ownership, copies the 48
route buffers, drains again and calls `Cache::observe(ids)`. A later
`Cache::prepare(previous_routes)` touches those routes' recency again before
choosing victims. `observe` can update either live or staged recency depending
on whether an unpublished transaction exists. Consequently, combining two
positions into one maintenance decision changes eviction history even if both
rows' arithmetic is exact.

`cache_quiesce()` is also not a neutral pause: it resolves pending maintenance
and **clears `previous_routes`**. Calling it before a chunk and then claiming
unchanged cache scheduling would be false. A new policy must document whether
that pending planning input is consumed, deliberately dropped after its earlier
observation, or carried forward. Do not invent an empty compute interval to
satisfy `Protocol::prepare`'s running-state precondition.

The two ownership APIs are distinct. The overlap protocol's `running` flag
does not move `Cache` into its own running phase. For a direct, serial-style
frozen chunk, the valid sequence is `Cache::begin_position`, actual completion,
`finish_position`, `prepare(chronological_routes)`, completed fills/publication,
then `commit`. `finish_position` leaves `Cache` in its **ready** phase, where
`observe` is forbidden. That path has only `prepare`'s recency touch and must
not be described as the old overlap policy. A fixture must identify which
ownership API it exercises instead of mixing the two protocols.

## Proposed first integration contract

1. At a real drained entry, finish or resolve all prior maintenance through the
   existing publication rules. Record the policy for any retained previous-route
   list. Keep the same expert cache capacity and exact host/device weight bytes.
2. Establish one read-ownership interval covering both rows and every layer.
   Freeze the published table, generations and referenced victim storage for
   that interval. No new fill may overwrite storage a reader can still address;
   no table publication or capacity/reset operation may occur inside it.
3. Keep each row/layer route record until all consumers and the later host
   observation have finished. Reusing the same per-layer route buffer for row1
   destroys row0's history unless it is explicitly saved. The current recorded
   route readback is 48 × 10 × 12 = 5,760 bytes; two rows require 11,520 bytes
   for these records alone, not a complete workspace budget.
4. Drain actual compute, verify sticky errors, then release read ownership.
   Only then read the complete captured routes. Reconstruct chronological
   order as row0 layers0–47 followed by row1 layers0–47, preserving each layer's
   route-slot order. The layer-major execution order is different and must not
   silently become the host recency order.
5. Plan maintenance under one explicit new policy, using only phase-valid API
   transitions. Require a row-serial
   control with the same chunk boundaries and policy when measuring the later
   paired executor. Keep the unchanged production policy as a separately
   labeled comparison. Report fills, publications, residency and initialization
   separately; exact output does not prove identical cache behavior.

On partial failure, stop new intake and retain the failed owner until its
actual work is quiescent. Neither a successful checkpoint nor an automatic
single-row retry may conceal a partially updated chunk. A metadata assertion
or host timeout does not prove that a device reader has released its storage.

## Meaningful CPU gates before integration

Exercise the real inherited `Cache`/`Protocol` objects with synthetic addresses
and explicit simulated completion facts. Refuse victim publication while reads
are owned, refuse incomplete fill publication, and retain safe host pointers
until completion. Distinct routes for both rows and several layers must expose
lost-row capture and layer-major recency replay. Check entry with idle, planned
and filling maintenance states and a nonempty previous-route list. These tests
can establish metadata ordering and failure policy; native pointer lifetime,
DMA completion and speed remain separate device gates.

## Metadata fixture result

The [four-group fixture](cache_contract_probe.cpp) now passes against the actual
inherited C++ objects; [its receipt](evidence/cache-metadata-tests.json) binds
the compiler, source closure, binary and logs. It exercises direct ownership,
publication/fill refusals, stale generations, failed-update retention and the
distinct overlap protocol. A two-row/two-layer synthetic route sequence proves
that replaying layer-major instead of row-major changes the surviving experts.
All addresses are synthetic integers and all completion facts are simulated.
This does not implement the proposed engine cache policy or prove real fencing.

The first helper attempt stopped before compilation because the shared compiler
lock imports the caller's `build_engine.limits`. The corrected helper registers
its bounded limits callback under that name, following the existing build
recipes. Both source snapshots and the initial refusal remain in `evidence`.
No compile or numerical test failed after that helper correction.

Reproduce from the repository root with the same helper CPU limits:

```bash
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet204-prefill-row-bindings/check_cache_contract.py
```

The helper compiles only this metadata fixture, retains a separate attempt
directory and uses a process-local 4 GiB address-space limit. It has no model,
device or service operations.
