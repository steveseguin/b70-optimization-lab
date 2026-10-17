# State ownership and copy schedule

## What the present receipts measure

`diagnose.py` reuses packet57's cycle attribution and hashes the 26 completed
packet61 screen receipts, timing logs and snapshot counters. It does not read
the running record chain. Counts include the 64-token incident request and
twelve 128-token requests: 1,587 generated intervals, 1,251 hits, 336 misses,
and 1,574 complete pipeline cycles in each lane. Medians below are per-cycle,
not medians of per-request means or the class-balanced headline.

| Median milliseconds | Lane A | Lane B |
| --- | ---: | ---: |
| Hit interval | 17.4563 | 17.1370 |
| Miss interval | 28.7599 | 28.6378 |
| Speculative rank0 half, hits | 13.7359 | 13.7338 |
| Rank1 half, hits | 15.4861 | 15.2107 |
| Rollback command | 0.7414 | 0.7386 |
| Corrected rank0 half | 12.5064 | 12.5130 |
| Speculative envelope minus busy time | 0.8151 | 0.8048 |
| Ordinary envelope minus busy time | 0.0330 | 0.0323 |
| Verify completion to rollback start | 0.0121 | 0.0116 |
| Restore completion to corrected-half start | 0.00154 | 0.00142 |
| Corrected-half preparation | 0.1166 | 0.1138 |
| Corrected-half enqueue loop | 3.0606 | 2.9779 |
| Corrected-half host wait | 9.0571 | 9.1692 |

Snapshot envelope-minus-busy includes preparation and position admission;
it is not isolated device copy time. Verification completion is later than
the shared verification publication. Host wait is not GPU idle. These are
existing screen observations, not new packet62 measurements.

The current capture has 975 descriptors (966 plan outputs and nine standalone
allocations), totaling 48,344,850 bytes. Confirmed redo restores 938 descriptors,
18,743,058 bytes, omitting 37 recurrent banks totaling 29,601,792 bytes.

The redo payload is: 8,388,608-byte GEMV workspace; 6,666,110 bytes of nonbank
plan buffers; 1,609,936-byte operator scratch write span; 983,040-byte layer
snapshots; 696,320-byte FP32 input; scores and probabilities at 196,896 bytes
each; 5,120-byte ordered mixture; 120-byte routes; 12-byte controls.

## Recurrent destination rotation

Active A and spare B are observable target state. A speculative step writes
into private C, preserving both A and B. On a completed hit, C becomes active,
A becomes spare, and B becomes private. On a miss, the candidate swaps back
if necessary, then its spare rotates back to B. A cancelled prefix follows the
same restoration path without an active/spare swap. No recurrent bytes need
capture or restore copies. A corrected ordinary half still writes B and
commits B/A exactly as before.

This requires a complete destination write and a distinct, unchanged input
bank. `RedoBankProof` must establish the full GDN/conv extent before the new
bank path is admitted. An unknown/partial writer fails rather than silently
using alternate bytes. The copied target kernels and BF16 stores are unchanged.

Prepared commands capture pointers by value, so changing a buffer map alone
would be wrong. Six ordered active/spare pairs are prepared during load, with
separate command vectors and binding maps. Runtime rotation chooses those
already prepared pairs. QSA launch extents remain logical state; only stale
context-bucket commands are refreshed through the original admission path.
No per-token whole-model command rebuild or allocation occurs.

The former spare can become the private reserve at a hit. Inventory therefore
names private reserves by their current role, while all target buffers and
both logical recurrent banks retain their full byte dumps. Only private
reserves, backup and copy table are zeroed at a resolved request boundary;
no committed target bytes are masked or cleared. CPU comparisons independently
require every private byte to hash as zero and compare all target buffer,
standalone scratch, host metadata and shared-stream bytes.

## Why not swap the entire write set

Memory allows more buffering on rank0, but bytes outside each writer's span
remain observable. The 8 MiB workspace and operator scratch retain historical
tails; QSA retains committed cache rows. A blanket alternate allocation would
lose those bytes, even if output tokens happened to agree. This packet limits
rotation to the fully proven recurrent destinations. It does not label full
buffering as impossible; it leaves it contingent on an exact read/write and
tail-preservation proof.

## Flat transport and bookkeeping

The original CopyEngine still validates every source, destination and extent.
The flat path copies its resulting descriptors into an owned device table.
One 256-lane workgroup handles each 4,096-byte tile; a binary search finds its
extent. Each lane copies at most 16 bytes, preserving unaligned offsets and
short tails. The CPU fixture invokes the exact same `copy_lane` function that
the SYCL kernel calls. All allocation IDs remain bound for the operation's
lifetime. Table upload completes before the kernel consumes it, and later
table reuse first drains the preceding work.

The original rectangular batch scheduled every descriptor to the largest
extent's grid. The flat schedule avoids this padding as well as reducing
submissions. New device bandwidth and launch latency remain unmeasured.

`banks-batch-overlap` removes only the immediate host wait after restore
submission. Shared-slot and host metadata restoration can run while copies
finish. Existing drains before restored device state is read still enforce
dependencies. QSA re-admission or other required drains may consume that
opportunity at a bucket boundary. The target verification, correction token,
controller ordering and error checks are unchanged.

## Memory

Packet61's 23/25 split at context 4096 has 6,172,740,440 bytes of rank0 arena
headroom; rank1 has 89,364,320 bytes (85.22 MiB). Rank1 never speculates and this
packet adds no rank1 allocation.

Rank0's third-bank allocation is 29,601,792 bytes, exactly offset by reducing
the backup from 103,607,362 to 74,005,570 bytes. The flat table adds 31,232 bytes
in either flat selection. This fits inside the existing 46,500,548-byte rank0
allocation reserve, so the inherited memory admission limits remain unchanged.
The six prepared host command maps add CPU metadata, not target weights or KV.
Actual device census and driver residency remain coordinator admission checks.
