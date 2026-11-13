# bcs-1: the prompt halves' card-to-card exchanges as copy-engine pushes (OWN_PX_BCS)

Helper work, 2026-11-12. Patch: `/home/steve/dsv41-work/bcs/bcs-1.patch` (against 2ef2e47d6, tp107 part; `git apply --check` passes at c69a220bd).
Binary: `/home/steve/dsv41-work/bcs/bin/own_run_v41_bcs` (build105.sh flags, `bcs/build_engine.sh`).
Working tree: `/home/steve/dsv41-work/bcs/tree` (git: branch `up` = 2ef2e47d6's engine files, `master` = bcs-1).

## What it does

Opt-in switch `OWN_PX_BCS` (default 0 = off: nothing is created, every path as before). It needs `OWN_PX=1`
and works with and without `OWN_PX_BIG=1`. Only blocks that run as two halves (px_ok) change.

* `OWN_PX_BCS=1` (the one to use): every exchange of the halves' layer loop is a PUSH on the sending card's copy
  engine, queued right after its producer:
  * X1 output-a rows (+ the attention mix's partial tokens, OWN_MT_DSPLIT region xdsA),
  * X2 output-b rows, X3 expert act rows (+ the FFN mix's partial tokens, region xdsF), X4 FFN rows,
  * the block's engram rows (once per block; both layers' rows are in that one region).
  Each card's copy engine writes the card's own slice into every peer's arena at the same offsets, then writes the
  push number into each peer's copy-flag word. The reader on each card waits on its LOCAL flags with a tiny launch
  right before the reader. The compute engine no longer runs the XchgPull launches on xqs for these exchanges.
* `OWN_PX_BCS=2` (diagnostic): the same pushes, queued where px_layers queued the pull (later than the producer).
* Unchanged: the output-a pair swaps of the split head groups (XchgPair, still a pull on xqs; small), every non-PX
  block, decode steps, checks.
* FINDINGS item e: with OWN_PX_BCS the redundant second engram copy at layer 14 is gone (the rows pushed once stay
  in place; px_eng at layer 14 does nothing).

Sums and launch order of the compute kernels are untouched (copies only), so the outputs must be bit-identical.

## Mechanism

| Piece | How |
|---|---|
| copy engine list | per card, `zeCommandListCreateImmediate` on the copy-only queue group (group 1 on B70: 1 engine), `ZE_COMMAND_QUEUE_FLAG_IN_ORDER` |
| producer -> copy engine | per card an own L0 event pool (64 events, device-scope signal and wait, reused round robin). `zeCommandListAppendSignalEvent` on qs[c]'s own native immediate list (`get_native(qs[c])`, the SYCL in-order queue's list: signalled in queue order, after the producer); the copy list's first command is `zeCommandListAppendWaitOnEvents` on it, its last `zeCommandListAppendEventReset` |
| the rows | `zeCommandListAppendMemoryCopyRegion` (2D: width = the card's row bytes, height = slots, pitch = slot stride) per peer; one plain copy for one slot; the second region (ds partial tokens) one plain copy per peer |
| the flag | a 4-byte `zeCommandListAppendMemoryCopy` from a device table `tbl[i] = i` (4 MiB per card) into each peer's word `xbf + 16 c`. The copy engine cannot fill 4-byte patterns (`maxMemoryFillPatternSize` = 1 on the copy group: the fill fails with 0x78000008) |
| order data -> flag | one in-order list: the flag copies come after the row copies (the bench checks it, no barrier needed) |
| the wait | `XchgWaitB` (kernels/sycl_v41.hpp), 32 work-items on qs[c] right before the reader: item t polls LOCAL word `xbf + 16 t` until >= the push number, polls the poison word (96) in the same loop, bounded by XSPIN; on timeout poison := 1 and err[0] = 1 + t (the existing "exchange timed out" error); then a system acquire fence and a barrier. The rows are read only by later launches (no stale lines) |
| push numbers | `bseq[c]`, one per card, the same on every card (every card pushes at the same host-order places). They restart at 1 (all flag words zeroed, copy lists host-synced) at a block start when the table would run out (2^20; never in practice) |
| flags location | arena words `xbf .. xbf + 16 * 6 + 16`, after everything else (xbf rounded up to 16 floats). Each sender's word on its own 64-byte line, written only by that sender's copy engine. Separate from the XchgPull flags (words 0..96), which keep counting the pair swaps |
| end / failure | the destructor host-syncs each copy list (3 s). If one is stuck: a compute-engine rescue list per card fills poison = 1 on every card and signals all events, then 5 s more. So no spinner is left on a card when the process exits |

### The 64-byte line rule

The copy engine writes whole lines into the peer; a card's slice must never share a 64-byte line with another
card's slice of the same region (two engines writing the same line could undo each other's bytes). Every region
offset and every card's row range is a multiple of 16 floats: td/tm/te splits are in units of 16, the output-a head
groups are 1,024 rows, the ds partial tokens are 400 floats, and xdsA is rounded up to 16 floats when OWN_PX_BCS is on
(the DSPLIT slack in mt_arena_floats grows from 4 to 16 floats for it). bcs_setup checks all of it and refuses to run
otherwise.

## Hazards (why no reader sees a half-written or overwritten region)

Notation: X(h, L) = half h's exchange at layer L. Every card runs the same host order; qs[c] is in order; the copy
list is in order; a push starts only after everything queued on qs[c] before it (the event).

**Read before write (the reader gets new data).** A reader on card d runs after d's wait launch saw every sender's
flag >= the push number. Each sender wrote that flag on its in-order copy list after its rows into d. The bench
checks this ordering (no flag before its data in 6,700 rounds, see below).

**Write after read at the destination (c must not overwrite rows d still reads).** c's push of X(h, L+1) starts after
c's producer, which runs after c's wait for an exchange that d pushed after d's last reader of the region. Per region:

| Region (half h) | readers on d | c's next push into it | why d's readers are done |
|---|---|---|---|
| OA_h (output-a rows) + xdsA | P2A(h, L) mix finish, P2B(h, L) output-b | X1(h, L+1), producer P1B(h, L+1) | c's P1B(h, L+1) is after c waited X4(h, L) at P5; d pushed X4(h, L) after its P4(h, L), after its P2B(h, L) |
| OB_h (output-b rows, then FFN rows) | P3A(h, L) (X2), P5(h, L) (X4) | X4(h, L) (same layer), then X2(h, L+1) | X4(h, L): c's P4(h, L) is after c waited X3(h, L), which d pushed after its P3B(h, L), after its P3A(h, L). X2(h, L+1): c's P2B(h, L+1) is after c waited X1(h, L+1), which d pushed after its P1B(h, L+1), after its P5(h, L) |
| ACT_h (expert act) + xdsF | P4(h, L) | X3(h, L+1), producer P3B(h, L+1) | c's P3B(h, L+1) is after c waited X2(h, L+1), which d pushed after P2B(h, L+1), after its P4(h, L) |
| ENG (engram rows) | P0A at layers 1 and 14 | the next block's engram rows | the next block's producer runs after c's P5(B, last layer), after c waited X4(B, last), which d pushed after P4(B, last), after its layer-14 P0A |

**Write after read at the source (c must not overwrite its own slice while its copy engine still reads it).** c's
next producer into its own slice of a region runs after c waited for a peer's exchange that the peer pushed after
the peer waited for c's flag of the earlier push; c's in-order copy list wrote that flag after reading the slice.
E.g. OA_h: c's P1B(h, L+1) is after c's wait X4(h, L) <- d's P4(h, L) <- d's wait X3(h, L)... <- d's wait X1(h, L)
(P2A(h, L)) <- c's X1(h, L) flag <- c's copy of OA_h(L). OB_h, ACT_h and ENG follow the same chain one step later.

**Block boundaries.** Every block ends with each card thread waiting for its queue (twait / the head's read). Every
card's last push X4(B, last layer) is waited for by every peer's P5(B, last layer); so when all queues are done, all
copy lists are done too. The next block (halves or not, or decode) starts with every copy engine idle.

**Event reuse (64 per card).** Event i is reused 64 pushes later. A push waits for the queue to reach its signal;
the copy list resets the event after its copies. The copy list cannot be 64 pushes behind: within a layer each card
waits for every peer's pushes of that layer, which the peers queue only after waiting for this card's earlier
pushes, so at most a few pushes per card are in flight.

**Pair swaps (XchgPair).** Unchanged pulls on xqs. Their region (xhoM) is separate from every pushed region, and the
chain above still protects it (d's next write of its head outputs comes after d waited X4(h, L) from c, which c
pushed after the pair pull it waited for).

## What it costs on the card

Per card: the table 4 MiB (`bcs_tbl`, 2^20 words), the flag block 112 floats in the arena, 12 more floats of DSPLIT
slack, one event pool of 64 events, two command lists. No extra exchange buffers (the hazards are closed by the
dependency chain above).

## Stress bench (bench/bcs_order_bench.cpp)

Six cards, one SYCL context per card, arenas mapped by IPC, the engine's exact push form (own event on the queue's
native list, in-order copy-only list, 2D region copies, flags from the number table, event reset), the engine's
shapes at halves of 256 tokens, two alternating regions per shape (the shortest reuse distance the engine has), a
busy kernel of varying length between push and wait, then a wait launch (local flags, poison, acquire; it also reads
the first and last 16 bytes of every peer slice to catch a flag that lands before its data) and a separate check
launch that compares EVERY value of all six slices. Log: `bcs/logs/order2.txt` (2026-11-12 22:02, no barrier between
data and flags):

| shape | rounds | wrong values | timeouts | flag before data | push alone | sent per card |
|---|---|---|---|---|---|---|
| x2/x4 output-b (5,120 stride, 256 slots, 0.84 MiB x 5) | 1,500 | 0 | 0 | 0 | 137.5 us | 32.2 GB/s |
| x1 output-a (8,192, 256, head split, 1.50 MiB x 5) | 1,500 | 0 | 0 | 0 | 260.4 us | 30.2 GB/s |
| x3 expert act (2,304, 1,792 slots, 2.62 MiB x 5) | 1,000 | 0 | 0 | 0 | 442.8 us | 31.1 GB/s |
| ds partial tokens (400 floats each, 0.13 MiB x 5) | 1,500 | 0 | 0 | 0 | 21.3 us | 32.4 GB/s |
| engram rows (25,600, 1,024 slots, 16.7 MiB x 5) | 200 | 0 | 0 | 0 | 2,974 us | 29.4 GB/s |

ALL OK, kernel journal clean. (The first try, `order1.txt`, stopped at once with 0x78000008 because the flag was a
4-byte fill on the copy engine; the rescue path finished every list and the run exited cleanly. Flags are copied
from the number table since.)

Copy-engine time per layer and half at 256 tokens: X1 260 + X2 138 + X3 443 + X4 138 = ~0.98 ms, ~2 ms per layer
for both halves, on the copy engine instead of the compute engine.

## Gate arms and measurements (2026-11-12, six B70s, oneAPI 2026.1)

Binary `bcs/bin/own_run_v41_bcs`: tp106 sources (dcf06e199) + bcs-1, built with build105.sh's flags
(`bcs/build_engine.sh`, 1,243 s). The patch is now against 2ef2e47d6 (tp107 part: OWN_CK2 on by default, a one-line
default in backend_sycl_v41_mt.inc); this binary has the older default, so `OWN_CK2=3` gives the new one. That line
only touches checks of 2-3 tokens, not prompt reading. Runner: `bcs/arm.sh` (env exactly as the brief: G/TB/PL),
each run through `bcs/six.sh` under `systemd-run --user`, a pause of 2.5-3 minutes between runs. Logs and ids:
`bcs/runs/<name>.log`, summary `bcs/runs/results.txt`, wrapper logs `bcs/logs/<name>.txt` (all "journal clean").

### Correctness (OWN_PX_BCS=1, OWN_PX_CHECK=1, 3K prompt, 40 tokens, trace of 3 steps vs runs/gm64/t3k_ref)

| arm | blocks | trace | 40 ids | OWN_PX_CHECK |
|---|---|---|---|---|
| t512a: OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1 | the blocks of 512 as halves | TRACE_IDENTICAL | IDS40_SAME | 0 bad (no BAD line; counts printed at 1, 2, 4 blocks) |
| t256a: OWN_PROMPT_BLOCK=256 OWN_PX=1 | the blocks of 256 as halves | TRACE_IDENTICAL | IDS40_SAME | 0 bad (no BAD line; counts printed at 2, 4, 8 blocks) |

OWN_PX_CHECK with OWN_PX_BCS also checks, after every block, that each card's copy flag of every peer equals that
peer's last push number (every push landed, none extra) and that the pull flags did not run ahead.

### Speed (3K prompt = 3,323 tokens, OWN_EOS=-1, 256 answer tokens, OWN_MT_EU_HEAVY=0 in both arms, same binary)

Blocks of 512 as halves (OWN_PX=1 OWN_PX_BIG=1), alternating:

| run | OWN_PX_BCS | 3K read | answer (256 ids vs p3kplain) |
|---|---|---|---|
| s512off1 | 0 | 5.42 s | same |
| s512on1 | 1 | 5.02 s | same |
| s512off2 | 0 | 5.41 s | same |
| s512on2 | 1 | 5.01 s | same |

Gain: 5.415 -> 5.015 s mean, **-7.4 %** (0.40 s; 617 -> 664 tok/s). Decode after the prompt is unchanged
(95.5-97.4 tok/s in both arms; no decode path changes).

Blocks of 256 as halves (OWN_PX=1, no OWN_PX_BIG), one pair:

| run | OWN_PX_BCS | 3K read | answer |
|---|---|---|---|
| s256off1 | 0 | 5.58 s | same |
| s256on1 | 1 | 5.26 s | same |

Gain at 256: **-5.7 %** (one pair). The trace arms (TB env + OWN_PX_CHECK) read the 3K prompt in 5.03 s (t512a) and
5.28 s (t256a) with the pushes; main's tp106 gate logs of the same arms without them: 5.43 s
(runs/tg106/t3k_b512px.log) and 5.56 s (runs/tg106/t3k_b256.log).

### What is left

* The engram rows (one push per block, 16.7 MiB to each of five peers at 512, ~3 ms) are pushed at layer 1 right
  before half A's wait (OWN_ENG_LATE, the default), so most of those ~3 ms per block are not hidden: ~18 ms of the
  3K read (~0.35 %). Splitting it per half (half B's rows waited at B's layer-1 gate) would hide about half of it.
* Each push costs the host ~13-18 Level Zero appends (event signal, wait, five region copies, five flags, reset);
  the card threads stay ahead of the cards in these runs (no sign of host-bound steps in the read times).
* OWN_PX_BCS=2 (push where the pull used to be queued) is kept as a diagnostic; it was not timed.
* The pair swaps (XchgPair) are still pulls on xqs; they are small (two split head groups).

## Card memory

Read from the run logs: 31.05 GiB free per card before load; after load (with OWN_PX_BCS=1, t512a) 3.12-3.65 GiB
free per card. The pushes add 4 MiB (number table) + 0.5 KiB of arena per card; nothing else grows.

## Faults

None. Every wrapper log ends "journal clean"; no STOP; no exchange timeouts; no poison.
