Provider bulk-reset transaction component (isolated; unapplied)

Result: bounded CPU tests passed with the actual production Owner, Sequence,
Prompt, immutable suite, v2 descriptor and provider publication layouts. Seven
cases cover prior bulk replay and prior recursive close, default-off admission,
private-zero failure, changed allocation identity, cold-byte failure and receipt
failure. After successful reset new bulk replay succeeds; after any partial reset
failure Owner stays poisoned. Existing legacy reset still refuses bulk reuse.
One initial test string-generation compile error is retained, as is the passing
six-case run before adding the seventh closed-stream case. No model or GPU ran.

Scope: two source files, overlay only. owner.hpp adds a separately named explicit
bulk transaction; the old reset function and its !bulk_used guard are unchanged.
reset_transaction.hpp composes Suite::Prepared, actual retained Owner reset and
private zeroing, actual inventory equality/cold-byte callbacks, installation of
the next authenticated Prompt, complete provider shared-map invalidation and a
receipt callback. A fresh Header is copied only after the receipt succeeds;
both bulk_used and bulk_closed reopen only after the completion returns. Wire
command sequence is supplied by the authenticated descriptor, never restarted.
Publication map extent must equal the existing wire::shared_bytes exactly.

This is not a complete native reuse implementation. It cannot be enabled safely
in isolation, and neither source is integrated into the canonical runtime.

Remaining blockers, in execution order:
1. Add actual startup suite admission to target/provider argv and source pins.
2. Native target persistent_reset must stage its new bulk_prompt from the same
   selected authority, use existing ring.reset/device zero/allocation checks,
   reset replay queues, clear its entire own target and four-slot bulk publication
   maps, install prompt, rotate output/traces and seal honest cold-byte receipts.
3. Provider runtime must call this component with the real private-image upload,
   actual live allocation identity inventory and an actual cold bundle comparison;
   rotate both bulk traces, preserve read-only target peer inode ownership, and
   emit the durable receipt. Generic callbacks are integration obligations, not
   evidence of GPU zeroing. The CPU gate uses real synthetic retained arrays.
4. The controller must quiesce ALL target/provider owners before ANY map cleanup,
   wait every reset ACK plus receipt, verify matching epoch/request/prompt and
   allocation identity, then permit OP15/OP28. A partial failure poisons the whole
   request; no retry/reset recovery. No barrier is claimed by this component.
5. Gate real A→B→A with cold canonical source-map+byte equality and repeated-A
   final full-state equality before one-process twelve-task qualification.

The existing v2 descriptor and immutable-suite overlays are prerequisites; apply
those isolated patches first if this component is later integrated. No target
reset guard or controller refusal is weakened by candidate.patch.

CPU build from experiments/own-xpu-runtime:
  nice -n 19 taskset -c 8-15 g++-13 -O2 -std=c++20 -Iresearch/pp4-review-2026-10-28/dedicated-reset-candidate/provider-transaction/overlay -Iresearch/pp4-review-2026-10-28/dedicated-reset-candidate/immutable-suite-prerequisite/overlay -Iengine/src -Iengine/src/pipeline/ring -Iengine/planning research/pp4-review-2026-10-28/dedicated-reset-candidate/provider-transaction/test_transaction.cpp -lcrypto -o /dev/shm/sc117-provider-reset-component-20261028-r3
  nice -n 19 taskset -c 8-15 /dev/shm/sc117-provider-reset-component-20261028-r3 /dev/shm/sc117-provider-reset-component-fixture-20261028-r3
Use fresh output paths for any deliberate future test; no automatic retry.
