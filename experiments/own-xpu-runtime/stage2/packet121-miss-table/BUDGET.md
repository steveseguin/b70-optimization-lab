# Packet121: the miss interval

Existing receipts only. `attribute.py` joins all commands overlapping each of
the 252 misses in the first 99 intervals of twelve cold requests. It retains
every command and every outside-command span in
[`evidence/miss-intervals.json.gz`](evidence/miss-intervals.json.gz), with the
input hash and ledger inventory in [`evidence/budget.json`](evidence/budget.json).
The source is the lane-A first p104b production control: packet97 + tile16,+**not a measurement of the packet118 implementation prepared here**.

There are 936 hits at 15.173465 ms and 252 misses at 26.088644 ms. Misses use
31.6428% of measured interval time. The requested 0.21 multiplier is rounded;
the exact fraction is 252/1188 = 0.212121. The arithmetic oracle is
`iq3-p49-split32-v1`. Packet114's roughly 0.785 acceptance is a separate
prefix/runtime identity and is not substituted into these receipts.

| Rank | Command or outside-command time | Events | Mean ms per miss | Dependency / contents |
| --- | --- | ---: | ---: | --- |
| 0 | R: rollback/restore | 252 | 0.549849 | Starts alongside rank1 draft. Validates and drains speculation, restores device bytes and host metadata. |
| 0 | C: corrected target half | 252 | 11.878631 | Must follow R; normal target arithmetic for the verified token, layers 0–23. |
| 0 | Accept corrected half | 252 | 0.000232 | Commits the verified state. |
| 0 | A: next speculative half | 252 | 12.855727 | Follows completed draft and correction; races rank1 B. Includes a new snapshot. |
| 0 | Outside all commands | — | 0.804205 | Dependency waits and control; not a GPU-idle measurement. |
| 1 | D: current draft | 252 | 1.772728 | Uses the already verified token and preceding committed target state; overlaps R and part of C. |
| 1 | B: target half/head | 252 | 13.647039 | Requires corrected rank0 streams; layers 24–47 and full head in this measured identity. |
| 1 | Accept | 252 | 0.000223 | Commits its target result. |
| 1 | Outside all commands | — | 10.668655 | Mostly waiting after D for R+C. No further rank1 model command is present during that wait. |

Each rank's commands plus its outside time sum to 26.088644 ms. The ranks
overlap: never sum the two ranks. The previous wrong-token half finished by
the starting emission and must not be charged again. The next half is A.

`miss = max(D, R+C) + max(B, A+start_offset) + gap`, with mean residual
0.013125 ms. Ready-to-rank1 is 0.004354 ms, draft issue 0.006643 ms and final
race-to-emission 0.000999 ms; these are already inside the residual.

Transfers are inside those command envelopes. The rank0 stream readback,
shared-memory handoff and rank1 stream upload transfer 4×2560×2 = 20,480
bytes per half. Snapshot capture/restore additionally use a descriptor upload
and one flat copy kernel apiece. The retained source-derived restore inventory
is 19,025,640 bytes after the already qualified 29,601,792-byte spare-bank
omission: workspace 8,388,608; other plan buffers 6,948,692; scratch 1,609,936;
layer snapshots 983,040; FP32 input 696,320; scores/probabilities 196,896 each;
mixture 5,120; routes 120; controls 12. Capture is 48,627,432 bytes. These
byte counts come from [packet88](../packet88-miss-path/MISS.md); they are
source/receipt inventory, not newly timed subcommands. The host also restores
the 65,536-byte shared slot, history, lookup/FP32 cache metadata, bank parity
and both prepared launch extents. The current receipts do not separately time
DMA, the flat copy kernel, or individual GPU operators. Unknown times stay
unknown; the packet77 sampled class estimates are not a current command sum.

## Ranked exact levers

Savings below are **test hypotheses, not measurements or predictions**. No
retained timer separates the proposed pieces, so no evidence-based precise
speed ordering is possible. Rank uses the stated central screening scenario
and implementation/proof feasibility. Positive numbers mean time saved:
`0.21 × miss_saving − 0.79 × hit_cost`. All can lose; the upper bound for any
restore-only idea is 0.549849 ms/miss (0.115468 ms/step at rounded 0.21).

| Rank | Exact change | Screening scenario: miss saving / hit cost, ms | Weighted saving, ms/step | Decision |
| --- | --- | --- | ---: | --- |
| 1 | Reuse the capture descriptor table in reverse for restore | 0.10 / 0.005 | 0.01705 | Prepare one runtime-switchable candidate. Bounds 0–0.20 saving, 0–0.02 cost; actual sign unmeasured. |
| 2 | Prepare corrected token's host lookup payload while restore completes | 0.04 / 0 | 0.00840 | Deferred. The entire rank0 prepare timer is only 0.104678 ms; payload staging must avoid the upload/drain and mutable lookup metadata until restore completes. |
| 3 | Aligned 16-byte restore loads/stores with exact byte tails | 0.02 / 0 | 0.00420 | Deferred. Restore kernel time is missing and compiler may already vectorize; inspect code generation before any build campaign. Keep capture unchanged. |

1. The new table path retains the original CopyEngine admission on every
   restore, including physical pointer and extent checks. Disjoint capture
   descriptors are partitioned into ordinary and deferred-bank ranges without
   changing backup offsets. A reverse kernel reads the same table and copies
   exactly the admitted range. Redo skips the existing proved bank suffix;
   an abandoned redo copies that suffix before any observer. No new allocation,
   omitted byte, response cache, changed float operation, or verifier change.
   Unlike packet62's flat batching, this removes the second table upload and
   table reconstruction. Unlike packet88's rejected BCS overlap argument,
   it changes actual work on R; R and D already overlap. Hit cost is the
   descriptor partition/cache bookkeeping and must be measured, not assumed zero.
2. This is immutable corrected-token embedding/PLE host staging on rank0,
   not rank1 draft relocation, a second speculative depth, or issuing the
   corrected kernels against unrestored state. Current `prepare_token` owns
   mutable history/cache fields and drains during upload, so a future change
   needs separate staging plus cancellation/abandonment proof. It cannot save
   the 2.74 ms enqueue timer: that overlaps GPU execution. Rank1's ordinary
   input preparation is already nearly empty and depends on corrected streams;
   moving that ahead offers no material supported budget.
3. A copy-only transport change preserves each byte and address. Explicit
   wide accesses are legal only for fully aligned, in-range 16-byte chunks;
   odd leading/trailing bytes retain the original loop. It differs from
   changing the arithmetic vector width, reducing state, or reopening a
   batching/geometry sweep. Without isolated kernel time, the small scenario
   does not justify a campaign yet.

Double-buffering arbitrary scratch/workspace is **not ranked as an exact
ready lever**: canonical tails, terminal rollback and prepared pointers still
need a complete ownership proof (packet45 SPEED1 / packet62 / packet88).
Skipping the remaining bytes because redo overwrites some is closed. So are
draft-on-rank0 (packet79 lost 1.3–2.3%, misses +2.1 ms), depth-two speculation
(packet66/71 family), and reuse of the wrong token's layer outputs. Every
target layer depends on changed embedding/PLE inputs. The next-step draft
also needs rank1's as-yet-uncomputed corrected final state/token; rank1's
10.67 ms wait is not sufficient input readiness. Weight/history residency and
prepared commands already exist. No closed mechanism is reopened here.
