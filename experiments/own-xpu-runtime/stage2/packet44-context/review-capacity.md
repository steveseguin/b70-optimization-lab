# Independent capacity review

Reviewed packet38 directly before receiving an implementation conclusion. CPU-only,
read-only inspection preceded the assigned kernel repairs below. No device was
opened or queried. This source review does not substitute for execution gates.

## Findings from the sealed base

1. `main.cpp:193-195` limits capacity to 1024; `kernels.hpp:57` limits it to
   4096. These are admission bounds rather than arithmetic constants.
2. `rope.hpp:6-8`, `build.py:30-31`, and `main.cpp:780-784` fix the rotary table
   at 4096 positions. An extension must retain the old 524288-byte prefix exactly.
3. `kernels.hpp:40,171-176` launches ceil(capacity/4)+1 pooling groups although
   a decode step appends one row and completes at most one pool.
4. `round2.hpp:11-27,69` launches ceil(capacity/4) groups per selection stage.
   Its score storage uses the capacity stride, but only valid pools are scored.
5. `kernels.hpp:42,191`, `round2.hpp:30`, and `p30_attention.cpp:42-45,67` launch
   scores over min(capacity,2051), including unoccupied attention slots.
6. `specialised.hpp:16-38,147-195` also derives pool/select work ranges,
   attention chunks, and softmax/value work ranges from capacity. Retained
   alternate dispatch paths must be repaired along with the default.
7. `p30_submit.cpp:39` overwrites its admitted bound with capacity. Its host and
   device implementations clear the unused capacity-sized score suffix.
8. The two target prepared-command banks (`main.cpp:764-769`, `rank.hpp:banks`)
   and separate draft captures (`mtp.hpp:prepare_commands`) all need bucket
   invalidation. Rollback/reset must not replay stale geometry.
9. `fixture_driver.cpp:171-175`, `p38_qsa_cpu.cpp`, and `suite.py:18` contain
   256-capacity fixture/admission assumptions. Suite token-cap support alone is
   insufficient to admit larger allocation capacities.
10. Builder cache shapes (`../packet3/step/plan.hpp:163-167`) already use full
    BF16 keys/values/raw/pooled arrays and a fixed 2051-entry index list. Retained
    layer fixtures, recurrent banks, scores/probabilities and controls have no
    capacity-dependent arithmetic.

## Kernel repairs assigned after the independent inspection

`ng::Shape` appends `extent=0`. `ng::launch_extent(s)` returns extent when nonzero
and otherwise capacity for compatibility with existing fixtures. Validation
requires a positive explicit extent to contain the submitted token count and
not exceed capacity. Capacity admission is 32768. Physical allocation bounds,
ID validation and selection scratch row strides still use capacity.

The runtime supplies a 32-position rounded extent. Selection launch counts and
attention score ranges use it. The specialised attention chunk counts also use
it. Selection/attention position guards reject an undersized stale extent before
consumption. Other operators retain the capacity bound because their captures do
not need refresh at a selection bucket crossing.

Pooling submits ceil(tokens/4) possible newly completed pools plus one append
group. Each pool maps its compact launch index through device position. The
specialised version makes the equivalent compact mapping for both stages.
For single-token decode this is two groups in the packet18 kernel, independent
of allocation capacity and position. Incomplete pools return immediately.

The packet18 selector only needs ceil(extent/4) local floats for scores. Its old
three-times-capacity-plus-256 reservation was unused. The largest reservation is
now 32768 bytes. Round2 remains a 256-float local allocation and stores scores
in existing global scratch. No selection tie, score, or ordering formula changed.

Both p30 variants and all retained fallbacks use the same launch bound. Unused
score elements beyond the launched extent are scratch, are never consumed, and
are no longer cleared per token. A full scratch-byte comparison across different
extents is not a model arithmetic gate; compare the admitted score/probability
positions, output bytes, and retained layer fixtures. Same-extent fixtures may
still compare their complete initialized buffers.

`p33r2.cpp` needs no change: its existing capacity-128/256 specialization copies
the new extent unchanged, and other capacities use the dynamic body. All actual
attention reductions retain selected n, including odd-tree +0 operations. A
rounded launch extent never becomes an arithmetic tree length.

## Required integration checks

- Extend RoPE with bit-exact old prefix and bind its new hash in the build.
- Propagate extent to target/draft captures and both target bank parities.
- Cross a 32-position boundary speculatively, undo, and compare redo with a
  never-speculated control; resetting a request must likewise refresh geometry.
- Keep selected pools ordered by descending score with ascending-index ties;
  emit four positions per pool followed by unpooled trailing positions. Even
  below the budget chronological ordering would change attention tree order.
- Existing rollback need not copy full QSA caches: invalid append tails are
  overwritten on redo, including a newly completed pool before selection.
- Execute both compiler gates, sanitizer/argument guards, and coordinator
  device qualification. This review alone makes no speed or device claim.


## Capacity fixture and K2 follow-up

The copied fixture driver now explicitly copies the nine shape fields into the
independent snapshot, while historical binary fixtures still read their eight
stored integers and default extent to zero. Snapshot edits are limited to the
appended field, 32768 allocation bound, and unused-score clearing bound; its
core equations and rotary lookup arithmetic stay unchanged. Its rotary constants
come from the packet-local extended table generated by the build.

The six lengths at 4096 are 88, 152, 1024, 2048, 2049 and 4096. The seven lengths
at 32768 are 88, 152, 1024, 2048, 4096, 8192 and 32767. Every length supplies
prepare, pool, selection and attention fixtures. Attention IDs come from the
independent core selector over the same synthetic query/pool fixtures; they are
not reverse-chronological fabricated lists. The selected dispatch must pass the
summary's existing every-workload rule across the complete class grid.

All four classes replay two resident preuploaded arms. Pool replay is idempotent:
prior rows are immutable, and the current raw row is taken from the unchanged
input, so each invocation overwrites the same append and completed-pool rows.
Outputs are compared exactly on every repetition. Retained output records contain
each compared output's uint64 byte length followed by its SHA256, avoiding tens
of gigabytes of duplicate full-cache files. K1 host hashes must be produced for
each capacity because the fixture bytes differ.

`k2-duration-plan.json` records 297 seconds for 4096 and 1840 seconds for 32768
as conservative scheduling estimates, not measurements. The latter intentionally
scales the measured n=64 selector's 13.854 microsecond p90 by quadratic valid-pool
work. The repaired historical four-minute campaign is a fixed allowance, not a
promise that a long selector costs the same. Refuse admission unless estimate
plus 17 seconds is at most one quarter of the watchdog.

The existing CPU summary tests passed 18/18 after these changes. Compilation and
execution of the revised C++ fixture remain separate gates.


## Independent review of runtime extent integration

Reviewed the completed target/draft plumbing in `main.cpp`, `rank.hpp`,
`mtp.hpp`, `runtime_kernels.hpp`, `adapter.cpp` and `request_reset.hpp` before
the final rebuild. Three clear findings were repaired:

1. Target and draft binders set extent on every Spec, while bucket admission
   recaptured only selection/attention. An independent fresh-argument audit
   would therefore see changed extent bytes in unaffected kernels. Extent is
   now zero on every unaffected site; only selection/attention carries it.
2. The tiny synthetic pooling adapter still launched ceil(capacity/4)+1 groups.
   It now launches two groups and maps the completed pool through position,
   matching the production single-token append scheme.
3. The tiny selector used scratch offset 2*ceil(capacity/4) with a fixed 8192
   float allocation, out of bounds at 32768. The offset now follows the admitted
   pool extent and its local allocation includes the index dot scratch. A stale
   tiny selection/attention extent is rejected before any reads. Draft admission
   also explicitly validates its host position against capacity.

Both target bank parities carry extent alongside the corresponding prepared
operation map and immutable command vector. Only the active parity is refreshed;
when another parity becomes active, the next half always calls admission before
any launch. At a speculative boundary crossing, undo swaps all four objects back
and restores device position; redo rechecks admission. Keeping a larger valid
bucket immediately after undo is safe and does not alter arithmetic.

Request reset restores parity zero, zeroes mutable state and position, and leaves
captures together with their recorded extents. The next half refreshes the active
bucket before execution; the other bank refreshes when next used. Draft reset
sets its own position to zero, and its next compute performs admission before
launching. No host-position or extent reset can falsely certify stale captures.

The production replay path has no remaining allocation-capacity-derived launch
counts: pooling is constant, selector ranges use valid-position buckets, attention
uses admitted-position buckets and actual selected counts. Allocation, initial
zeroing and quiescent full-state dump/reset still scale with capacity as expected.
This is a source-level conclusion; final compiler, argument-audit, rollback and
request-reset execution receipts remain the qualification authority.


## Final source audit and independent-reference arena

The final read-only pass inspected production kernel bodies, their submission
adapters, prepared replay, both target banks, native controller positions,
rollback, target reset and draft reset. No further valid-position arithmetic
change or capacity-sized production replay loop was found. Remaining capacity
terms in `specialised::scratch_floats`, `round2::scratch_floats` and required-byte
checks reserve or validate storage; they do not iterate over it on replay.
Specialised selection still clears 2051 IDs, a fixed budget-sized operation at
all capacities. Full allocation initialization, reset and evidence dumps remain
capacity-sized request-boundary work.

The reference fixture arena needed a separate correction: its monotonic Core
keeps vector-growth allocations and tree clones for all 6144 output reductions.
The old 256 MiB bound is too small beyond the selection budget. The wrapper now
computes a conservative attention arena from valid positions and the admitted
upper bound, with a 768 MiB hard maximum. Formula values are 67108864 bytes at
n=88 or 152, 475421996 bytes at n=4096 and 592858412 bytes at n=32767. These are
allocation calculations, not observed RSS or performance measurements. Short
requests use the same arena regardless of allocation capacity.

Reference inputs import only valid key/value/raw/pooled prefixes. Geometry keeps
the full capacity bound, and the fixture retains unused tails unchanged for full
byte comparison. Core arithmetic, stable sorting and tree order are untouched.
The arena sizing checks position before integer addition; an INT_MAX poisoned
position cannot overflow during preflight. Execution remains subject to the
recorded compiler fixture gates, not this allocation proof alone.

Output-mask audit: prepare compares slots 6, 7, 8 and 9; pool compares 4 through
7; selection compares all 2051 IDs in slot 2; attention compares output 5, scores
6 and probabilities 7. Every case also compares sticky error 15. Each check is
an exact byte comparison before its compact length/hash record is written.
The generated finite-capacity reference fixtures now fail explicitly if their
independent reference reports an arena or model error.

The retained capacity fixture sets require roughly 1.1 GB at the largest grid;
reference arena and active comparison/transfer copies keep their modelled peak
well below 8 GB. Actual process limits and receipts remain necessary because
allocator/runtime overhead and concurrent jobs are outside that calculation.
