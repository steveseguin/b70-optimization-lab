# kvshard step 0 + step 1 (kvshard-1): what was built

Design: `STUDY.md` (this folder). Worktree `/home/steve/dsv41-work/tp114src` (detached HEAD, on top of
`0e826cc908` = tp118c). Nothing was compiled or run: every line below needs your build and gate.

Paths below: E = `experiments/own-xpu-runtime/engine`, K = `E/src/stage2/packet3/kernels/sycl_v41.hpp`,
B = `E/src/stage2/packet3/backend/backend_sycl_v41.hpp`, MT = `E/src/stage2/packet3/backend/backend_sycl_v41_mt.inc`,
R = `E/planning/dsv41-fixtures/own_run_v41.cpp`. Line numbers are at `68f6c0ac1e`.

## Commits

| commit | what |
| --- | --- |
| `3ea50924f0` | wip tp119: kvshard-1 (K, B, MT, R): `OWN_KV_SHARD` |
| `d6aefb4485` | wip tp119: kvshard bench: `E/tools/bench/test_topk_shard.cpp` (new) |
| `68f6c0ac1e` | wip tp119: kvshard bench: `E/tools/bench/bench_attn_a1.cpp` `KVS=1` arm |

The benches need the first commit (they use `kvs_owner`, `KvGather`, `KvStageCmp`, `KvStageFold` from K).

## In plain words

With `OWN_KV_SHARD=1` each card keeps only its own sixth of the compressed KV rows (in chunks of 2,048 rows, dealt
round robin to the six cards) plus a copy of the newest 4,096 rows of each source. Before the attention reads a
list of 512 rows, one kernel copies those rows (from this card, its tail copy, or a peer card) into a staging area in
list order, and the attention reads the staging area through a matching slot list. The attention reads the same
bytes in the same slots, so the output must be the same bit for bit. `OWN_KV_SHARD=2` does the same but also keeps
the full copies and compares every staged row against them on the card, then prints the totals at exit.

## Switches (runner R:424-430)

| env | default | meaning |
| --- | --- | --- |
| `OWN_KV_SHARD` | 0 | 0 off (nothing changes: no allocation, no launch, no branch in a kernel); 1 on; 2 on + check |
| `OWN_KV_SHARD_R` | 2048 | rows per ownership chunk (a multiple of 8, so a layer-20 block of 8 rows never spans two owners) |
| `OWN_KV_TAIL` | 4096 | newest rows of each source kept on every card (at least 2 x MTB = 1,024) |

Refused with a clear error (B:635-651): `OWN_KV_SHARD` > 2; BF16-activation builds (`OWN41_ACT_BF16`); `OWN_TP` != 6;
`OWN_XLL`; `OWN_DEV_INDEX=0` (host index path); `OWN_LAYERS` (not the whole model); head dim != 512;
`OWN_KV_SHARD_R` not a multiple of 8; `OWN_KV_TAIL` < 1,024. Also refused at the call: `load_state` (B:1363-1364) and
segment-mode host rows `append_published` (B:1262).

**DSpark / guessing is NOT refused** (your brief suggested refusing it if unsure). Why I left it on:
(1) the draft's own attention reads only its own ring (`dring`), never the compressed rows or the lists
(`backend_sycl_v41_draft.inc`); (2) one-token checks (`ck1`) run through `tp_phase` and check blocks through
`tpm_layer`, both of which fetch; (3) a rejected guess only rewinds `tlen` (`commit_block`, MT:3443) and the next
block rewrites rows at or above the rewound length, which is always within MTB = 512 rows of the newest: those rows
are read from the tail (the tail guard below), never from a chunk. If you prefer the cautious form for the first
gate, add one line in the refusal block (B:635-651), e.g. after B:640:
`if (o.dspark) throw std::invalid_argument("OWN_KV_SHARD: not with OWN_DSPARK yet");`

## What was built (every function / kernel added or changed)

Kernels, K:8327-8454 (namespace `ops41sycl`, new section "kvshard-1" after `PubAppendAM`):

- `kvs_owner(r, R, N)` (K:8336), `kvs_local(r, R, N)` (K:8337): owner card and row in its chunk.
- `PubAppendS<A>` (K:8341): `PubAppendA` with the shard's stores: the row's BF16 words into its tail slot, the
  owner's chunk row (null pointer on other cards), the mirror row (mode 2; null otherwise); index-key row unchanged.
- `PubAppendSM<A>` (K:8359): the same for a block's n rows (`PubAppendAM`'s layout), tail slot `row % TT`, chunk
  row `kvs_local(row)` when `kvs_owner(row) == card`.
- `KvGather` (K:8386): one work-group of 256 per list entry; writes `sl[so + e]` (-1 stays -1, a row becomes
  `128 + so + e`) and copies the row (from the tail when `r >= tail0`, else from `ch[kvs_owner(r)]`) into staging
  row `so + e`.
- `KvStageCmp` (K:8413): mode 2; staged row vs mirror row, counts in 6 device words (rows, differing words, tail /
  own chunk / peer rows, distinct rows via a mark word per row and a per-launch stamp).
- `KvStageFold` (K:8442): one item; adds the words into 64-bit totals, keeps the largest distinct count and the
  launch count, zeroes the words.

Backend B:

- `Options::kv_shard`, `kv_shard_r`, `kv_tail` (B:578-587).
- Constructor: refusals (B:635-651); `ckv_mirror` not allocated when `kv_shard == 1` (B:738); `kvs_alloc(t)`
  (B:741); `h_ckv` reserve skipped when on (B:765).
- Destructor: `kvs_report()` after the queues are drained (B:821); the peers' chunk IPC handles closed (B:835-838).
- `append_published` (B:1262) and `load_state` (B:1363) throw when on.
- Members (B:1431-1444): `kvs_chunk`, `kvs_tail`, `kvs_stg`, `kvs_peer`, `kvs_sl`, `kvs_mark`, `kvs_cw`, `kvs_ct`,
  `kvs_stamp`, `kvs_coff`, `kvs_nloc`, `kvs_n1`, `kvs_nm`.
- `tp_setup`: `kvs_map()` right after the arenas' IPC mapping (B:4836).
- `tp_phase` case 1 (one-token attention): `kvs_fetch(c, si, list, 1, 0, 0)` at index layers after `sync_cidx`
  (B:5395); `WindowAppendP` gets the slot list (B:5399); `kvc` = staging (B:5409); new `cl` (B:5411) used for
  `score_tw` and `out_f`'s list argument (B:5422, B:5445).
- New (B:5621-5731): `kvs_tail0`, `kvs_alloc`, `kvs_map`, `kvs_fetch`, `kvs_report`.
- `publish_tp` (B:5770-5782): `PubAppendS` branch; the `PubAppendA` branch unchanged.
- `tp_trace` case 1 (B:6007-6008): with the shard on, `TT_CIDX` traces the list itself (`cidx_mirror[0]`), not the
  attention list (which now holds staging slots), so traces stay comparable with tp117.

Blocks MT:

- `tpm_publish` (MT:1332-1339): `PubAppendSM` branch; `PubAppendAM` branch unchanged.
- `tpm_layer` `PX_P1` start (MT:2305-2309): `kvs_fetch(c, si, cidxm + px_tok * 512, M, px_tok * 512, 1)` at index
  layers (after `ix_wait` / `tpm_index` in `PX_P0B`); `wci` (MT:2322), `kvc` (MT:2329, MT:2428) and the per-token
  path's list (MT:2422) switch to the slot lists / staging.

Runner R:424-430: the three env vars only.

Benches:

- `test_topk_shard.cpp` (new): `kvs_global` (inverse map), `TkCompact` (line 48), `TkMerge` (line 80), `main`.
  Arms per length and score family: `ref P` (TopKSelP whole array), `1card` (the engine's topk-m M1+Q2 / MB1+QB2:
  their first bitwise record), `R2048`, `R16384` (the shard). Prints `PASS` / `FAIL (n differ)`.
- `bench_attn_a1.cpp`: `kvs_global_` (line 325), the `KVS` block in `main` (lines 434-662; `gather` 493,
  `kvs_lists` 544, `kvs_cat` 562), header line 1 (build + run) and the env list (line 40). Nothing else changed.

## Memory per card

- Chunks: `(3 x (max_seq/2 + 2) + (max_seq + 2)) / 6` rows rounded up to whole rounds of 6 R, x 1 KiB (about a
  sixth of today's `ckv_mirror`; e.g. 163 MiB instead of 977 MiB at max_seq 400K).
- Tails: 4 x 4,096 rows x 1 KiB = 16 MiB.
- Staging: `mtb_n()` tokens x 512 rows x 1 KiB = 128 MiB (256 MiB with `OWN_PX_BIG`), slot lists 0.5 / 1 MiB.
- Mode 2 adds back the full mirrors plus 4 B per position (marks).
- The startup line `OWN_KV_SHARD=...: per card ... GiB of chunks ...` (card 0 only, stderr) prints the sizes.

## Build (CPU only; after `six.active` clears, as build118.sh)

```bash
W=/home/steve/dsv41-work; C=68f6c0ac1e
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
F="-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
rm -rf $W/src119; mkdir -p $W/src119
git -C $W/tp114src archive $C:experiments/own-xpu-runtime/engine src planning tools/bench | tar -x -C $W/src119
cd $W/src119
# runner
nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp
nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp119 -lze_loader
# benches (the lines at the top of each file, output into $W)
nice -n 5 icpx -fsycl $GPU "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src tools/bench/test_topk_shard.cpp -o $W/test_topk_shard
nice -n 5 icpx -fsycl $GPU "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src tools/bench/bench_attn_a1.cpp -o $W/bench_attn_a1_kvs
```

## Test order

1. **Benches, one card** (when a card is free; a few hundred MiB of card memory, under 100 MiB of host memory):
   - `ONEAPI_DEVICE_SELECTOR=level_zero:1 $W/test_topk_shard` must end `PASS` (every row y; `NOTIME=1` skips
     timing, `ONLY=139000` one length). A `1card` NO is a topk-m finding, not a shard one.
   - `KVS=1 ONEAPI_DEVICE_SELECTOR=level_zero:1 $W/bench_attn_a1_kvs` must end `PASS` (default R 64: every list
     spans all six owners and the tail). Also once with `KVS_R=8` and once with `KVS_R=2048 KVS_TT=4096`.
2. **Default unchanged**: the tp119 binary without `OWN_KV_SHARD` on tp118c's p3k gate (IDS256_SAME / traced
   TRACE_IDENTICAL against tp117): `OWN_KV_SHARD=0` must change nothing.
3. **Gate c-kvs1** (STUDY 5.1; c117 pattern: stable mode, preflight before each start, first fault, non-zero exit or
   difference = STOP):
   1. `OWN_KV_SHARD=2` p3k, traced: TRACE_IDENTICAL against tp117's trace, and stderr ends
      `OWN_KV_SHARD=2 check: ALL SAME` (0 words differ on all six cards).
   2. `OWN_KV_SHARD=1`: p3k IDS256_SAME (e52), p10k IDS64_SAME (tg107), plain IDS128_SAME (ab1), guessing code /
      analysis SAME AS the plain run + GLOG_SAME (tg105v), x95k IDS256_SAME (e82), x200k IDS1024_SAME (lc1), s200k
      SAME AS the plain run. `OWN_KV_SHARD=2` at x95k: ALL SAME, and the distinct-rows counts (the U of STUDY 3.2;
      "distinct rows per list ... on average, ... at most" in the check lines, set "blocks").
   3. Free memory after load (tpd-mem lines) should follow ~1,530 B per position.
   4. **Stop at 200K** until the push form exists (next step). STUDY 5.1 step 4 (x700k, ~1M) needs it.

## Next step (not in this commit): the push form for prompts

This commit pulls everywhere: `KvGather` reads peers' chunks through the IPC mapping, in one-token steps and in
prompt halves alike. The host resets of 11-10..14 came with card-to-card reads, and the prompt path has been
read-free since tp107. Before any run past 200K, prompt halves should switch to: the owner gathers its listed rows
(the half's lists are on every card after `ix_wait`) and pushes them into each peer's staging on the copy engine
(`OWN_PX_BCS` machinery, flags after data), keeping `KvGather` for one-token steps and checks. De-duplicated block
staging (STUDY 5.3) can come with it: short prompts give every token the same rows.

## Unsure / check first (file:line)

1. **Pointer array inside a by-value kernel struct**: `KvGather::ch[6]` (K:8388). The engine's peer kernels pass
   peer pointers as direct fields (`XPullK128`, B:94-145). Residency of the peers' chunks relies on `kvs_map`'s
   `touch()` (B:5664-5685; own_run sets `DisableIndirectAccess=1`, B:1547-1553). If the first fetch faults or
   returns zeros, replace `ch[6]` with six direct pointer arguments.
2. **Prompt-path pulls** (MT:2309): card-to-card reads during prompts, the reset class above. First runs in stable
   mode and up to 200K only.
3. **Prompt speed**: a half of 256 tokens fetches 256 x 512 rows (128 MiB, about 5/6 from peers) at each of the
   8 index layers per card, with no de-duplication. Expect prompt reading to slow down; the gate is about identity.
4. **The tail guard** (B:5622-5634, `kvs_tail0`): rows at or past `tlen - kv_tail + MTB` come from the tail, older
   ones from chunks. It relies on a block publishing at most MTB rows per source (B:1214-1215, `mtb_n() <= MTB`) and
   on `tlen` never dropping below the start of the running block. If any path publishes more per block, it breaks.
5. **One-token fetch placement**: case 1 after `sync_cidx` (B:5395), not case 0 as STUDY wrote. It sits right
   before the first reader of the list (`WindowAppendP` / `score_tw` / `out_f`), so whatever makes the list final
   for them (including `OWN_IDX_DSPLIT`'s exchange) makes it final for the fetch.
6. **`OWN_PX` halves** (MT:2309): each half fetches into its own staging rows (`px_tok * 512` on); the halves may run
   on different queues. `kvs_fetch` throws if a half would run past the staging (B:5693). `tail0` is computed at
   enqueue from `tlen`, which may already include the other half's rows; the guard still holds (that half's rows
   are within MTB of the newest).
7. **DSpark not refused** (see above; one-line refusal after B:640 if you prefer).
8. **`sync_rows` with no mirror** (mode 1; B:3176-3189): a no-op in tp mode because `src_len` only grows through
   `append_row_host` / `load_state`, both refused with the shard. If that ever changes it would copy into a null
   mirror.
9. **The report is printed by the destructor only** (B:821), like the `OWN_IDX_DSPLIT_CHECK` totals: a run that
   exits without destroying the backend prints no `ALL SAME` line.
10. **Trace change** (B:6008): with the shard on, `TT_CIDX` reads `cidx_mirror[0][isrc_for(L)]` instead of
    `idxs_cat + 128`; with it off the traced bytes are the old ones.
11. **Mode 2 marks** (B:5651): one mark array per card shared by the four sources (one word per row up to
    `max_seq + 2`); a new stamp per fetch keeps sources apart.
12. **Bench coverage**: `bench_attn_a1 KVS=1` checks one card, up to 16 tokens per block (form 0 only at 16), with
    a fixed set of rows; prompt halves of 256 tokens use the same kernels with larger M, and nothing in the bench
    races a publish against a fetch. `test_topk_shard` is a record for kvshard-2 (the engine does not split the
    index yet); its "dummy +inf block" trick is explained at its top.
13. **Not done from the STUDY plan, on purpose**: no `CidxFillT` (KvGather writes the slot lists), staging is
    allocated in the constructor (`kvs_alloc`) rather than `mt_alloc`, no push transport.
