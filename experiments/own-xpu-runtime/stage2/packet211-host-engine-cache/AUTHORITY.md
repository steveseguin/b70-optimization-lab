# Packet211 tiny Engine cache authority

## Question and identity

Can the actual four-layer synthetic HOST_ONLY Engine keep expert pointer tables
and both rows' routes valid across a frozen prefill interval, without changing
its inherited expert arithmetic or checkpoint state? Three executions of the
same new binary provide the controls: original contiguous weights, indirect
weights with row-serial execution, and indirect weights with paired layer-major
execution. The two indirect modes use identical cache maintenance boundaries.

The new experimental contract is `v1.2+p211`, labeled
`experimental-host-engine-cache`. It does not inherit device qualification or
claim production model quality, GPU completion or a serving-speed improvement.
[Input pins](authority-inputs.json) identify the frozen source authorities.

## Outcome

The designated GNU HOST_ONLY run passed. Three comparison Engine processes
completed 48 requests with 39 SAVE and nine RELEASE controls. All 13 checkpoint
sets per mode match the direct control and retained P207 bytes, including all
20 state blobs and processed tokens. Both cached modes match all 108 canonical
prefill endpoints. The paired mode issued 400 captured pair sites and skipped
800 original submissions.

Each cached mode completed 181 intervals covering 281 consumed positions, with
500 hits, 10,740 misses, 11,007 fills, 11,005 evictions and 16,906,752 actual fill
bytes. Their retained routes, normalized tables, maintenance policy and warm
reset evidence match exactly. These counts demonstrate exercised cache behavior;
they are not throughput results.

One standalone adapter process passed four top10 arithmetic cases and 27 binding
and mutation checks across nine small Host owners. One separate Engine process
hit the intentional cached partial-chunk failure, refused further intake, saved
no checkpoint/result and exited1 safely without SIGTERM or retained resources.
Ten parser processes refused unsupported modes before owner creation. Eleven
read-only authority tests subsequently passed without replaying a native owner.

## Existing arithmetic and the required binding change

The inherited `performance.cpp` HOST_ONLY `Multiply` reads contiguous,
expert-major weights. It validates each Route, updates route status, chooses
shared versus per-slot BF16 inputs, calls `arithmetic::row` with variant2 and
converts the result to BF16. The raw and checked copies of this body match;
their exact digest is recorded in the input pins.

There is no existing tiny F32 indirect submission mode. The p28 validator
allows indirect weights only for its quantized routed types; dense F32 forbids
routes and multiple experts. The p39 expert templates statically require
IQ2/IQ3 at K2560 or IQ4 down at K640. Merely enabling cache allocation for mini
would pass pointer-table bytes to a contiguous-weight consumer.

The explicit new HOST_ONLY adapter therefore changes address binding, using
the inherited pointer resolver while preserving the original route/status,
input selection, arithmetic call, reduction policy and BF16 conversion. The
direct control must continue to call the original inherited expert function;
it must not silently use the new adapter with a different flag. This is an
address-adapter qualification, not newly invented expert arithmetic.

## Engine integration constraints

The production cache assumes 48 layers, 512 experts, 144 table destinations and
a retained 21,552,729,600-byte arena. The tiny adapter must explicitly use its
four-layer geometry and 12 tables with a bounded aligned cache. The fixed
144-destination Publish operation cannot be invoked with an incomplete tiny
destination array. A tiny direct CopyEngine publication path can preserve the
same pointer-table bytes without claiming that production overlap was exercised.

Startup `cache_capacity` is called after initialization; it is not called for
each request. `p58_reset_request` zeros request/scratch allocations but skips
weights and pinned slabs. The new process cache, pointer tables and immutable
banks must survive that reset with their contents and residency consistent.
Route workspaces and request state must reset normally. Snapshot before/after
reset evidence must distinguish immutable cache preservation from request-state
reuse. Checkpoint restore happens after request reset and restores only the
existing state inventory; cache pointers are not checkpoint payloads.

The frozen read interval covers both complete rows and every layer. Route
records must be copied before the shared route workspace is reused, including
the distinct gate/up and down Route extents. Maintenance replays row0 layers
0–3 then row1 layers0–3 with slot order preserved. The row-serial cache control
must use these same intervals, not the old one-position overlap policy. The
final prompt, single-row boundary tails, decode and restored continuation still
consume correct indirect weights even where there is no paired interval.

## Meaningful exactness gates

1. Run the unchanged 16-request fixture in three separate, bounded, sequential
   owners. Each uses 13 SAVE and three RELEASE controls and a clean final drain.
   Restore only checkpoints produced by that same owner/new binary. Inspect
   P207 and P198 checkpoints as external byte oracles; never restore them.
2. Compare generated IDs and all 20 state blobs plus processed tokens and
   pending-token/control descriptors for every checkpoint. Cover A/B/A reuse,
   same-generation continuation, append/repeat/fresh references and the restored
   pending token at position31 before crossing32.
3. Compare every completed two-row canonical state and remaining serial-tail
   endpoint to the original direct control: 100 pairs plus eight tails, or108
   endpoints, for each cached mode. Final prompt and decode indices must stay
   unchanged. Paired execution must issue its expected actual prepared pair
   sites and skip their original submissions, while the serial control does not.
4. Compare both cached modes' complete interval route records and chronological
   replay, hit/miss decisions, fill/publication transactions, residency and
   normalized pointer generations/offsets. Raw process addresses are not
   comparable across owners. Require observed cache hits, misses and populated
   reuse rather than accepting an always-host-miss adapter.
5. Prove reset preserves cache allocation identity and bytes while state resets.
   Keep immutable banks and all indirect sources owned until readers and fills
   finish. Captured pointers are not allocation leases. Source review must
   identify the retained owner and no-release boundary for hidden raw pointers.
6. Reject unsupported mode, geometry, backend, ownership, capture/draft/record
   and alternate-start paths before loading weights or creating an owner. Do
   not permit the flag to turn production/full-model paths into tiny tests.
   On a genuine request/native failure stop intake and preserve the original
   error and bounded single incident drain; never retry a request or owner.
7. Before Engine execution, compare the new address wrapper with unchanged
   `integrated::experts` for gate/up and down, each with ten routes, valid and
   invalid Route/status values, partial rows and exact BF16 bytes. Captured
   metadata rebinding must not redirect arguments; live pinned and resident
   payload changes must affect output. Actual allocation/capture guards must
   refuse crossed writable aliases, short tables and released hidden storage.
   First-entry malformed pointers may update inherited status but must not
   write BF16 output; a later malformed entry may leave partial output and
   must poison the owner. Preserve the distinction between clean binding
   refusals and failed-but-drained CPU execution faults.
8. Inject one failure after layer0 row0 while the cached two-row interval is
   active. Require the original error, poisoned intake, no successful request,
   SAVE or interval-publication trace, and a safe failed-owner shutdown. This
   is separate from earlier uncached or standalone cache failure evidence.

Both cached modes cover 181 intervals and 281 consumed token positions. Their
full Route triples are retained and hashed; hit counts are independently checked
against the previously published resident IDs, and eviction must occur. The
serial cached control still records one arithmetic timing row per token; its
canonical state records are grouped at the same frozen boundaries as the paired
candidate. These counts describe scheduling and correctness, not performance.

## What failed or remains uncertain

The intentional failure retained `p211 intentional partial chunk refusal` while
the two-row cache interval was active and poisoned. No successful interval was
published and no rollback is claimed. Both compile attempts passed; the second
adds accurate serial-cache canonical endpoint instrumentation, with the first
source/build candidate preserved.

The proof uses real CPU arithmetic/copies under
the inherited Host/LifetimeMock/MockDevice simulated event model. It does not
prove GPU address accessibility, asynchronous fencing or production overlap
recency equivalence. Production expert quantization and wide kernels remain
outside the tiny F32 address adapter. Cache policy comparisons must be matched;
warm-cache benefits are not a measured paired-prefill speedup.

## Evidence and patches

The new overlay, strict adapter and helper leave all parent sources unchanged.
The harness reuses the byte-exact P207 fixture and retains each plan, protocol,
request result, cache/state trace, checkpoint, owner receipt and refusal. Source,
compiled dependency/object and binary hashes must match throughout execution.
Every meaningful failed attempt keeps its exact source and raw diagnostics.

[The complete raw archive](evidence/raw-host-proof.tar.gz) retains all 1,709
closed run files, including plans, parser logs, arithmetic proof, four Engine
outputs and their state payloads. Its [per-file index](evidence/raw-host-proof-index.json)
records SHA256 and size for every member and the archive; a full readback matched
all bytes. The archive is 2,008,263 bytes for 28,367,578 logical bytes, and the
original ignored build output is also retained. This is permanent research
evidence, not transient build output. Restore the archive/index from Git and
extract to a fresh directory to inspect the original relative run paths; the
archive does not authorize model or device execution.

[Host result](evidence/host-proof.json) and
[authority-test receipt](evidence/authority-tests.json) bind the run and checks.
The test snapshot preserves the exact pre-closeout prose; final documentary
hashes are recorded separately without changing the executed harness or test.

## When to revisit

A passing tiny Engine proof supports the address/lifetime integration only.
Any production or device integration requires a separately reviewed experiment
with its selected arithmetic, capacity and admission identity preserved.
