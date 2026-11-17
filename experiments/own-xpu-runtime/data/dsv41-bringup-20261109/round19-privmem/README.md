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

## c120: tp120 gated (2026-11-16 12:50-13:25)

tp120 (fe2eae1ab2) = tp118p + privmem-2 + kvshard-1 and its push form (opt-in) + eng-gate-1 + tpd-3 + eng-warm-1 /
eng-spread-1 (opt-in). One-card benches first (`kvb2-summary.txt`): the push form's test PASS (54 cases; its four
launches 233 us against KvGather's 447 us at M 256 on one card), the kvshard-1 benches PASS. Then c120, 10 fresh
starts, every one identical to its reference (`c120-summary.txt`):

| case | reading | writing | note |
|---|---|---|---|
| p3k / p10k / plain | | | IDS256 / IDS64 / IDS128 SAME |
| code, guessing (x2) | | 147.21 / 147.51 tok/s | c118p 147.33, c117 148.24; GLOG SAME |
| analysis, guessing (x2) | | 165.81 / 165.77 tok/s | c118p 163.16, c117 166.45: privmem-2 took back the LensPut cost |
| x95k | 661.9 tok/s | 91.37 | |
| x200k | 645.2 | 87.59 | IDS1024 SAME |
| x700k, skip39 + idxsplit off | 559.3 | 58.79 | IDS1024 SAME as c118p's x700k_def (64.40 tok/s with idxsplit on) |

No slow block this time, so the gate never had to hold anyone; it cost nothing measurable (x95k reading 661.9 against
662.2). The engine source is on main as e74ba9f8b5.

tpd-3's new summary line, answer steps (per step and card): x95k 22.8 minor page faults and **5.2 sleeps** inside the
engram reads (484 us); x200k 18.3 and 4.2 (459 us); p3k 19.2 and 2.2 (140 us). The sleeps are waits for the disk.

## Where long-context READING time goes (tlp2, 2026-11-16 15:03-15:09, tp122)

Prompt-block timelines (two 512-token blocks, every card) at the start of the 3K read and at ~189K of the 194K read
(`tlp2-cmp-p3k-x200k.txt`). Card 2's GPU time per block: **733 ms at 3K, 821 ms at ~189K (+89 ms)**, of which
**`IndexerScoreBM` +65 ms** and `IndexerScoreBCM` +9 ms (the candidate-only layers, fixed 16,384 rows per token);
the selects together ~+3.5 ms, the sparse attention +2.8 ms. So the reading cost that grows with the context is the
index scores of layers 2 / 8 / 14 (half the positions) and 20 (all of them): each card scores its ~43 tokens of a
half against every row. The kernel runs at ~44 % of the cards' FP32 instruction rate: its sums are a fixed order of
separate multiplies and adds (the build has `-ffp-contract=off`), so neither fused multiply-adds nor the matrix
units can give the same bits; the room is in the memory side (each token reads all 256 B key rows itself) and the
per-group query loads. idxrp-1 (tp123, opt-in, `test_index_score_px` checks it bit for bit): the existing
4-rows-per-item form (`OWN_IDX_RP`, +2.4 % reading at 95K in round 18 but never used for prompt halves) and the
groups numbered row group first (`OWN_IDX_RMAJ`: the tokens of a row group run together and share the key rows in
the caches).

## 1M: the engine reads the far context correctly (ck1m2, 2026-11-16 23:44 - 2026-11-17 00:37, tp125 + switches)

`ck1m2-summary-partial.txt` (OWN_KV_SHARD=1 OWN_KV_DEDUP=1 OWN_ROPE_DEV=1):
- **x700k_ks: identical to the reference made without the shard** (1024 answers, 704,773 tokens): kvshard + dedup
  exact at 704K (ckvs2 had checked kvshard to 200K). Read 578.3 tok/s (591.7 without the shard), writing 87.55.
- **x1mq: the 1M prompt with the task repeated after the document (993,210 tokens): the answer gives the planted
  code 7194-KESTREL (2 % into the document, ~970K tokens before the question) and a sensible five-rule summary**
  (`ck1m2-x1mq-text.txt`). Read 550.5 tok/s, writing 85.68. So x1m_a's answer, which ignored the task stated only at
  the start, was the model (2-bit weights, near its 1,048,576-position limit), not the engine: for prompts near 1M,
  put the question at the end.

### x1m_b did not load: a start race on host memory (hostfloor-2)

x1m_b (dtopk + skip39 off, against x1m_a) ended 7 s after its start, before any card work: "host MemAvailable fell
below the floor during upload". mem.txt: 13.7 GB at the start, AnonPages +5.2 GB while the six contexts' kernels
load, then the runtime's post-build spike (~2 GB for a second or two) fell inside the upload's first seconds: 1,638
MiB sampled at 00:36:40.2 (floor 1,600), back to 6.1 GB 0.5 s later. x1mq's start dipped to 1,906 the same way and
passed. Fix in the source (0e832319e5, from tp127): a dip during the upload pauses the copies up to 15 s (nothing is
allocated meanwhile) and prints "hostfloor-2: ... paused N times"; a dip that does not pass still ends the load.
ck1m3 retries such a start once after 30 s (tp126 has no pause).

### Next: guessing at 1M needs ~0.2 GiB more on card 2 (ck1m3)

The draft costs 1.40 GiB per card (s200k vs x200k: 183.6 vs 175.1 GB uploaded; its window ring is 128 rows, so no
context term). At 1M card 2 had 1.44 GiB free after load (x1m_rd), card 5 1.62; the load guard keeps 384 MiB. tp126's
idxrows-2 gives ~0.16. Card 2 holds the q_b / output-a rows of both attention layouts (whole groups for one-token
steps, 12 heads for prompt blocks: heads 16-35 = 2.5 groups, ~0.19 GiB per half group). ck1m3: (1) hl232 = prompt
heads 3,3,2,3,3,2 (card 2: heads 16-31, 2 groups), A/B at 3K / 10K, then s1m (1M + guessing) with it; (2) m1 =
the same split for every step (`OWN_TP_HEADS_MIN=1`: no second layout, card 2 / 5 hold 8 heads), exactness + speed
at 3K and in guessing, used for s1m_m1 only if s1m is refused for card memory.

## c125: kvdedup-1 and exact ropedev-1 gated (2026-11-16 22:34-23:44, tp125 = 3c77277c87)

`c125-summary.txt`: **8 fresh starts identical to their references.**

| case | switches | result |
|---|---|---|
| p3k_dd | kvshard check mode + dedup | ALL SAME (every staged row = the full mirror), 91.0 x fewer staged rows |
| p3k_dd32 | the same, tail 1024, chunks of 32 rows (all six owners push) | ALL SAME |
| x95k_rd | rope fill on the card | identical; read 665.1 tok/s; 0 fix-ups below 96K positions (0.1 s) |
| x95k_dd | kvshard check mode + dedup | ALL SAME over 389.7M entries; 12.8 x fewer rows (10,142 distinct per half list) |
| x200k_rd | rope fill on the card | identical; read 650.4 tok/s, writing 95.69 |
| x200k_dd | kvshard + dedup | identical; **read 635.8 tok/s** (563.3 without dedup, 650.4 without kvshard); 10.1 x fewer rows; card 0 out **736 -> 61 GiB** |
| x700k_rd | rope fill on the card | identical (704,773 tokens); read 591.7 tok/s, writing 89.63 |
| x1m_rd | kvshard + dedup + rope fill | identical to x1m_a (993,166 tokens); **read 500.3 -> 550.8 tok/s**, writing 86.49; the 2 rope fix-ups at 887,541 / 889,359 as the bench found; 7.4 x fewer rows |

Attach trace (`faults/attachtrace-20261116-d.txt`, uprobe on urEnqueueUSMMemcpy + kprobe dma_buf_dynamic_attach): in
the rope-fill cases no 8 MiB rope copy and no dma-buf attach after the first minute (the 6 / 44 / 61 rope-sized copies
are the load-time compare reading each window back once); attaches only at start (~250) and at exit (~75). The cases
without the rope fill still copy the window from host memory mid-run (x200k_dd: 92 copies after the first minute).
Next: tp126 = both on by default + idxrows-2 (the two halves share one region of index score rows, ~172 MB less per
card at 1M), gate c126.

## tp124 gated, the rope bench, and two changes for tp125 (2026-11-16 21:26-22:15)

**c124** (`c124-summary.txt`, tp124 = b7a16b5e7e: idxrp-1 on by default, hostfloor-1, ropedev-1 opt-in): 6 fresh
starts identical (p3k, plain, guessing code 147.93 / analysis 166.13 tok/s, x95k, x200k). x95k read 663.2 tok/s,
writing 95.50; x200k read 651.4 tok/s, writing 95.33.

**tsx2** (`tsx2-rope.log`): the rope window computed on the card in double differs from the host's glibc tables in
**2 of 134,217,728 floats** over 1,048,576 positions (base p 887,541 slot 5 sin; yarn p 889,359 slot 20 cos; one
float step each). Not exact, so ropedev-1 was not tried in c124. tp125 (7b06b0b089) makes it exact by
construction: at load every window of [0, max_seq) is computed on a card and compared with the host's own
`rope_fill`; the differing floats become fix-ups (`RopeFixD`) written after every refill.

**kvdedup-1** (tp125, 3c77277c87, opt-in `OWN_KV_DEDUP=1`; design in `kvshard/README-push.md`): with memory
sharing every token of a 256-token half staged its own copy of its 512 listed rows (131,072 rows, 128 MiB per half
and index layer); at 194K card 0 pushed 736 GiB to its peers. Now each distinct row is staged and pushed once and the
slot lists name that copy (the attention reads the same bytes). Gate c125: check mode at 3K and 95K, 194K, 1M.

**ck1m2 first try** (`ck1m2-first-summary.txt`): x700k with sharing stopped in the weight upload, host
MemAvailable 1 MiB under the 2048 MiB floor. Host page tables grow ~15 MB/s during every upload (to ~0.6 GB) and
sharing adds ~1 GB of host memory not visible in the usual counters (200K after the upload: 3,465 MiB with sharing,
5,104-5,432 without). The long sharing cases now use a 1,600 MiB floor (the owner-approved research guard).
Queue chainq131: build tp125 -> c125 -> ck1m2 -> lp1p, ab2p, tm1p.

## First ~1M context (ck1m, 2026-11-16 20:51-21:25, tp123 + idxrp switches, OWN_KV_SHARD=1)

**ckvs2 first** (`ckvs2-summary.txt`, 20:08-20:38): the kvshard push form (every card keeps only its share of the
compressed KV rows; prompt halves push rows on the copy engines, the rest pulls) **12 fresh starts identical** to
their references (3K / 10K / 95K / 200K, check mode, guessing at 194K). Costs reading time: 95K 659.5 -> 568.1 tok/s,
194K 645.3 -> 563.2; writing unchanged (93.6 / 91.8 tok/s); guessing at 194K 124.52 tok/s, the same answers.

**x1m_a** (`ck1m-summary.txt`): the 1M prompt (`mk1m.py`: the x700k template around a longer document, the code
planted at 2 %) **993,166 tokens read on the cards in 1985.3 s (500.3 tok/s), then 1024 answer tokens at 85.80 tok/s**;
no fault; card free memory 1.2-1.7 GiB, host MemAvailable ~3.6 GB. The first start (20:39) was refused before the
upload: host MemAvailable under the 2560 MiB floor in the runtime's start-up spike (driver counters: 2.2 GB of system
memory for ~1.3 s after the kernels are built); the floor for the 1M cases is 2048 and tp124 waits out the spike.
**But the answer (`ck1m-x1m_a-text.txt`) never sees the task at the start of the prompt** ("Read this document. First
state the access code ..."): it describes the end of the dump and finds no task, while every 700K run with the same
template quotes the task and the code (7194-KESTREL). Not settled: the engine past 704K / with kvshard, or the model
near its 1,048,576-position limit. ck1m2 (queued): x700k with kvshard against the 700K reference (exact?), the 1M
prompt with the task repeated after the document (`x1mq`), and the second select path (dtopk off, skip39 off) against
x1m_a. x1m_b did not start (the same floor).

## idxrp-1 gated (tsx1 18:45 + c123 18:46-19:23, 2026-11-16, tp123 = a9a9944a3e)

`test_index_score_px` (one card, one card's 43 tokens of a half, `tsx1-idxpx.log`): every variant's scores bit for
bit equal to `IndexerScoreBM`'s in all 10 cases (PASS). ms, min of 5:

| ratio | rows | BM | BM rmaj | R2 | R2 rmaj | R4 | R4 rmaj |
|---|---|---|---|---|---|---|---|
| 1 (layer 20) | 95,000 | 5.94 | 5.46 | 5.21 | 4.74 | 5.34 | 5.31 |
| 1 | 705,000 | 50.09 | 45.70 | 43.80 | **39.46** | 42.75 | 40.20 |
| 1 | 993,000 | 70.64 | 63.83 | 60.66 | 54.85 | 59.17 | 55.84 |
| 2 (layers 2/8/14) | 705,000 | 25.01 | 22.94 | 22.36 | 19.68 | 21.54 | 20.32 |

Picked: `OWN_IDX_RP=2 OWN_IDX_RMAJ=1` (-21 % at 705K). c123 (`c123-summary.txt`): 8 fresh starts identical to their
references (p3k, plain, spec code / analysis, x95k with the dtopk default, x200k with and without the pick, x700k with
it). **705K read 571.6 -> 591.1 tok/s** (c118p x700k_def 1232.79 s -> 1192.26 s), writing 89.72 tok/s, 1024 answers
identical; 194K 645.3 -> 651.5 tok/s.

## Host events 2026-11-16 and what changed

* **15:15:50 self-reset** in ckvs2's "plain" start, ~26 s in = the weight upload (README in
  `dsv41-work/faults/reset-20261116T1515/`): BERT CPU 6 bank 5 bea0000000000108, ADDR = `pci_conf1_read+0xe4`
  (a core stuck in a PCI config read), reset reason "data fabric sync flood". 80 six-card starts in stable mode before it.
* **17:17 freeze, idle** (2 h after that boot, nothing running, no BERT): the links were back at Gen5 (the session died
  with the host, nothing re-applied Gen4). The only other idle hang (11-14 10:53) was at Gen5 too.
* **Boot unit** `b70-gen4-boot.service` (`b70-gen4-boot.sh` here): at every boot, after the six cards are bound,
  Gen4 x16 on the six root links and the cards' audio functions + their bridges kept awake (owner OK for every boot).
* **Config-read trace** (bpftrace on `pci_conf1_read` / `pci_mmcfg_read`, 20:07-): during a run the only steady
  conf1 reads were the kernel's PME scan of the six card bridges 02/22/42/82/a2/e2:02.0 (+ USB 45:00.4), one per
  device per second; after audio-awake (20:28:22) only the USB one is left. Run starts: ~500 mmcfg reads
  (`pci_p2pdma_distance_many` from dma-buf attaches) in the first ~5 s, before the upload. **Every run past ~50K
  tokens attaches again ~107 s after its start, mid-prompt** (~120-130 reads): dma-buf imports by the runtime inside
  `ur_command_list_manager::appendUSMMemcpy` (the card threads, 5 to 10 per card), i.e. the first copy of some
  peer pointer. Being moved to the start.

## c122: dtopk-1 gated (2026-11-16 14:08-15:02, tp122 = tp121 ac7d505ac5, built with `-exclude_ir`)

dtopk-1 (`dtopk-README.md`): at one-token steps past 32,768 index rows, each card picks the top 512 of its own share
of the scores, the six candidate lists are exchanged, and every card merges them. The pick is the same as from all
the scores at once because the order is total (score, then position); no score rows travel between cards any more.

1. One card, `test_dtopk` (`dtb1-*`): **PASS (441 cases)** incl. ties, +0/-0, -inf and NaN at 194K / 352K / 705K.
2. Six cards, `OWN_IDX_DTOPK=2` (on + the old selects into shadow buffers, compared on the card): 10,710 lists at 3K
   (thresholds lowered to 513), 7,650 at 95K, 30,690 at 194K: **0 differ**; answers identical.
3. On (`OWN_IDX_DTOPK=1`), answers identical to the references:

| context | writing before | writing with dtopk-1 | reading |
|---|---|---|---|
| 3K (below the threshold: off) | | 99.75 tok/s | 677.4 tok/s |
| 194K | 90.94 (same binary, `=0`) | **95.85** | 645 |
| 388K | 76.90 (tp115, lc2) | **92.40** | 613.8 |
| 705K | 64.40 (c118p) | **89.68** | 571.7 (c118p 571.6) |

Writing now loses only ~10 % from 3K to 705K (it lost ~35 %). Kernel code against tp120 (`zebin-tp120-tp122.txt`):
every shared kernel the same size, differing in 8-11 bytes (a build stamp; tp118p -> tp120 had real changes), plus the
new kernels; the images shrank from 250.3 to 196.7 MiB (no SPIR-V). `malloc_trim` after the load frees ~170-210 MiB.

## ew1: the drive kept awake (2026-11-16 13:25-13:44, tp120, x95k plain, 256 answers each, all identical)

| run | writing | engram rows per step and card | reading |
|---|---|---|---|
| base / base again | 91.59 / 91.46 tok/s | 478 / 489 us | 661.3 / 661.1 tok/s |
| `OWN_ENG_WARM=1000` | **94.15** | **114 us** | 661.3 |
| `OWN_ENG_SPREAD=1` | 91.56 | 529 us (the requests now count here) | 661.2 |
| both | **94.61** | 153 us | 660.9 |
| both + `OWN_ENG_GATE=3` (the gate on one-token steps too) | 94.36 | 154 us | 661.0 |
| code guessing base / both | 147.58 / 147.70 | | |

Writing +3.4 % at 95K with both, for 9.5 MiB of 4 KiB reads over the answers; nothing changes in what the engine
computes. Both are on by default from tp121 ac7d505ac5 (tp122). The gate on one-token steps costs ~0.25 % and no
answer-step stall has been seen, so it stays opt-in.

## Host memory: what the 6.2 GB is (`hostmem-FINDINGS.md`, a helper's read-only study)

~4.7 GiB of the engine's ~6.2-6.9 GB anonymous host memory are the GPU runtime's copies of our kernel images: per
SYCL context (one per card) three copies of every image plus one of its SPIR-V. Verified byte-exact for the two
biggest per-card mappings (401,972 kB = 3 x image 9 + its SPIR-V; 196,440 kB = 3 x image 10), and they appear during
`get_kernel_bundle`. Every MiB of kernel image costs ~18 MiB of host RAM. Next build (tp122): ocloc `-exclude_ir`
(no SPIR-V in the images: ~1.3 GiB), `h_engm` only when it is read (144 MiB), `malloc_trim(0)` after the load.
Later: compile out kernels production never launches.

## Where long-context writing time goes (tlx1, timelines of answer steps 20-27, tp118p)

Writing slows from 99 tok/s at 3K to 87.6 at 194K and 64.4 at 705K (c118p). Per-launch GPU time per answer step
(`tlx1-cmp-p3k-x200k.txt`, made by `tlcmp.py`; the timeline files themselves are 5 MB each and stay out of git), card
2, 194K against 3K: busy +1.11 ms, of which the index selects +0.58 ms (`TopKSelQ<96>` x3 0.24 ms, layer 20's rows
select `TopKSelR` 0.32 ms: one work-group over every row), the gathering of every card's scores +0.21-0.28 ms
(`XchgPull`, 7 pulls per step against 3), candidate scoring `IndexerScoreBC` +0.15 ms. And outside the GPU time: each
card's GPU sits **idle 375 us per step** waiting for the host's engram rows (end of layer 0 -> the rows' decode 286 us,
between the two engram layers 89 us); at 3K the same read hides under layer 0. The 388K timeline run was stopped by
the third host-thread stall of the day (card 1, 1.27 s at position 59,392), before eng-gate-1 existed.

Two levers follow:

1. **dtopk-1** (in writing, worktree tp121): every card picks the top 512 of its own sixth of the rows and the cards
   merge 6 x 512 candidates, instead of every card gathering every score and searching all of them alone. Exact by
   construction (the order "score descending, lower row first" is total, so the global top 512 is inside the union
   of the parts' top 512). At 705K the four split layers search 350K-705K rows each with one work-group today.
2. **The engram rows' disk reads.** CPU bench `madv.c` / `madv2.c` on the engram shard (48 cold rows, as one answer
   step): back to back 90 us of requests + 153 us of waiting; after a 10 ms pause 90 + 376; after 30 ms 86 + 649,
   also with the CPU kept busy, so it is the **NVMe drive's power state**, not the CPU's; after a 10 ms pause with one
   4 KiB read every 1 ms, 95 + 149. Answer steps are 10-16 ms apart and ~34 of a step's 48 rows come from the disk at
   194K (137.7 MiB read in 1,024 steps). **eng-warm-1** (`OWN_ENG_WARM=1000`: one 4 KiB O_DIRECT read of the shard
   every 1 ms during the answers; no system setting changed) and **eng-spread-1** (`OWN_ENG_SPREAD=1`: the card
   threads ask for their share of the rows at step start, not the main thread for all 48, ~90 us, before it wakes
   them) are in tp120 fe2eae1ab2, default off; A/B `ew1` after the gate `c120`.

## Files

- `pr4-*`, `pr5-*`, `pr6-*`: summaries and logs; `pr6-smaps-plain.txt`: the engine's host memory map 150 s in.
- `c118-summary.txt`, `c118-x200k.log`, `c118-x200k-mem2-excerpt.txt`: the host-stall stop.
- `c118p-*`: the gate (summary, marks, logs of the long cases, x700k_def's 1,024 answers, the x700k_off stop and its
  host-memory excerpt; mem2.txt itself is 1 MB, not copied).
- `privmem-check-tp118.txt`, `privmem-check-tp118p.txt`, `privmem_check.py`: per-kernel private memory.
- Scripts: `pr4.sh pr5.sh pr6.sh c118.sh c118p.sh build118p.sh chainq118c.sh chainq118p.sh hold119.sh chainq119b.sh
  bench119.sh kvb1.sh c118q.sh build118q.sh chainq119c.sh chainq120.sh chainq120b.sh build120.sh kvb2.sh c120.sh
  ckvs2.sh tlx1.sh tlcmp.py ew1.sh chainq120c.sh madv.c madv2.c c122.sh dtb1.sh chainq122.sh build122.sh
  zebin_sizes.py chainq123.sh tlp2.sh ck1m.sh chainq124.sh mk1m.py dec.py kern_isa.py
  zebin-tp120-tp122.txt build123.sh tsx1.sh c123.sh chainq125.sh`, `tlp2-*`, `ew1-*`, `c122-*`, `dtb1-*`, `tlx1-*`, `c120-*`, `kvb2-*`, `dtopk-README.md` (the helper's dtopk-1 write-up). Source: worktree `/home/steve/dsv41-work/tp118p` (069121f625 privmem-1, 5d6c2ae46a tpd-2,
  5dc319d3d5 privmem-2).
