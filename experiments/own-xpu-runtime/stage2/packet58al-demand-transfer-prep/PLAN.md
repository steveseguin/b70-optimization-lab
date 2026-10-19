# Demand staging after the actual router

## Question and identity

Can copying **known, currently missing** packed expert bytes on BCS while
resident slots run on CCS recover enough exposed service to justify a change
on packet58ah? Packet147 section 4's approximately 2.35 ms/token is a legacy
cross-identity sensitivity, not a measured budget or promised 7% saving.
Packet58ai's whole-token census is the prerequisite. Its generous unsplit
ceiling even includes unavoidable resident arithmetic; do not subtract all of
it from token time. Router readback, host submissions, split dispatch, copy
dependencies, cache effects and BCS contention all count.

Parent: `packet58ah-onecard-record`, final chain b, one B70 on card 0,
HC p60fusion + hc-wide, experts wide64+halfcache, p109 other-fusion,
ordered foreground retirement, down-tile16, rows4-shared, overlap maintenance,
max cache 21,552,729,600 bytes, context 4096, BF16 KV, plain greedy target.
No draft, changed quantization, altered CPU oracle, or precision change.
The exact parent result and native argv are pinned by `audit.py`.

## Source map: do not edit the apparent template as if it were the binary

Paths below are relative to `stage2/`. Physical line numbers, not embedded
`#line` directives, are used. `evidence/source-map.json` records hashes and
checks generated source against the source hashes in packet58ah's retained
`lineage/58ag-build-receipt.json`.

Packet58ah contains binaries and source snapshots, **not a build/native tree**.
Its snapshot entry is a generator input. In particular its old serial cache
methods are replaced by the async transform. A build brief must copy the
complete sealed source closure and reconstruct it privately; never compile
the snapshot alone or silently import mutable sibling modules.

| Packet58ah tree site | Physical lines | Purpose / future edit boundary |
| --- | --- | --- |
| `packet58ah-onecard-record/lineage/58ag-snapshot/sources/main.cpp` | 842–918 | Pinned expert banks, original cache table/route storage and serial template. Preserve repacking and exact expert strides; async replacement below is authoritative. |
| same | 1195–1214 | Gate/up dispatch selects `p58ag::expert` and down retains p49d tile16. Add partition/stage bindings around these implementations, retaining their arithmetic. |
| same | 1358–1365 | p109 fused router/activation dispatch; capture its real completion as the demand descriptor producer dependency. |
| same | 1417–1450, 1486–1506 | Prepare and replay. Demand hooks must run in the prepared path, not just legacy `enqueue`. Preserve absorbed commands, layer-end hooks and both parity banks. |
| same | 1809–1857 | Position start, layer loop and existing end-of-position drain/readback. Maintain ordinary output and maintenance order. |
| `packet58ah-onecard-record/lineage/58ag-snapshot/native/engine_bracket.hpp` | 1–52 | Quiescent view selection and arena/weight descriptor equality. Add demand quiescence before view changes; control and candidate share one maximum allocation. |
| `packet58ah-onecard-record/lineage/58ag-snapshot/native_source.py` | 1–35 | Source transformations; do not lose async/capacity transforms while copying the parent. |
| `packet58ah-onecard-record/memory_plan.py` | 1–35 | Parent host budget already includes extra cache backing and half-table charges. Extend explicitly, never revert to the 18 GB calibration. |

The following are **read-only generated dependencies named and hash-bound by
packet58ah's own retained build receipt**, not files falsely claimed to live
inside its snapshot. Their full paths and hashes are in the source map.

| Dependency in `packet58ag-onecard-ports/` | Physical lines | Required behavior |
| --- | --- | --- |
| `build/native/main.cpp` | 589–663 | `ExpertBank`, maintenance state, `cache_boundary`, prior-position planning. Replace eligible later H2D fills with D2D from owned staging; retain revoke/fill/publish ordering. |
| same | 852–905 | Wait/allocate/upload/readback. Existing `readback` drains globally; do not use it for the new early descriptor without measuring that lost window. |
| same | 932–1025 | Existing table publication, initialization and position boundaries. Cache pointers remain unchanged during a position. |
| same | 1307–1321, 1524–1550, 1592–1610 | Exact dispatch, capture and replay hooks. |
| same | 1963–2010 | Enqueue full position, plan previous routes, drain, then observe current routes. This is why staging may outlive the token that created it. |
| `build/native/single_device.cpp` | 26–45, 77–97 | Foreground compute/copy queues plus separate maintenance BCS list; copy-only ordinal discovery. Multiple lists do not mean more copy engines. |
| same | 110–131 | Ordinary `copy()` immediately inserts a compute barrier. Using it for all early demand copies would serialize resident work. |
| same | 167–201 | Separate fill tail, foreground drain, full synchronize, queue/context release. Add demand ownership to every terminal and failure path. |
| `build/native/owner.cpp` | 168–212, 317–367 | Owned dependency validation, prepared issue, foreground copy and async fill adapter. Demand tickets cannot masquerade as foreground or maintenance tickets. |
| `native/cache_protocol.hpp` | 7–42 | One outstanding transaction; revoke only with no readers; publish only after fills complete. |
| `build/native/p58ag_expert.hpp` | 67–118 | Real gate/up slot mapping and exact wide64 half-cache arithmetic. |
| `build/native/p58ag_submit.cpp` | 6–38 | Complete allocation/extent validation before compute. Extend bindings rather than bypassing checks. |
| `build/native/p109_fusion.hpp` | 32–42, 74–82 | Existing ordered expert combination and BF16 materialization; leave unchanged. |

The pinned `p58_pointer.hpp` resolves an address without validating its
generation. Generation numbers are evidence, **not protection against early
reuse**. Pinned tile16, pointer and combination dependencies are also in the
machine-readable source map. Line ranges above must be regenerated if a source
hash changes; a changed parent is a new identity, not an automatic repin.

## One implementation candidate: `bcs-demand-retained32x2`

Build only this candidate if DECISION permits it. Keep original zero-copy as
the control and fallback. Do not launch a geometry or buffer-size sweep.

1. **Know the route.** After the actual fused router, produce a bounded
   descriptor for this layer: original slot, expert ID, resident/miss bit,
   published generation and exact projection byte extents. Charge the small
   descriptor-producing CCS kernel as new work; it is not free router output.
   Classify by exact published pointer membership/ranges against the existing
   pinned bank/cache arena, not generation alone. Classify against
   the table visible to this position, not `prepare()`'s future table or fills
   count. A small route descriptor D2H must depend on router completion.
   Submit resident gate/up work before waiting on the descriptor on the host.
   The resident kernel can classify directly from the stable device table;
   no host route prediction is needed. A host submitter cannot use GPU route
   IDs before this dependency completes. Log descriptor transfer and wait cost.
2. **Admit actual sparse misses.** In ascending original slot order, use the
   first free staging entry only when this layer has resident work and the
   expert is not already selected by a planned/filling maintenance transaction.
   Never duplicate an already outstanding H2D fill. No free entry, all misses,
   invalid route, or an ownership uncertainty uses the original path (invalid
   routes retain their original sticky-error behavior). No benchmark-derived
   expert list, prompt class filter or hidden warm cache is allowed.
3. **Issue demand copies on a copy-only BCS list.** Copy the unchanged packed
   gate/up bytes first, then tile16 down bytes into fixed offsets of that
   entry. Source is the existing immutable pinned expert bank; no extra host
   weight bank or CPU repack. Each demand batch owns its own event chain in
   the same device/context. Do not append it to `fill_tail_`, overwrite the
   maintenance ticket, or call foreground `copy()` and incur its immediate
   compute barrier. Add a narrowly scoped owned BCS API with explicit
   producer dependencies and a separate consumer-barrier operation.
4. **Resident slots first, misses last.** Resident gate/up is already running
   or queued on CCS. Enqueue the gate/up copy-completion barrier **after** that
   resident kernel, then gate/up for staged and fallback misses. Keep all
   writes in their **original route slots**. Use the original activation;
   then resident down, then a down-copy barrier, then missing down. Finally
   run the unchanged weighted combination in original slot order 0..9.
   This conservative ordering needs no per-slot activation rewrite. It may
   hide gate/up copies under resident gate/up, and down copies under resident
   gate/up, missing gate/up, activation and resident down. Those intervals are
   not independently additive. All compute kernels serialize on the one CCS.
5. **Retain packed staging for the ordinary later cache plan.** A selected
   staged miss supplies D2D into the planned cache slot instead of a second
   H2D from its pinned bank. Cache policy, route observation order, capacity,
   one-position lag and two-phase publication remain unchanged. This is
   transfer-source substitution, not early admission into the resident cache.
   Physical H2D bytes, D2D bytes and logical cache-fill bytes are separate
   counters. No claimed improvement can omit the D2D cost or contention.

The original full kernel runs when there is no useful partition; avoid empty
split launches where possible without changing status writes. For a mixed
layer, every valid output/status slot has exactly one writer per projection.
Partition kernels must not zero or poison the other partition's output.
Use a separate immutable **original-slot-indexed** stage map to select a
packed base pointer. `p58::resolve` indexes the original expert ID: passing a
32-entry staging table as its 512-entry expert bank is invalid. Validate the
original expert ID and all original input/output slots even when choosing a
stage base. Preserve subgroup participation and shuffle trees across masked
lanes; a partition predicate must not make a subgroup collective divergent.
Keep the original lane chains, subgroup reductions, BF16 roundings, status,
NaN/Inf and signed-zero behavior. Never combine a resident subtotal and a
miss subtotal: that changes the floating-point reduction order.

## Ownership and event ledger

| Object | Lifetime / release condition |
| --- | --- |
| Pinned packed expert banks | Immutable process lifetime, owned until all foreground, demand and maintenance events drain. |
| Published cache table and resident slots | Stable throughout current position. Existing complete-position fence and host-pointer revocation precede overwrite; complete fills and publication precede new residents. |
| Route descriptor / staging map | Position+layer+generation tagged; descriptor D2H owns its destination through host inspection. A separate small device map is immutable until its partition consumers complete. Do not patch a captured raw pointer in place. |
| Staging entry | `FREE → COPYING → CONSUMING/RETAINED → LEASED_TO_FILL → FREE`. Consumer completion and every D2D reader completion are required before reuse; copy completion alone is insufficient. |
| Demand ticket | Separate namespace/ledger and final native event. Both projection-copy consumers and shutdown can prove completion. Retired handles are never queried. |
| Maintenance ticket | Existing actual terminal event retained; a D2D source lease lasts until that terminal completes. Foreground-prefix completion is insufficient. |

There are two bounded banks, each 32 entries, with **per-entry** leases, not
an unconditional ping-pong swap. Each entry tracks the route snapshot/position
that owns it as well as any eventual plan epoch. The current route observation is only planned
during a later position when maintenance is idle. Until it is selected or
explicitly superseded, its bank cannot be recycled. If both banks are held,
new demand uses zero-copy; it never blocks indefinitely waiting for storage.
After `prepare(previous_routes)`, bind selected entries to exact fill offsets
and generations. Entries not selected can be released after their consumers
finish. If the parent overwrites an unplanned `previous_routes` epoch because
maintenance is still busy, record that disposition and release only entries
with no readers. A later unrelated demand may transfer those bytes again;
do not claim a global once-per-expert transfer invariant.

Demand staging is **not consulted for later-token expert compute**. That
would enlarge the effective cache and change this experiment. Its only later
reader is a policy-selected fill. Misses already pending in maintenance use
zero-copy; a future no-duplicate mechanism for those misses is a different arm.

All output buffers keep their existing positions and reset rules. The new
staging allocation is fixed at load; per-position state is metadata only.
Before request/view switch: drain demand consumers, resolve or discard only
unleased retained entries, drain leased D2D work, quiesce maintenance, then
reset metadata and reprepare. Empty initial expert cache and cached_tokens=0
remain mandatory. Failed copies never publish stage pointers. Failure retains
all owner queues/allocations until graceful completion; no busy hard kill.

## Admission: no bytes from the reserve or larger cache

These are design bounds calculated from pinned layouts, not measured staging
occupancy. GNU and Intel real-shape proofs must check them again.

| Packed projection | Shape per expert | Bytes |
| --- | --- | ---: |
| IQ2_S gate | 640 × 2560, 820-byte row | 524,800 |
| IQ2_S up | same | 524,800 |
| IQ4_NL tile16 down | 2560 × 640, 360-byte row before exact tile permutation | 921,600 |
| One whole expert | three projections | 1,971,200 |
| Two banks × 32 experts | 64 entries | 126,156,800 |

The parent **256 MiB transfer allowance (268,435,456 bytes)** is already in
the 29,963,128,848-byte device-owned bound. Suballocate the 126,156,800-byte
stage pool there, plus at most 1 MiB of demand maps/descriptor buffers. This
leaves 141,230,080 bytes of that allowance for inherited transfer allocations.
Require a full allocation/lifetime census proving their sum fits; this is
not permission to assume the rest is unused. Keep the existing 1 GiB
workspace/control bounds, 262,144-byte half table, 1,179,648-byte async
publication allocation, driver allowance 536,870,912 and device reserve
1,500,000,000 bytes. The admitted device bound has only **240 bytes** of
unassigned capacity after those allowances; no additional top-level device
allocation is available. Failure to fit closes this variant; do not shrink
cache/KV or take reserve to rescue it.

Use packet58u's measured accounting through packet58ah's private admission:
accounted host bound **90,400,317,440** plus unchanged **8,589,934,592-byte
(8 GiB) reserve** = **98,990,252,032 bytes required MemAvailable**. This is
already the max-cache/half-table parent, not 58u's original 18 GB requirement.
Conservatively add 126,156,800 device-backing bytes, a maximum 1 MiB additional
device-map backing, and a maximum 2 MiB pinned/pageable demand metadata/events
even though device staging fits an existing device allowance: host bound
**90,529,619,968**, required available **99,119,554,560 bytes**. Do not count
these additions as a newly measured peak. Keep the existing 4 GiB shadow stop,
simultaneous-sample accounting, full nonexpert/file allowance and live sensor.
Any larger runtime/event allocation must be charged before READY; no dynamic
unbounded per-token event vector. A mixed one-load bracket admits its largest
lifetime footprint in every view. No host settings change is part of this arm.

The **25 GB storage floor** is disk, not VRAM. Keep it unchanged and add the
measured planned writes at device admission. CPU preparation stops below
27 GB free. The build brief specifies artifact-size measurement and the
three-times-measured maximum; inflated blanket multi-GiB reservations are
not a substitute for that measurement.

## Evidence that makes the candidate real

Record real cold first-request rows and all 48 layers. Retain original slot
IDs/masks, packed bytes, router/descriptor/demand/consumer event identities,
resident and miss services, demand H2D and fill D2D bytes, bypass reasons,
bank high-water mark, lease retirement, maintenance contention and actual
copy/compute interval intersections. Device event timestamps must share a
verified clock domain; never subtract host and device clocks or add overlapping
durations into a wall time. An available resident interval is not observed
overlap. No memory-stall label is inferred from a whole expert kernel.

Use the original parent path as the unprofiled control. Compare off-mode
overhead with the frozen parent, preserve cold rows in analyzer tests, and
keep timing checks out of in-run data proofs. The ready build brief spells
out exactness, device-define CPU preparation, offline numerical tolerances,
wait limits, one-load v5 and promotion boundaries.
