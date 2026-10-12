# Terminal EOS strict restoration

The original implementation did not restore every physical byte after terminal
abandonment. Packet40 now implements `strict_snapshot.hpp`: a private pre-half
image restores inactive banks, overwritten intermediates, uncommitted QSA tails,
token/history controls, standalone mutable allocations and exact host metadata.
It also restores rank0's shared slot, without touching rank1 publications.
Committed active banks and valid QSA prefixes are excluded from the image, so
an illegal mutation remains detectable. Sticky failures cannot be rolled back.
Only the private image is zeroed at a quiescent boundary; target state is not
canonicalized before comparison. See the independent
[retention/token-authority review](review-retention-token-authority.json).

Current-source full-state CPU qualification is required before sealing. This
source review is not an execution result or a device performance claim. No
reduced-state exception is assumed.

## Historical finding and design assessment

The remainder preserves the pre-fix investigation and proposed design. Its
statements about an unimplemented snapshot or pending scope exception describe
the earlier implementation, not current behavior. The actual implementation
restores the image on every rollback, including a miss followed by redo.

## What is identical

Only the unchanged rank1 target output can emit a token or end a request. Rank0 receives the target-only verification publication with a release/acquire fence, stops at an actual compute launch boundary on a miss, drains every submitted event, restores the saved history and position, and reverses a bank swap only if the complete half actually swapped. A nonterminal miss then executes the actual token. The forced-miss gates compare every final plan allocation, both physical state banks, and host state against a never-speculated run; a separate archive gate checks the standalone inventory except the event counter.

Retention reads the target buffers into distinct snapshot allocations. It does not write target arithmetic or verification state, and consumed snapshot buffers are cleared. Retention on/off gates compare emitted tokens, all final plan and spare-bank hashes, and the full standalone/host inventory. These gates do not establish universal physical-byte equality at terminal EOS under timing-dependent speculation.

## Why terminal bytes can differ

At EOS there is no next actual-token half to overwrite discarded work. Retaining fixtures adds copies, reads and waits, changing when rank0 sees a miss. The number of already-submitted speculative kernels can therefore differ. These kernels can leave different bytes in the inactive recurrent/conv state bank, overwrite-only intermediate allocations, and QSA rows beyond the confirmed sequence extent. Those bytes are not committed model state, are not emitted, and cannot be consumed by a later request: request reset clears all non-weight allocations before new input.

The scheduling counter `logical_event` is a separate issue. It counts submitted operations, not model data. Ordinary model parity omits only this field from the inventory while retaining its original value and the SHA256 of the original inventory. Omitting this counter does not justify omitting a model allocation, an active bank, history, cache metadata, or a valid QSA row.

## Additional terminal control and cache finding

The differences are not limited to unnamed scratch or unused cache tails. `half_step` writes the guessed input to the rank0 plan buffer `token` and calls `prepare_token` before checking the first compute cancellation boundary. `undo` restores position, host histories and `token_history`, but does not restore the previous `token` bytes. A never-speculated EOS execution therefore need not have the same token-input control. This buffer is not the emitted-token authority, but it is part of the full final-state inventory requested by the owner.

Rollback also clears `lookup_ids` and the FP32 cache source/extent instead of restoring their exact previous values. In layer-streaming mode the host `selected` routing vector can retain the speculative final route. The existing terminal committed-state gate deliberately does not compare these fields. Its pass must not imply that all token controls or cache metadata were restored, and full terminal physical-state equality remains unresolved. The prior mini/real redo and retention receipts keep their stated scopes; this source finding does not manufacture a runtime failure receipt or invalidate a comparison they actually performed.

A proposed finalization scrub restricted to inactive banks, overwrite-only scratch and invalid QSA tails would not fix the token/control/cache differences. Restoring an exact pre-speculation image, including host-derived metadata, is a stricter alternative under review. No finalization or additional rollback behavior has been implemented.

## Exact terminal comparison

`native_mini_gate.py::committed_terminal` performs a quiescent pre-reset dump and compares rank0 position, error and active controls, token history, host PLE histories, and the active state outputs of every `gdn` and `conv` launch. It compares each `qsa_append_pool` output through the exact confirmed extent: `position` rows for full arrays and `floor(position / 4)` rows for pooled arrays. Rank1 retains the complete final-state comparison. All raw final-state and inventory hashes remain in the test's bookkeeping records; equality is not claimed for the discarded physical bytes.

The terminal test includes forced wrong speculation and target EOS for both Python and native controllers. The request reset boundary independently zeros plan allocations, spare banks, standalone controls and scratch, resets histories and caches, and clears provider request state; the persistent-pair/reset-order gates compare subsequent requests. Read the actual current gate receipts before claiming these tests passed: this note describes their defined scope and is not a replacement for execution evidence.

## Options if every physical byte is required

A complete rollback image could preserve every allocation that speculation may write, including overwritten scratch and future cache rows, and restore it after a terminal abandon. That adds memory traffic, storage and lifetime rules at each speculative half. A selective write-set snapshot could reduce the copy volume but still requires every launch class and every partial multi-pass operation to declare and preserve its exact written extent. Either changes the runtime and requires rebuilding and rerunning the CPU and device qualification chain.

A deterministic post-request scrub can make inactive allocations canonical, but then the receipt proves the scrubbed state, not byte identity to the unsanitized never-speculated execution. Resetting everything before hashing would erase the state being tested and cannot silently substitute for the requested proof. The current implementation uses neither shortcut.

No device was run and no speed is claimed by this note.

## Pre-speculation snapshot cost assessment (source only)

The retained real rank0 plan uses context 256 and a 24-layer half. Its declared plan outputs plus the host-written `token` require **40,172,372 bytes** when recurrent destinations are mapped to their inactive physical bank. This excludes the untouched active recurrent banks, weights, `active`, rank0 `next_token`, immutable `ple_metadata`, and the shared transport/pinned slab outside the existing target inventory. This is an allocation-granular conservative write set, not a proved minimum byte-range set.

| Snapshot region | Bytes |
| --- | ---: |
| 37 inactive recurrent/conv banks | 29,601,792 |
| 24 complete QSA key/value/raw/pooled allocations | 3,637,248 |
| Other plan-written allocations and token input | 6,933,332 |
| Operator scratch | 268,435,456 |
| GEMV workspace | 8,388,608 |
| Layer snapshots | 983,040 |
| Prepared FP32 input | 696,320 |
| Attention scores and probabilities | 393,792 |
| Parallel controls, compact routes, ordered mixture | 5,252 |
| **Conservative total** | **319,074,840 (304.29348 MiB)** |

These totals come from `launch-plan-rank0.json` buffer sizes and `Engine::initialize` standalone allocations. They deliberately preserve whole shared workspaces across supported dispatches; the 256 MiB operator-scratch allocation dominates. Selected kernels use only parts of it, so a proven maximum written-prefix descriptor could reduce the total substantially. It is not safe to infer that the allocation is unused merely because its category is scratch or a CPU path leaves it untouched. The selected device implementations can write scratch differently from their host equivalents. A minimal prefix implementation would itself require dispatch-specific write-footprint proof. The table is a concrete safe sizing estimate, not a completed descriptor or measured speed cost.

Capture the image after the preceding committed half has drained, before writing the guessed token, calling `prepare_token`, or installing cancellation hooks. Queue all device-to-device saves at this boundary ahead of the speculative launches on the ordered queue; no per-launch checkpoint is needed. Keep allocation IDs and pre-speculation bank mapping, both host histories, token history, lookup-id vectors, selected routes, loaded-layer state, FP32 source IDs/extents and bank parity. On terminal abandon drain first, reject sticky error, undo any completed bank swap, restore the saved physical allocation bytes and exact host metadata, then drain before any dump or release. Restoring saved IDs must not resurrect freed layer weights; layer-streaming resources need a separate lifetime check. Do not rewind event IDs or suppress fault evidence.

An allocation-granular implementation needs roughly one thousand save-copy commands per guess, even if all saved bytes occupy a single backup arena, because the source allocations are separate. At 63 guesses the conservative snapshot payload is 20,101,714,920 bytes (18.7212 GiB); this excludes restoration, device read-plus-write traffic, command overhead and any backup cleanup. This is payload arithmetic, not a throughput prediction. Host readback per guess would add synchronization and transfer costs, so a speed candidate should keep the backup on rank0's device and have the coordinator measure the actual overhead. Reserve the extra 304.3 MiB in the rank0 memory plan. New backup allocations must be retired or consistently emptied before inventory so they do not introduce a fresh unequal-state region.

Nonterminal miss handling may continue to redo and retain its existing full-state proof; restore the complete image for terminal abandon. Tests must include cancellation before the first compute launch, after every mini-model launch, after the completed-half bank swap, retained/nonretained runs, both controllers, and sampled real positions including QSA pool boundaries. All runtime binaries and dependent gates require requalification. No snapshot implementation or device measurement was performed for this assessment.
