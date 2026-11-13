# idxsplit-1: the prompt index lists split across the six cards (OWN_IDX_SPLIT)

Helper work, 2026-11-13. Engine tree: lab 44081756b (`b/`, git: commit `base` = 44081756b's engine, working changes =
idxsplit-1). Patch: `idxsplit-1.patch` (against lab HEAD; `git apply --check` clean). Binary: `bin/own_run_v41_is1`
(build108.sh's flags, `build_engine.sh`). Runs: `runs/tr` (traces), `runs/lg` (the x34k_on run cut by the 06:02 host
reset), `runs/lg2` (long documents after the reset audit, `plan_lg2.sh`); wrappers `six.sh`,
`drive.sh`, `one.sh`, `plan.sh` (copied from xchg2 and adapted).

RESULTS: section 5 (reset audit: no defect) and section 6 (long documents: same answers; reads -6.4 % / -9.2 % / -15.4 %
at x19k / x34k / x95k).

## 1. Ledger (where the index time goes today)

From the tp109 prompt timelines (`runs/tlpx109/tlpx_34k.txt` blocks 62-63 of the 34K document, `runs/tlp109/tlp_px512.txt`
blocks 3-4 of the 3K prompt; px-512 + copy engine; tool `tools/idx_ledger.py`). One piece = one block of 512 tokens as two
halves of 256. Per (index layer, half) the launches of `tpm_index`: the indexer's q_b rows (WsH16<40u>, 4096 x 1280 H16),
the q rope, the proj rows (GemvH16P<160>, 32 rows), the scores (IndexerScoreBM, or IndexerScoreBCM past layer 20 over the
layer-20 candidates), the selects (TopKSel*). 8 index layers (2, 8, 14, 20, 24, 28, 32, 36) x 2 halves = 16 per piece.

Card 2 (the slowest card, per piece, ms):

| piece | q_b | rope | proj | scores | selects | index total | piece span | share |
|---|---|---|---|---|---|---|---|---|
| 3K, block 3 | 5.62 | 0.07 | 0.54 | 7.75 | 1.21 | 15.19 | 723.8 | 2.1 % |
| 3K, block 4 | 5.64 | 0.07 | 0.54 | 10.69 | 1.26 | 18.19 | 726.7 | 2.5 % |
| 34K, block 62 | 5.72 | 0.06 | 0.55 | 127.58 | 4.18 | 138.10 | 857.3 | 16.1 % |
| 34K, block 63 | 5.74 | 0.07 | 0.54 | 128.83 | 4.17 | 139.35 | 855.4 | 16.3 % |

Per (layer, half) at 34K on card 2: layers 2 / 8 / 14 (ratio-2 source, ~16K rows) score 6.9-7.0 ms + select 0.17;
layer 20 (ratio 1, ~32K rows) 13.8-13.9 ms + 0.22 (block select) + 0.33; layers 24-36 (candidates) 7.2-7.3 ms + 0.26;
q_b 0.35-0.37 ms every time. Other cards: 123-136 ms per piece (card 0 is ~10 % faster on the same kernels).

All of it is replicated: every card computes every token's lists (the attention on each card reads every token's list).

Model (card 2): q_b + rope + proj ~6.2 ms per piece (constant), scores + selects ~2.2 ms + 4.04 ms per 1,000 positions.
Summed over a document's pieces (the index on the slowest card), and what the split takes off (the biggest share is 43
of 256 tokens, so ~83 % of it), with an assumed 0.1 ms of exchange cost per (layer, half):

| document | index (s) | saved (s) | read today (s) | predicted read |
|---|---|---|---|---|
| 3K (3,323) | 0.10 | 0.08 | 5.13 | ~5.06 (-1.4 %) |
| x19k (18,692) | 1.68 | 1.40 - 0.06 | ~30 | ~-4.5 % |
| x34k (33,815) | 5.06 | 4.21 - 0.11 | 56.1 (lc107b) | ~52.0 (-7.3 %) |
| x95k (95,497) | 37.5 | 31.2 - 0.30 | 173.8 (lc107b) | ~142.8 (-17.8 %) |

Per piece at 32K: 138.6 ms of 856 -> ~115 ms saved (-13.5 %); the whole 34K read averages over shorter contexts.

List gather cost: per (layer, half) each card sends its share (42-43 tokens x 512 ints = 86 KB) to each of 5 peers (430 KB
out per card, 2.5 MB in all); on the copy engine (~30 GB/s per card, bcs bench) that is ~15 us plus latency, queued right
after the selects and running beside the attention's q_b rows (~0.6 ms) and rope.

## 2. Design

Opt-in `OWN_IDX_SPLIT` (default 0: nothing changes, not even the arena layout).

* `OWN_IDX_SPLIT=1`: in prompt blocks (OWN_PX: halves) of at least `OWN_IDX_SPLIT_MIN` tokens (default 32; not checks),
  card c computes the index only for its tokens [t0[c], t1[c]) (`ix_split`, a fixed partition of the block's / half's
  tokens, the same at every index layer; equal shares, or `OWN_IDX_SPLIT_W="w0,...,w5"` weights): the indexer's q_b rows,
  their rope, the proj rows, the scores and the selects (and at layer 20 the candidate masks and block lists, which only
  the same token reads again at layers 24-36, so they stay local).
* `OWN_IDX_SPLIT=2`: only the scores and selects are split (q_b / rope / proj for every token as before).
* The lists live in the arena (`cidxm[c][slot] = arena + xidxM + slot * 512 * TB`, 8 slots, 8 MiB per card; the old
  separate 8 MiB allocation is not made then). After its selects, each card sends its share to every peer at the same
  offsets:
  * halves on the copy engines (OWN_PX + OWN_PX_BCS, production): `bcs_push` (as X1..X4), waited for by `XchgWaitB`;
  * plain blocks (blocks of 64 / 256, a prompt's odd tail block): `XchgPull` mode 1 (publish) after the selects, mode 2
    (wait + copy) before the attention;
  * OWN_PX without the copy engine: not split.
* Order in `tpm_layer` (split layers only): q_a / kv rows and norms, then **the publish and this card's index (+ push)**,
  then the attention's q_b rows and rope, then `ix_wait` (the lists' wait), then the attention. The publish / index read
  xn, qn and the published rows; q_b / rope read qn and write q, kvn: no shared buffer, so only the queue order moves and
  the exchange runs beside q_b + rope.
* Short tokens (<= 512 rows: CidxFill) of a split layer: each card fills its own tokens' lists, the rest arrive with the
  exchange (no 64-byte line written by two engines).
* `OWN_IDX_SPLIT_CHECK=1` (diagnostic): each split layer also runs the full index of every token into separate lists
  (and, with =1, the card's own q / proj rows into separate buffers); after the exchange the host compares every token's
  gathered list with the full one and the card's own q / proj rows with the full ones, bitwise. Totals at exit.

Files: `backend/backend_sycl_v41_mt.inc` (tpm_index's split path, `IxPend` / `ix_split` / `ix_on` / `ix_pull` /
`ix_wait` / `ix_check`, the arena region, tpm_layer's order), `backend/backend_sycl_v41.hpp` (options, BCS alignment
check, check totals), `planning/dsv41-fixtures/own_run_v41.cpp` (env parsing).

## 3. Why the bits stay the same

* Every token's list comes from the same kernels with the same per-token inputs. The index kernels (IndexerScoreBM /
  BCM / BMR, TopKSelM / MQ / MBQ / MC / MCQ, CidxFillM) give token t its own work-groups (t * gpt .. for the scores, one
  work-group per token in the selects) and read only token t's query rows, weights, score row, candidate row and block
  list, plus the key mirror, which every card holds whole and identical (every card publishes every row). A share is
  the whole block's launch with the token pointers moved to the share's first token and `m` = the share's count. The
  forms (lmax -> gpt, IDX_CAND's ccm, OWN_TOPK_Q's qb / qr) are still chosen from the whole block.
* OWN_IDX_SPLIT=1 runs gemv_m / RopeRows for 42-43 tokens instead of 256: every dense form computes each token's row with
  the same sums whatever the token count (the property every block size already relies on: tail blocks of any size give
  identical traces); RopeRows is per row. OWN_IDX_SPLIT_CHECK compares these rows bitwise too.
* The exchanges copy bytes. The queue reorder (publish + index before q_b + rope) changes no kernel's inputs.
* So every card ends with exactly the lists it computed before, and everything after them is unchanged.

Hazards (each list region is written once per block per half and read by that half's attention at the index layer and
the layers up to the next index layer):
* BCS push: starts after the selects (own event on qs), lands before the peer's XchgWaitB passes (rows, then flag, one
  in-order copy list). The next push into the same region is a block later; every block ends with all queues and copy
  lists drained. Push numbers stay equal on every card: every card pushes at the same host-order places (also with no
  tokens of its own: flags only).
* Pull: XchgPull's rule (a card rewrites its slice only after later exchanges whose flags every peer raised after its
  copy); exchange numbers stay equal on every card. In split blocks (>= 32 tokens) no store-form exchange (XchgP /
  XPUSH2) is used, and every reader of the regions exchanged before the publish ran before it.

## 4. Decode (one token) at long context: design note only

lp107: index + top-k +0.57 ms per step at 69K (8 index layers, ~70 us each). A row split would score rows [r0, r1) of
the one token on each card, gather the scores (46 KB per card at 69K, a pull ~10-15 us) and run the unchanged top-k on
every card over all rows (same list). Saving ~5/6 of the score (~50 us per layer) against ~15 us of exchange on the
step's critical path: ~0.2-0.3 ms per step (~2 %). Splitting the top-k too (local top-512 per range + an exact merge)
needs the merged list in exactly TopKSelP's order and tie rule: more work, more risk. Not done.
Draft checks (blocks of 2-6 tokens) at long context are a better target for the token split itself (one token per card;
"check 15.6-16.2 ms per cycle" at 19K-69K, lc107b), but those blocks use the XPUSH2 store exchanges; left for later.

## 5. Reset audit (2026-11-13, after the 06:02 host reset during `runs/lg/x34k_on`)

Why: the host reset about 70 s into `lg/x34k_on` (the first long document with `OWN_IDX_SPLIT=1`; `runs/lg/x34k_on.log`
ends after the weight load). Evidence: `/home/steve/dsv41-work/faults/reset-20261113T0602/` (MCA bank 30, "data fabric
sync flood"; the ten earlier resets were bank 5 core watchdogs without idxsplit). A copy-engine or kernel access outside
a valid allocation is one way to get such an error, so every idxsplit-1 read and write was checked before any rerun.

Method: read every changed line (`git -C b diff` == `idxsplit-1.patch`; `snap-is1/` == `b/`, so the binary is this
code) and every kernel the split path launches; recomputed every offset with `tools/reset_audit.py` (the engine's own
formulas + the admitted geometry of `model/directory_v41.hpp`), output in `runs/audit/reset_audit.txt`. The script's
arena layout reproduces the flag words the binaries printed (production 62133808 in `runs/lc107b/x34k_px.log`; idxsplit
64230976 in `runs/tr/k512.log` and `runs/lg/x34k_on.log`), so the numbers below are the binaries' numbers.
Code lines below: `b/experiments/own-xpu-runtime/engine/src/stage2/packet3/` (`mt` = backend_sycl_v41_mt.inc,
`hpp` = backend_sycl_v41.hpp, `k` = kernels/sycl_v41.hpp).

**Result: no defect found.** No idxsplit-1 read or write can leave its allocation at x19k / x34k / x95k (or any length up
to max_seq): every offset is bounded by the block's token count (at most 512 = mtb_n(), halves at most 256), not by the
context length, and every buffer that does scale with the context is indexed exactly as the production launch indexes it.

| what (code) | offsets (floats unless noted) | largest at x34k (33,815) | largest at x95k (95,497) | allocated |
|---|---|---|---|---|
| idx region in the arena (mt 374-399, hpp 4172-4203) | [xidxM, xidxM + 8 x 512 x 512) | 62,133,792 .. 64,230,944 | same (no context term) | arena 64,231,088 floats; copy flags at 64,230,976 (32 floats past the region) |
| slot choice (mt 1403; hpp index_slot) | slot = index_slot(L) in 0..7 (layers 2, 8, 14, 20, 24, 28, 32, 36); half at + px_tok x 512 (0 or half size x 512) | slot 7, half B: + 7 x 262,144 + 256 x 512 | same; tail halves 128 (x95k), 130 (x19k) | 262,144 per slot |
| bcs_push of the lists (mt 1408, hpp 1677) | dst/src = arena + q.off + ua[c] x 512 .. ub[c] x 512, one copy per peer (5), then the flag word xbf + 16 c | end 64,230,944 = region end; <= 88,064 bytes per peer (43 tokens) | same; tail shares 21-22 tokens (45,056 bytes) | inside the region; all edges multiples of 16 floats (64-byte lines) |
| XchgPull of the lists, plain blocks (mt 1411, 1479) | b0/b1 = a[d] x 512 .. b[d] x 512 at q.off, nslot 1 | not used: the long runs' plain blocks (x34k: 23 tokens; x95k: 9) are below OWN_IDX_SPLIT_MIN (32) | not used | (3K k256 used it: identical) |
| CidxFillM, own short tokens (mt 1237-1244, k 7456) | out + t x 512 + i, t < M, lens[t] = -1 for other cards' tokens | (px_tok + M) x 512 <= 262,144 ints | same | 262,144 ints per slot |
| selects' lists (TopKSelM / MQ / MC / MCQ, k 7542-7621) | out + u0 x 512 + t x 512, t < un, outn = 512 entries | 262,144 ints | same | same |
| scores (IndexerScoreBM / BCM, k 7467, 7623) | b.score + u0 x SS + t x SS + j, j < round32(len) | SS 34,880; largest 17,857,503 | SS 96,320; largest 49,315,039 | SS x 512 = 17,858,560 / 49,315,840 |
| layer-20 masks, bytes (TopKSelM<true>, MBQ) | b.cand + (u0 + t) x SS + r, r < len | 17,857,494 | 49,315,016 | 17,858,560 / 49,315,840 bytes |
| layer-20 block lists (blm, 2,112 ints per token) | blh + (u0 + t) x 2,112 + [0, 2,048]; BCM reads b[1 + i/8], i < 16,384 | 1,081,280 | same | 1,081,344 ints |
| q_b / rope / proj rows of the share (mt 1258-1269) | b.qn / b.xn + u0 x stride, un tokens (+ at most 8 spare token reads, as every dense form) | tokens <= px_tok + M + 8 = 520 | same | mtba_n() = 520 tokens |
| rope tables | (pos + u0 + t) x 32, pos + M <= n | 1,082,079 | 3,055,903 | max_seq x 32 = 1,114,112 / 3,080,192 |
| OWN_IDX_SPLIT_CHECK buffers (mt 464-469, 1506) | ixl2 / ixq2 / ixw2 + (px_tok + t) x 512 / 4096 / 32 | <= 512 tokens | same | 512 tokens each (diagnostic, not in the long runs) |

The share's kernels (`score_sel`, mt 1271-1378): every launch is the whole block's launch with each per-token pointer
moved by u0 x its stride (queries 4096, weights 32, scores SS, masks SS, block lists 2,112, lists 512), `lens` moved by
u0 (ln = lens + u0) and `m` = the share's count. Every kernel finds token t as its work-group (selects) or work-group /
gpt (scores) and reads only `lens[t]` and pointer + t x stride; none reads a position or another token's row (checked:
CidxFillM, IndexerScoreBM, IndexerScoreBMR, IndexerScoreBCM, TopKSelM<true/false>, TopKSelMQ, TopKSelMBQ, TopKSelMC,
TopKSelMCQ). So a share touches a subset of what the whole launch touches. The forms (gpt from the block's longest row
count, ccm, qb, qr) come from the whole block, as before: x34k qr 40, qb 8; x95k qr 96 (TopKSelMQ<96>), qb 16
(`runs/audit/reset_audit.txt`). 32-bit: arena offsets are unsigned floats (largest 64,231,087 < 2^32; bytes
256,924,352 < 2^31); push length (r1 - r0) x 4 <= 88,064; score / mask strides are size_t; row index j int <= 95,615.

What the 3K traces had not exercised (the only paths new at long context): the register selects (qr > 0 from 4,096 rows),
layer 20's register block select (qb > 0 past 16,384 rows) and the candidate-only scores + selects past layer 20 (ccm,
past 16,384 rows). All three are the production kernels on the production buffers, launched over a share as above.

Ordering / hazards re-checked (not out-of-bounds, but they would give wrong lists): push numbers are the same on every
card (ix_on depends only on options, the block and the layer; nlong comes from mlen, which every card computes the same);
each push is waited for at the same layer (ix_wait right before the attention), so a copy list never runs more than a few
pushes behind (the 64 reused events are safe); at block end every card's queue has passed every peer's last flag, so all
pushes have landed before the next block rewrites any slot; a card writes only its own tokens' lines of a split slot.

OWN_IDX_SPLIT=0 (production): the off path issues the same launches with the same arguments (tpm_index's `!split`
branch: qrows(0, M) = gemv_m(.., mt = M) as before, TokRows{rope, M, {4096, 32}} = tokr(rope, 4096, 32), score_sel(0, M)
= the old ccm / idx_r / BM / L20 / rows code with pointers + 0; tpm_layer's `else` branch is the old code); no arena
region (mt_arena_floats + 0, xidxM 0), the eight list buffers allocated as before (same dalloc calls, same order), no
CHECK buffers. The `x34k_off` run below also prints the flag word, which must read 62,133,808.

So the code gives no reason to blame idxsplit-1 for the reset; per the main thread's rule the long documents run next,
the control (OWN_IDX_SPLIT=0) first.

## 6. Results: long documents (runs/lg2, 2026-11-13 09:47-11:50)

Six runs, one per six.sh call (`plan_lg2.sh` -> `drive.sh lg2`), control first; px-512 + copy engine, 256 answer tokens,
the same binary `bin/own_run_v41_is1` with OWN_IDX_SPLIT=0 / 1. Every run exited 0, every wrapper log ends "journal
clean" (`logs/lg2-*.txt`), no STOP, no host reset. Read times from `runs/lg2/summary.txt` ("prompt: ... read on the
cards in"); answers vs `runs/e82/<doc>_plain-ids.txt` (one.sh) and off vs on by `cmp runs/lg2/<doc>_off-ids.txt
<doc>_on-ids.txt` (identical for all three).

| document | read, split off (s) | read, split on (s) | change | answer (256 tokens) | min card GiB free after load |
|---|---|---|---|---|---|
| x19k (18,692) | 28.47 | 26.64 | -1.83 s (-6.4 %) | same (off = on = reference) | 3.03 / 3.03 |
| x34k (33,815) | 53.48 | 48.57 | -4.91 s (-9.2 %) | same | 2.95 / 2.95 |
| x95k (95,497) | 166.34 | 140.72 | -25.62 s (-15.4 %) | same | 2.59 / 2.59 |

Flag words: the =0 runs print 62133808 (production layout), the =1 runs 64230976 (`grep "flags at arena word"
runs/lg2/*.log`), as section 5 computed. Section 1 predicted ~-7.3 % at x34k and ~-17.8 % at x95k against lc107b's reads
(56.1 s / 173.8 s); against today's controls the split saves 4.91 s and 25.62 s.

So: the x34k run with OWN_IDX_SPLIT=1 that was cut by the 06:02 reset completed this time (as did x19k and x95k), with
the same answers; together with the audit (section 5) nothing points at idxsplit-1 as the reset's cause, but one clean
pass does not prove it was not a trigger. Left: the uneven shares (`plan2.sh`, OWN_IDX_SPLIT_W), and adoption into the
production launch (the main thread's call).
