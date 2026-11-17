# kvshard push: prompt halves' rows as copy-engine pushes (tp120)

Design: `STUDY.md`, kvshard-1: `README.md` (this folder; its section "Next step: the push form for prompts" is this).
Worktree `/home/steve/dsv41-work/tp120` (detached HEAD, on top of `a8a24c0268` = tp119 kvshard-1 + privmem fix).
Nothing was compiled or run: every line below needs your build and gate.

Paths: E = `experiments/own-xpu-runtime/engine`, K = `E/src/stage2/packet3/kernels/sycl_v41.hpp`,
B = `E/src/stage2/packet3/backend/backend_sycl_v41.hpp`, MT = `E/src/stage2/packet3/backend/backend_sycl_v41_mt.inc`,
R = `E/planning/dsv41-fixtures/own_run_v41.cpp`. Line numbers are at `13863d34fd`.

## Commits

| commit | what |
| --- | --- |
| `19a2a07c25` | wip tp120: kvshard push (K): KvPushCount / KvPushScan / KvPushSlots / KvPushCopy, KvStageCmpP |
| `c5acc8a28d` | wip tp120: kvshard push (B, MT, R): `OWN_KV_PUSH` |
| `13863d34fd` | wip tp120: kvshard push bench: `E/tools/bench/test_kv_push.cpp` (new) |

## In plain words

With kvshard-1 every card copied the rows it needed from the other cards by READING their memory, also while reading
a prompt. Card-to-card reads during prompts are what came with the host resets of Nov 10-14, and the prompt path had
none since tp107. Now, in prompt halves, each card SENDS its own rows to the others on its copy engine, the same way
the halves' other exchanges already travel (`OWN_PX_BCS`): data first, then a number in the receiver's flag word,
and the receiver waits for that number before it reads.

The trick that makes one copy per card possible: the staging rows of a half are now sorted by which card owns the row
(card 0's rows first, then card 1's, ..., then the rows every card has in its newest-rows tail). The lists are the same
on every card, so this order is the same everywhere, and each card's rows form one unbroken block at the same place on
every card. Each card fills its own block from its own memory and copies that block into the same place on the five
others. The slot list tells the attention where each entry's row now sits, so the attention reads exactly the same
1,024 bytes for every slot as before: the same outputs, bit for bit.

The cost of the design: the copy engine must be told the copy size by the host, and the size depends on the lists,
which only exist on the card. So the host reads 64 bytes (the block sizes) back once per half and index layer
(16 times per block per card) and waits for them before it queues the copy. One-token steps and blocks outside the
halves (guess checks, a prompt's short last block) still pull with `KvGather`, as kvshard-1.

## Switch (R:431-434, B:588-594)

| env | default | meaning |
| --- | --- | --- |
| `OWN_KV_PUSH` | 1 (with `OWN_KV_SHARD`) | 1: prompt halves push; 0: kvshard-1's pulls everywhere (A/B, fallback). Ignored (set to 0) without `OWN_KV_SHARD` (B:642) |

Refused at startup (B:659-667): `OWN_KV_PUSH` > 1; `OWN_KV_PUSH=1` without `OWN_PX=1` and `OWN_PX_BCS=1|2` (px_bcs is
already 0 there without `OWN_PX` or with one card, B:606); more owners than the class words hold (cannot happen with
`OWN_TP=6`). **Behaviour change:** `OWN_KV_SHARD=1|2` without `OWN_PX=1` is now refused unless `OWN_KV_PUSH=0`.

## What changed (file:line)

Kernels K:8438-8625 (namespace `ops41sycl`, after kvshard-1's):

- `KvStageCmp` (K:8438): `operator()` now calls `cmp(..., sl = nullptr, ...)` (K:8451): with no slot list it reads
  exactly what it read before (row `so + e`); the benches' calls are unchanged. With a slot list it reads the row the
  slot names and also checks the slot list (a skipped entry's slot must be the entry: 1 word counted otherwise; a
  row's slot outside the fetch's staging rows: every word of the row counted, nothing read).
- `KvStageCmpP` (K:8496): `KvStageCmp` through the push form's slot lists (`OWN_KV_SHARD=2`).
- `KVP_K = 8` (K:8517), `kvp_class` (K:8519): class of a list value: -1 no row; owner d (0..5) for rows `r < tail0`;
  6 (= N) for rows `r >= tail0` (tail).
- `KvPushCount` (K:8526): per token (work-group of 256, item w holds entries 2w, 2w+1), 8 group reductions -> the
  token's count per class into `tb[t * 8 + k]`.
- `KvPushScan` (K:8548): one work-group, in place: `tb[t * 8 + k]` = class k's base + class-k entries of tokens before
  t; `hb[k]` = class base, `hb[8 + k]` = class count (rounds of 256 tokens: the engine's halves are <= 256, one round).
- `KvPushSlots` (K:8576): per token, 8 group exclusive scans give each entry's rank inside its token's class; slot =
  `128 + so + tb[t * 8 + k] + rank` (-1 stays -1, as KvGather).
- `KvPushCopy` (K:8605): one work-group per entry (as KvGather): tail rows from the ring, this card's own rows from its
  own chunk (local pointer), into the row the slot names; peers' rows are left to their pushes.

No kernel has an array member, none gets a peer pointer (the peers' staging rows are written by the copy engine only).

Backend B:

- `Options::kv_push` (B:588-594); normalization (B:642); refusals (B:659-667).
- Destructor: peers' staging IPC handles closed after `bcs_drain` (B:856-859).
- Members (B:1466-1475): `kvs_speer[c][d]` (card d's staging rows as card c's copy engine writes them), `kvp_tb`,
  `kvp_hb` (card), `kvp_h` (host copy, 64 bytes per card, plain member array: no pinned memory), host counters.
- `kvs_alloc` (B:5671; changes B:5685-5695): `kvs_ct` 48 words (third set: halves pushed); `kvp_tb` (mtb_n() x 8 words), `kvp_hb`
  (16 words); the startup line says which form runs.
- `kvs_map` (B:5705; the staging loop B:5723-5739): every card's staging rows IPC-mapped into every peer's context (as the chunks, `touch`ed).
- `kvs_fetch` (B:5745): unchanged launches; its check moved into `kvs_check` (B:5761: the same KvStageCmp launch for
  the pull form, KvStageCmpP for the push form, then KvStageFold into set 0 / 1 / 2).
- `kvs_push_on` (B:5778): `o.kv_push && px_run[c] && bcs_blk()` (host state, the same on every card).
- `kvs_fetch_push` (B:5798-5840): the half's fetch (order below).
- `kvs_push` (B:5846-5872): `bcs_push`'s pattern (B:1915-1953) for the staging run: own event signalled on qs's native
  list, the copy list waits for it, one copy per peer of `n` rows into `kvs_speer[c][d]` at the same rows (skipped when
  `n = 0`), then the push number (`bseq`, from the number table) into each peer's copy flag word `xbf + 16 c`, event
  reset, `px_note(..., 3, ...)` (`OWN_PX_CHECK` sees it as a push).
- `kvs_report` (B:5874-5909): fetch counts incl. halves pushed; `OWN_KV_PUSH:` line per card (rows staged from tail /
  own chunk / peers' pushes, rows pushed per peer, GiB out, largest run); with `OWN_KV_SHARD=2` a third check line per
  card, `halves pushed`, which counts towards `ALL SAME` / `MISMATCH` (B:5908).

MT:2339-2349 (`tpm_layer` PX_P1 start): `kvs_push_on(c) ? kvs_fetch_push(...) : kvs_fetch(...)`, same lists, same
`so = px_tok * 512`, same M.

R:431-434: `OWN_KV_PUSH`.

## How a half's fetch is ordered and flagged (B:5798-5840)

At an index layer, PX_P1 start of half h (after `ix_wait` in PX_P0B: the half's lists are on every card):

1. qs[c]: `KvPushCount`, `KvPushScan` (class counts -> per-token offsets, `kvp_hb`).
2. qs[c]: copy `kvp_hb` -> host `kvp_h[c]` (event `eh`).
3. qs[c]: `KvPushSlots` (slot list `kvs_sl[c] + so ...`), `KvPushCopy` (tail + own rows into their staging rows).
4. Host: waits for `eh` only (steps 3 keep the card busy meanwhile); counted like `twait` (`OWN_TP_HOSTPROF`'s
   `tph_wait`, `OWN_TIMELINE`'s host waits). Checks the bases / counts form a layout (else throws with the numbers).
5. Host: `kvs_push(c, so + base[c], n[c])`: signal (qs order: after `KvPushCopy`) -> copy list waits -> five row
   copies -> five flag copies (number `bseq[c]`, the same on every card) -> event reset.
6. qs[c]: `bcs_wait(c, seq)`: XchgWaitB spins until every peer's copy flag holds >= seq, i.e. every peer's run of
   this half has landed (flags after data on one in-order copy list, as every bcs push).
7. `OWN_KV_SHARD=2`: `KvStageCmpP` + `KvStageFold` (set 2) on qs[c].
8. The attention reads `kvs_stg[c]` through `kvs_sl[c]` exactly as with KvGather.

Hazards (B:5790-5797 comment): (a) a peer's push into this card's half-h rows at index layer L2 comes after the peer
passed its wait for this card's X1 of half h at layer L2 - 1, which this card pushes after that layer's attention
(X1 is pushed per half at every layer: `oa_m`, MT:2005-2014); (b) this card's run, read by its copy engine, is rewritten only
at the next index layer, after every peer's X1 of this layer, which each peer pushes after it saw this push's flag;
(c) halves use disjoint rows; one-token steps after a block start after every push landed. No deadlock from the host
wait: every card queues the same pushes in the same host order, and everything on qs[c] before step 2 waits only for
pushes queued at earlier places in that order. Take the card whose host thread is blocked at the earliest place P:
every other host thread is at P or later, so it has queued every push that comes before P; so this card's queue
reaches P, its host wakes up and queues its push, and so on. A half's KV push is waited for (step 6) only after the
card queued its own.

## Under OWN_PX_SERIAL=1 (the stable mode default)

Nothing is queued on qs[c] between the push (step 5) and its wait (step 6), in both modes: the compute queue spins
while the copy engines move the rows, as with every serial X1..X4 push (`bcs_fire` + `bcs_wait`, MT:2879-2886). The
local copies (step 3) run before the push is released. Peers' pushes may land while this card runs steps 1-3: they
write other rows (other classes) than steps 1-3, the same as a serial push landing beside the receiver's compute
today. The push is not moved earlier in `OWN_PX_SERIAL=0` either (it waits right before the attention; overlap would be
a later A/B).

## Build (CPU only; after `six.active` clears)

```bash
W=/home/steve/dsv41-work; C=13863d34fd
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
F="-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
rm -rf $W/src120; mkdir -p $W/src120
git -C $W/tp120 archive $C:experiments/own-xpu-runtime/engine src planning tools/bench | tar -x -C $W/src120
cd $W/src120
# runner
nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp
nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp120 -lze_loader
# benches (the new one, and the two kvshard-1 ones again: KvStageCmp now goes through cmp())
nice -n 5 icpx -fsycl $GPU "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src tools/bench/test_kv_push.cpp -o $W/test_kv_push
nice -n 5 icpx -fsycl $GPU "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src tools/bench/bench_attn_a1.cpp -o $W/bench_attn_a1_kvs120
nice -n 5 icpx -fsycl $GPU "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src tools/bench/test_topk_shard.cpp -o $W/test_topk_shard120
```

Check the private-memory report of the new kernels if
your build prints one (privmem-1): KvPushCount / KvPushScan / KvPushSlots / KvPushCopy / KvStageCmpP should need none.

## Test order

1. **Benches, one card** (a few hundred MiB / ~1.3 GB of card memory, < 0.5 GB host):
   - `ONEAPI_DEVICE_SELECTOR=level_zero:1 $W/test_kv_push` must end `PASS (54 cases)`; it also prints the time of the
     four launches and of KvGather at M 256 (one card, no PCIe: only the kernels' own cost). `ONLY="R8 TT1024"` etc.
   - `KVS=1 ... $W/bench_attn_a1_kvs120` and `... $W/test_topk_shard120` must still end `PASS` (KvStageCmp refactor).
2. **Shard off, unchanged**: the tp120 binary without `OWN_KV_SHARD` on the p3k gate: IDS256_SAME / traced
   TRACE_IDENTICAL against tp117 (with the shard off `kv_push` is forced to 0: no allocation, no mapping, no launch).
3. **`OWN_KV_SHARD=2`, stable mode** (c117 pattern: preflight before each start, first fault / non-zero exit /
   difference = STOP):
   1. p3k traced, default tail: TRACE_IDENTICAL and `OWN_KV_SHARD=2 check: ALL SAME`. At 3K every row is in the tail:
      the pushes carry flags only (`OWN_KV_PUSH:` line: peers' pushes 0 %). This checks the layout and the numbering.
   2. p3k with `OWN_KV_TAIL=1024 OWN_KV_SHARD_R=8`: most rows now come from chunks, every list spans all six owners:
      real pushes at 3K. ALL SAME, the `halves pushed` lines show peers > 0. (Optional: once more with
      `OWN_PX_CHECK=1`: no push-number complaint.)
   3. x95k: ALL SAME; note the `halves pushed` distinct-rows numbers (U) and the `OWN_KV_PUSH:` GiB out.
   4. (Optional A/B) p3k / x95k with `OWN_KV_PUSH=0`: kvshard-1's pull form, ALL SAME too; prompt time difference.
4. **`OWN_KV_SHARD=1` gate up to 200K** (README.md test order 3.2 with the push on): p3k IDS256_SAME (e52), p10k
   IDS64_SAME (tg107), plain IDS128_SAME (ab1), guessing SAME AS plain + GLOG_SAME (tg105v), x95k IDS256_SAME (e82),
   x200k IDS1024_SAME (lc1), s200k SAME AS plain. Free memory after load ~1,530 B per position (tpd-mem lines).
5. **Then 400K+**: x400k (lc2-size) IDS1024_SAME, then x700k and the ~1M planted-fact prompt in two placements
   (`OWN_KV_SHARD_R=2048` and `16384`), STUDY 5.1 step 4.

Expect prompt reading to slow down (est. at 95K: ~16 half-fetches per block, each pushing ~20K rows to five peers
and receiving ~100K rows, ~1.5 GiB in and out per card per block, ~50-70 ms per block at 25 GB/s with no overlap:
+6-9 %; plus 16 short host waits per block). The gate is about identity first.

## Doubts (numbered, file:line)

1. **The host wait** (B:5814-5820): the copy engine needs sizes the host knows, so the host waits once per half and
   index layer for the 64-byte bases / counts. Sixteen times per block per card, each a short gap in the card's
   queue (the host stops running ahead until the card reaches the scan). I could not avoid it with the copy engine;
   the alternative is a compute-kernel push (the owner's kernel writes into the peers' staging rows, then a
   system-scope flag): no host wait, but writes from kernels across PCIe are a traffic class the engine has not used
   in prompts. Measure the bubble with `OWN_TP_HOSTPROF=1` (the wait is counted in `tph_wait`) before deciding.
2. **The 64-byte read into pageable memory** (B:5808): `qs[c].memcpy` into a plain member array, as `ix_check` /
   `kvs_report` do. The runtime may stage it through its own pinned buffer internally; we allocate none.
3. **Large copies, flags after data** (B:5855-5866): bcs pushes were gated with copies of a few hundred KB; these are
   up to ~100 MB per peer. The pattern is the same (one in-order copy list, flag copies after the row copies), but if
   the driver splits a large copy across engines, the ordering rests on the driver's in-order guarantee. Step 3.2 /
   3.3 (mode 2) is the test; a flag landing before its rows would show as MISMATCH, not as a hang.
4. **The layout must be the same on all six cards** (K:8519, B:5803): it depends on the lists (the same on every
   card after `ix_wait`, the engine's existing rule) and on `tail0 = tlen - kv_tail + 512` (every card publishes every
   row at the same host-order place, MT:1303-1371, so `tlen` is the same). Nothing checks it across cards outside mode
   2; a difference would put rows in the wrong place (mode 2 catches it: the compare follows the slots).
5. **Blocks outside the halves still pull** (MT:2346-2348): guess checks, plain blocks (`OWN_PX=1` but the block is
   odd or its halves are below `OWN_PX_MIN`, e.g. a prompt's last block). Those blocks already pull their X1..X4 and
   index lists (`xchg_m`, `ix_pull`), so this is the same traffic class as today, but it is not read-free.
6. **No de-duplication** (STUDY 5.3, not done): a row listed by several tokens of a half is staged and pushed once per
   listing. It keeps the layout simple (one staging row per entry, as KvGather). The mode-2 `halves pushed` lines give
   the distinct-row counts to decide whether to add it.
7. **Default on** (B:594, B:642, B:662-665): `OWN_KV_SHARD` without `OWN_PX=1` is now refused unless `OWN_KV_PUSH=0`.
8. **Hazard (a) leans on X1** (B:5790-5797): a peer pushes into this card's half rows at the next index layer only
   after this card's X1 of the layer before, which is pushed after the attention. True in every px_layers order I read
   (`oa_m` MT:2005-2014, `px_layers` MT:2976-3100), including skip39 (layer 39 is not an index layer). A future change that drops X1
   from a layer between index layers would break it.
9. **The scan's single work-group** (K:8548): 8 classes x one round of 256 tokens (the engine's halves are at most
   MTX = 256, K:29); the bench covers 260 (two rounds).
10. **`KvStageCmp` refactor** (K:8438-8481): the pull form's check now goes through `cmp()` with a null slot list; the
    reads and counts are the same, but it is a changed kernel: the two kvshard-1 benches must still pass.
11. **XSPIN** (B:3971, ~0.9 s of polls): peers spin in XchgWaitB from the moment they reach the wait until this
    card's host has read its sizes and queued the push. In lockstep that is microseconds; a host thread descheduled
    for a long time would trip the time-out (poison, the step fails), as with any late push.
12. **`touch` of the peers' staging mappings** (B:5737): no kernel uses those pointers (only the copy engine), so the
    touch is only for symmetry with `kvs_map`'s chunks; harmless, a few launches at start.
13. **Mode 2 cost**: the check adds a compare launch per half and index layer after the wait (as kvshard-1's); mode
    2 also keeps the full mirrors, so x95k is fine but mode 2 cannot go past the old ceiling.

## kvdedup-1 (2026-11-16 22:xx, tp125 candidate 3c77277c87, opt-in `OWN_KV_DEDUP=1`)

Why: the push form stages one row per list entry. At 194K (ckvs2 x200k_dt) every card staged 793,183,488 rows in
6,064 halves (130,800 per half = 255.5 tokens x 512) and card 0 pushed 154M rows to each of 5 peers (736 GiB out);
reading cost ~13 % against no shard (95K 659.5 -> 568.1, 194K 645.3 -> 563.2 tok/s). The mode-2 check's distinct
counts (only the first blocks, ckvs2 x95k_chk: 1,275 distinct rows per half list on average, 2,898 at most, of
~131K entries) say neighbouring tokens list mostly the same rows; long-context U is not measured yet (the new exit
line `OWN_KV_DEDUP=1: card c: E list entries with a row staged as U distinct rows` gives it).

What: per half and index layer, on every card (kernels `KvDd*` in sycl_v41.hpp after `KvPushCopy`):
1. `KvDdZero` + `KvDdMark`: a bitmap of the listed rows (atomic or; the order of atomics cannot change the set).
2. `KvDdChunk` (one work-group per R-row chunk): per word the chunk's earlier set bits below / at-or-past tail0;
   per chunk the totals. `KvDdScan` (one work-group): class k < N = the chunks q % N == k in increasing q, class N =
   every chunk's tail part; bases and counts into hb exactly as `KvPushScan` (+ hb[2K] = entries with a row).
3. `KvDdSlots`: every entry's slot = 128 + so + class base + rank of its row among the half's distinct rows of
   that class (row order). `KvDdRows`: rowof[so + rank] for the rows this card stages itself (its chunks + the tail).
   `KvDdCopy`: those rows from chunk / tail into staging (1,024 work-groups striding).
4. The rest is unchanged: host reads hb, `kvs_push` of this card's class run to every peer, `bcs_wait`.
Identity: the attention reads, for every list position, the same 1,024 bytes as before (only the staging row
holding them changes; every listing of a row names the one copy). The layout is a function of the set of listed
rows, tail0, R and N: the same on every card (as the push form's). Needs R % 32 == 0 (a bitmap word in one chunk).
Scratch per card: 3 words-arrays of rows_c1 / 32 words, 4 chunk arrays, rowof (mtb_n() x 512): ~1.5 MB at 1M.
Gate (c125): check mode at 3K (default tail; tail 1024 with R = 32 so all six owners push), check mode at 95K, 194K
against R200 (speed against x200k_dt), and the 1M case against x1m_a (with ropedev-1).
