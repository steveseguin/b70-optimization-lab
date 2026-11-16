# privmem-1: ~0.94 GiB per card of hidden card memory freed; guessing at 194K stable; first 704,773-token read (2026-11-16)

## In plain words

Guessing runs at ~194K tokens failed about 3 times in 8 with "card-to-card exchange timed out". The cause was card
memory that the start-up figure never showed. Seventeen of our index kernels carried a small per-token table (1 KiB)
inside their launch arguments and looked entries up by a number known only at run time. The GPU compiler handles
that by copying the whole argument block into private memory for every lane. The driver then reserves that private
memory for every hardware thread on the card, the first time each kernel runs, and keeps it: about 70 MiB per
kernel (35 MiB for the 16-lane ones). Over a long prompt, as longer selections came into use, this took about 0.94
GiB per card *after* the "free after load" line. Guessing starts with ~1.4 GiB less room (the draft model), so it
ran out. Now the tables live in card memory (or, for blocks of up to 16 tokens, in a form the compiler reads by
fixed positions). Same values read, same answers bit for bit.

Result: free memory now stays flat during a long read; two guessing runs at 194K passed; and the 704,773-token
document was read to the end for the first time (571.6 tok/s), then 1,024 answers written at 64.4 tok/s.

## Evidence

**pr4** (tp118, guessing, x95k prompt with room for 300,032 positions; card 2 at 0.71 GiB free after load): died at
the first prompt block with `xe 0000:43:00.0: [drm] VM worker error: -12` (out of memory), exec queue resets and
`UR_RESULT_ERROR_DEVICE_LOST`: card memory running out *during* the run. Our own fault, acknowledged in
`stable-mode/faults-acked.txt` (preflight now reads the kernel log from the newest acknowledgment on).

**pr5 -> pr6** (95,497-token prompt, free card memory after every block, `OWN_TPD_MEM=1`; card 2 = the fullest):

| | after load | after block 1 | later |
|---|---|---|---|
| pr5 plain (tp118) | 2.80 GiB | 2.36 | 2.19 (block 2), 1.89 (16K), 1.82 (32K), **1.75 (65K)**: steps of exactly 0.067 GiB = one 1,104-B/lane kernel x 32 lanes x 2048 threads |
| pr6 plain (tp118p) | 2.80 GiB | 2.61 | **2.57 at 95,488** (nothing moved 32 MiB in between) |
| pr5 guessing (tp118) | 1.41 GiB | 0.92 | 0.68 (3.5K), 0.45 (16K), 0.38 (32K), **0.31 (65K)** |
| pr6 guessing (tp118p) | 1.41 GiB | 1.17 | **flat** to the end |

Answers IDS64_SAME and guessing SAME AS the plain run in both; speeds equal (prompt 659.7 -> 660.7 / 651.5 -> 652.2
tok/s, writing 90.33 -> 90.00, guessing 150.90 -> 150.61; 64 answers each, noise level).

`privmem_check.py` (zeinfo `per_thread_memory_buffers` of the binary's device code): tp118 had 17 kernels at 30
MiB or more (`privmem-check-tp118.txt`: ten TopKSel*M forms at 69-70.5 MiB, seven index lambdas at 35-35.5 MiB),
2,872 MiB per card if every kernel ran; tp118p has none at 30 MiB or more and 1,932 MiB if every kernel ran.

**c118p** (tp118p = tp118 + privmem-1 + tpd-2, source 5d6c2ae46a; stable mode, preflight before every start):

| case | prompt | reading | writing | card 2 free after load | result |
|---|---|---|---|---|---|
| p3k | 3,323 | 678.8 tok/s | 99.14 tok/s | 3.13 GiB | IDS256_SAME |
| p10k | 10,621 | 683.9 | 96.85 | 3.08 | IDS64_SAME |
| plain, prompt 1 | 36 | - | 106.79 | 3.45 | IDS128_SAME |
| code, guessing | 82 | - | 147.33 (c117 148.24) | 2.07 | IDS511_SAME, GLOG_SAME |
| analysis, guessing | 113 | - | 163.16 (c117 166.45) | 2.07 | IDS511_SAME, GLOG_SAME |
| x95k | 95,497 | 662.2 | 91.72 | 2.81 | IDS256_SAME |
| x200k | 194,000 | 645.1 | 87.60 | 2.47 | IDS1024_SAME |
| s200k_1, guessing | 194,000 | 638.0 | **129.62** | 1.07 (0.83 all run) | IDS1024_SAME, SAME AS plain |
| s200k_2, guessing | 194,000 | 637.9 | **129.94** | 1.07 (0.83 all run) | IDS1024_SAME, SAME AS plain |
| **x700k_def** | **704,773** | **571.6** (1,232.8 s) | **64.40** | 0.72 (0.53 all run) | exit 0 (capacity case) |
| x700k_off (skip and index split off) | 704,773 | stopped at 94,720 | | 0.74 | host stall on card 3 (below) |

Guessing lost 0.6 % (code) and 2.0 % (analysis): the draft took +0.07-0.08 ms and analysis checks +0.26 ms per
round. Cause: the card-memory tables are written by a tiny launch (`LensPut`, ~8-10 us on a small step's critical
path) whenever a table changes, which in guessing is every round. **privmem-2** (tp118p 5dc319d3d5, in tp120 as
1b417c59cf): blocks of up to 16 tokens carry the table in the arguments as `LensT` (16 values read by a select chain
over fixed positions: no private memory, no launch); longer blocks keep the card-memory table (one launch per
prompt block). Gate `c120` (tp120 with the shard off) re-times guessing.

## A second, unrelated failure: a card's host thread held up for ~1.6 s (c118 10:41, c118p x700k_off 12:04)

c118 (tp118) stopped at x200k, plain answers, with plenty of card memory (1.35-1.88 GiB free on every card):
`card 0: card-to-card exchange timed out waiting for card 1` at position 157,696. The tpd-1 report showed card 1's
host thread spent **1.56 s** on the step's engram rows (other cards 0.019 s), so card 1 queued its work late and
card 0's wait (~0.9 s limit) ran out. `/proc/pressure` (`c118-x200k-mem2-excerpt.txt`) shows no long disk or memory
stall at that moment (at most 92 ms of disk and 43 ms of memory stall per 0.5 s), so most likely the time went inside
the driver (the copy or launch calls). The host ran with ~200 MB truly free all along: the engine holds ~6.5 GB of
its own memory from load on (`pr6-smaps-plain.txt`: 3.95 GB anonymous mappings + 2.6 GB heap; flat after load, not
per context) plus ~3.8 GB of cached engram-table pages (the engram tables are the 135 GB shard 00006, read by
mmap). tpd-2 (in tp118p) now splits each card's engram time into the copy + decode calls and the host's row reads.

It happened again in c118p's x700k_off case, at position 94,720, and tpd-2 answered: card 3's host thread spent
**1.661 s** on the block's engram rows, of which **0.001 s** in the copy and decode calls; the other five cards
0.024-0.032 s. So the time is not in the driver: it is the host thread reading the rows. But the other cards read
the same rows (each card reads a sixth of them first, then copies all of them) in 0.03 s, so the disk had them;
card 3's thread was held up on the host itself: scheduling, a lock or memory reclaim. That second the host dropped
440 MB of page cache (`c118p-x700k_off-mem2-excerpt.txt`: Cached 3,209 -> 2,771 MB, MemFree ~200 MB). Card 0 waited
for card 3 in its exchange spin (~0.9 s limit) and gave up.

**eng-gate-1** (tp120 72c9b8acce, `OWN_ENG_GATE`, default 1 = blocks): after its engram reads each card thread
waits on the host until every card thread has read its rows, before it launches anything past layer 0. A late host
thread then holds all cards' launches back on the host, where there is no time limit, instead of letting the peers
run out their device spins. Same launches in the same order, same values. **tpd-3** (same commit) adds to every
slow-block line the share step's time, the thread's major/minor page faults, its voluntary/forced context switches
and the gate wait, so the next stall shows which of these it was. Gate `c120` ends with this x700k_off case.

## Files

- `pr4-*`, `pr5-*`, `pr6-*`: summaries and logs; `pr6-smaps-plain.txt`: the engine's host memory map 150 s in.
- `c118-summary.txt`, `c118-x200k.log`, `c118-x200k-mem2-excerpt.txt`: the host-stall stop.
- `c118p-*`: the gate (summary, marks, logs of the long cases, x700k_def's 1,024 answers, the x700k_off stop and its
  host-memory excerpt; mem2.txt itself is 1 MB, not copied).
- `privmem-check-tp118.txt`, `privmem-check-tp118p.txt`, `privmem_check.py`: per-kernel private memory.
- Scripts: `pr4.sh pr5.sh pr6.sh c118.sh c118p.sh build118p.sh chainq118c.sh chainq118p.sh hold119.sh chainq119b.sh
  bench119.sh kvb1.sh c118q.sh build118q.sh chainq119c.sh chainq120.sh chainq120b.sh build120.sh kvb2.sh c120.sh
  ckvs2.sh tlx1.sh tlcmp.py`. Source: worktree `/home/steve/dsv41-work/tp118p` (069121f625 privmem-1, 5d6c2ae46a tpd-2,
  5dc319d3d5 privmem-2).
