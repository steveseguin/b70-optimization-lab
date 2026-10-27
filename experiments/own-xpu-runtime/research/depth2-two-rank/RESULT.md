# Two-rank depth2 implementation

## Artifacts

- `depth2.patch`: production source delta against the isolated B19 copy.
  SHA256 `7667372a94e423fb19102a817448a024af669b72ef11f0eaa9a4b02c5c27123f` (675 lines; `a/src/...` and `b/src/...`; `patch -p1 --dry-run` passed from the canonical engine root).
- The patches are authoritative. The isolated `engine/` build tree is scratch and is not committed.
  SHA256 `d96d1941e202416312c6e8d8e111646d630d4872e3a1a8ee21ebe872c8f05a2e` (142 lines; `patch -p1 --dry-run` passed against the reviewed depth2 source).
- `depth2-memory-update.patch`: incremental alternative for trees that already have the previous memory patch; touches only `mtp.hpp` and preserves the tested cache-sized content.
  SHA256 `f96705b46058b0a2a7f3478cc12bfeb27c90e3650b5f2ea2d7ce42440cb8d7bf` (25 lines; `patch -p1 --dry-run` passed from canonical engine root).
- `depth2-request-gate.patch`: incremental per-request admission delta against the cache-sized tree.
  SHA256 `f5bfcf53a8e32e28a34133975fc1893fdf08b06e3b83035cf46328c21e16ec40` (31 lines; `patch -p1 --dry-run` passed from canonical engine root).
- `engine/`: isolated complete source tree; canonical engine sources outside this directory were not edited.
- `native_controller_depth2_test.cpp`, `test_controller.py`, `snapshot_geometry_test.cpp`, `controller-test-results.json`, and `snapshot-geometry-results.json`: CPU differential harnesses and receipts.
- `test_memory.py` and `depth2-memory-accounting.json`: zero-additional-rank1-allocation source invariants and 64K/32K accounting.
- `/dev/shm/ownrt-depth2/full-build/sc117-depth2`: successfully linked full engine.
  SHA256 `b125e47ab123d3f39234460b485b6f963e085fae923be3c15efca72937d0fe89`.
`OWNRT_DRAFT_DEPTH2=1` enables the feature. Unset or `0` preserves the B19 depth1 path. Other values are refused. Depth2 is selected per request only when mode=MTP, draft_rank=0, overlap=1, and correction/split probes are absent. Non-overlap, target-only, and other controller modes execute canonical depth1 rather than aborting. Eligible V3 MTP requests remain refused; target-only V3 requests use their canonical controller.


## Protocol and invariants

The existing asynchronous d1 publication is consumed normally. A rank0 draft command with `speculative=2` snapshots the complete mutable post-d1 draft state and recursively computes d2 from the draft's own streams. This is the same arithmetic executor as the canonical draft; there is no target arithmetic change.

Only rank0 target rows are speculative. Rank0 has independent `Candidate` and `SpeculativeImage` instances for d1 and d2. The base target result is already available before dependent submission, so rank1 d1 is submitted only after d1 is verified, as an ordinary confirmed half. Rank1 therefore has no suffix image, no speculative rollback allocation, and no additional arena bytes; its raw-ring and session paths remain the canonical depth1 paths. Private rank0 image/table labels are unique, excluded from nested capture, and classified at request/checkpoint boundaries.

Resolution is:

1. **Base target EOS or d1 miss:** do not submit rank1 d1. Roll back rank0 d1/d2 in reverse order and restore the draft to its post-previous-confirmed state. A nonterminal miss redoes only the verified target token. A cancelled d1 suppresses d2 submission because no valid d1 row exists.
2. **d1 hit:** accept rank0 d1, commit the draft snapshot, and execute rank1 d1 as an ordinary confirmed row. The draft is now exactly in the canonical state after consuming verified d1.
3. **d2 hit, nonterminal:** additionally accept rank0 d2. The next ordinary rank1 base row consumes the verified target output; no speculative token is emitted.
4. **d2 miss, nonterminal:** accept rank0/rank1 d1, roll back only rank0 d2, and redo the verified target token on rank0. Rank1 did not execute d2 and must not be rolled back.
5. **Terminal after the dependent target result:** d2 is rolled back even when it matches, matching depth1's terminal committed state. Rank1 d1 remains accepted.

Draft `speculative=3` commits the post-d1 snapshot and `4` restores it. Invalid d2 generation restores the post-d1 state before the ordinary depth1 fallback. Every dump/reset/redirect/checkpoint/finish boundary requires both target candidates and the draft transaction resolved. Shared rank1 input rows are restored to the canonical base/corrected hidden row after dependent speculation.
With `dumps=1`, d1 is accepted and `state-(p+1)` is dumped before dependent target submission; `state-(p+2)` follows after the next canonical draft advancement. No intermediate dump is skipped.

Checkpoint coverage includes the second private target images and production draft backup as skipped, boundary-rewritten allocations. Canonical target/draft allocations and host position/extent/history metadata remain in the existing checkpoint machinery.

## CPU verification

`test_controller.py` runs the real `native_controller.hpp` against a two-rank mock with dependent hidden rows, rollback state, cancellation, ordinary split-head service on confirmed rank1 rows, redo verification identity, and complete draft snapshots. Every case compares emitted tokens, complete canonical mock target state, complete canonical draft state, accepted fixture state, and complete state at every dump against depth1 execution. Every candidate case also requires zero rank1 speculative rows.

All 18 differential cases passed:

- both hits;
- second miss with cancellation;
- first miss with cancellation, including uncancelled rank0 d1, confirmed-only rank1 scheduling, and ordinary split-head service;
- no usable guess;
- EOS on the first target result;
- EOS on the dependent target result;
- non-overlap and target-only requests issuing zero depth2 rows, scalar/token-by-token prefill controls remaining depth1, and overlapped prefill MTP still issuing d1/d2;
- output cap after a pair and with a depth1 tail;
- one-output/no-lookahead and exact near-end pair;
- dump/finish boundaries, including both intermediate and pair-end state;
- two-request continuation from quiescent checkpoint state.

Invalid-switch refusal also passed. Receipt: `controller-test-results.json`.
`snapshot_geometry_test.cpp` passed the pooled-divisor regression: the depth1/default maximum remains `(context-1)/divisor*stride`, the extent guard refuses overflow, and raw-ring modulo geometry remains bounded. Receipt: `snapshot-geometry-results.json`.
`test_memory.py` passed. Its source invariants prove that rank1 returns before snapshot inventory/allocation and that only rank0 constructs a suffix image. Adding zero bytes to the parent-supplied rank1 owned totals leaves 64K at 32,123,721,324 B with 88,533,396 B headroom and 32K at 31,154,837,100 B with 1,057,417,620 B headroom under the unchanged 30 GiB cap. These are accounting proofs, not new GPU measurements. Receipt: `depth2-memory-accounting.json`.
The production draft backup no longer has a context-independent 32 MiB limit. It allocates the exact summed `mutable_ids` bytes after requiring draft KV mutable bytes to equal the context-derived `cache_bytes` and bounding only the separate non-cache workspace to 64 MiB. The 64K regression uses the authoritative 155,189,248-byte (148 MiB) cache and admits up to 222,298,112 B total, rather than rejecting it as workspace. Depth1 does not enter this allocation branch, and its draft-memory JSON is unchanged.

The full 40-translation-unit SYCL build and final link passed. Build log: `/dev/shm/ownrt-depth2/full-build.log`.

## Not exercised / remaining qualification

No GPU was launched and no service A/B or speed measurement was performed.

Device qualification must still cover actual VRAM admission for the second rank0 image and exact context-sized draft backup, confirm the source-proved zero additional rank1 allocation, exercise real queue/cancellation interleavings, and compare complete GPU target/draft state plus the actual session op17/18/19 checkpoint sequence. Rank1 raw-ring/session behavior is unchanged by scheduling and needs no suffix-image restoration. The CPU harness proves controller-level checkpoint quiescence and continuation, not a device checkpoint bundle round trip.

An auxiliary all-host engine build was attempted for an additional miniature checkpoint test, but the retained canonical tree lacks the historical host-validation include closure (`device_validation.hpp` and related prepared-submit validation declarations) needed to compile unrelated device-only translation units in host mode. Those unexecuted harnesses were removed. This does not affect the successful production SYCL build, but it leaves the device checkpoint round trip as an explicit qualification item rather than a claimed CPU result.
## Device result: exact but slower; rejected (2026-10-27)

Canonical integration and device qualification found and fixed three issues not visible in the mock:

1. Rank1's second suffix image exceeded the 30 GiB cap at 64K and 32K. The final schedule submits rank1's d1 only
   after verification as an ordinary confirmed half, so rank1 has no suffix image or additional allocation.
2. The production draft backup was larger than the assumed 32 MiB. The final code allocates the exact mutable
   inventory, requires context-derived cache bytes (155,189,248 at 64K), and bounds only separate workspace to 64 MiB.
3. The service's target-only/non-overlap/prefill controls require canonical depth1. Final per-request admission uses
   depth2 only for eligible overlapped rank0-draft MTP; all other modes use canonical depth1.

B20 with depth2 disabled passed both 64K oracles, prefill 13/13, continuation and session compatibility. Its suite
matched B19 in every output and MTP statistic at 66.179 tok/s. B23 with depth2 enabled then passed the same startup
gates at 64K, including real checkpoint compatibility. Its 12 outputs were also token-for-token identical, but median
decode fell to **59.842 tok/s**, **9.58% slower** than the depth1-inert 66.179 tok/s run. Depth2 recorded 6,816 proposals
and 4,360 accepted proposals; these counts are not comparable to depth1's 5,954/4,533 first-guess counts.

The reduced overlap outweighs the extra accepted tokens. This schedule is closed negatively and was removed from
canonical `engine/src`; B19 is the restored service. Patches and receipts remain here for mechanism reuse only. A future
attempt needs a schedule that restores useful d1/d2 overlap without rank1 suffix memory, not another run of this one.
