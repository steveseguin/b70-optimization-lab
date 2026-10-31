# Exchange in the producer's tail (F4) for the HC split sites (2026-10-31): closed

**Question.** Since the HC split, four-card decode runs 178 / 161 direct exchanges per half, about 4.5 us each. Can the
GEMV that produces a split site's rows do the exchange itself, writing the peer's rows and the flag in its tail, so the
separate `tp_xgather` kernel disappears? The base is the hc-split r1 tree (979462f7c + the fc2 and hc-split patches).
The test family is the HC split sites (102 per half on rank 1, 92 on rank 0), the one with the most exchanges.

**Answer: no. Closed for these sites.** Both forms that keep the exchange protocol lose.
- **Spread form** (`hc`: every row's storing item writes the peer's copy right after the GEMV; then the exchange
  kernel's per-group release fence, counter and flag): **wrong results**, and 1.5-1.7 ms *slower* per half.
  - Under stress it corrupted every one of five arms, on both ranks.
  - Card 1 still equalled card 0 at every dump, so only the comparison against the flag-off reference saw it.
- **Last-group form** (`hcl`: the group that completes the counter reads back the card's rows and does every peer
  store itself, then the fence and flag, as one exchange-kernel group does): **exact** under the same stress (about
  5,200 halves, five arms, both ranks, token by token and batched), but **0.46-0.49 ms slower per half**.
- Kept as default-off code: `OWNRT_TP_XTAIL=hc|hcl` in [engine-xtail.patch](engine-xtail.patch) (after the fc2 and
  hc-split patches). It is not for use.

## In plain words

- The separate exchange kernel is cheap because it spreads the peer stores over 2-16 work-groups that do nothing else.
- Moving the stores into the GEMV either spreads them over all of the GEMV's 41-640 work-groups, or funnels them through
  the one work-group that finishes last.
  - Spreading made every work-group run a system-scope fence and a shared atomic. That cost 1.5-1.7 ms per half.
  - Worse, it let a card read the peer's rows before they had all arrived, although the flag said they had.
  - Funnelling is safe but serial: one work-group writing 20 KB to the other card takes longer than the separate kernel
    it replaces.
- The equal-cards check can be fooled. Both cards consumed the same stale rows and went on to compute identical wrong
  values, so the gate that catches a race is the comparison with the unchanged engine. That gate saw it every time.

## The change ([engine-xtail.patch](engine-xtail.patch), default off)

5 files, private tree `/dev/shm/xtail-2026-10-31/tree`. The shared `engine/src` was not touched.
- **`stage2/packet6-kopt/xtail.hpp` (new): `xtail::body<R,U>`.**
  - Every subgroup runs `dense_v2::bf16_rows<R,U>` unchanged, with the same static matrix selection as
    `bf16_multi_static`, 128-item groups, and the R/U that the existing path picks (`<2,4>` gate, `<1,10>` low+inject).
  - The split matrix writes straight into the card's offset of the whole y.
  - Then comes the exchange tail. Its protocol code is copied from `single_device.cpp` `submit_exchange` mode 0:
    per-item `atomic_fence(release, system)`, group barrier, `fetch_add(acq_rel)` on the device-scope counter, and
    epoch = old/groups+1. The last group runs fence(acq_rel, system), the flag store, fence(release, system), the bounded
    poll and fence(acquire, system), and updates the same wait counters.
  - Peer stores: `hc` writes one 32-bit word per row from the item that stored it. `hcl` has the counting-complete
    group read back all of the card's rows after a device acquire fence, write them with 16-byte stores (loads first),
    then run its own system release fence and barrier before the flag.
- **`kernels.cpp` / `kernels.hpp`:** `fused_gemv_xtail`, `xtail_admits` (the dense_v2 BF16 paths except bf16split),
  and the host-side y offset in `Multiply::run`.
- **`generic_engine.hpp`:** a producer is admitted when its next launch on the same card is its `tp_xgather` (HC split
  sites only; all 204 / 184 launches admitted). Decode then issues the tail form (`gsq_xtail`: raw peer pointers
  resolved on the host, the tp_xgather's own slot), and the tp_xgather issues nothing in decode (`main.cpp`).
  - Batched prefill and row replays keep the separate exchange.
  - The tail is off under `OWNRT_TP_EXCHANGE_STATS`.
- Builds: r1 `3611caefc688` (hc), r2 `0c17f94f9279` (+ hcl with a scalar copy loop), r3 `1c70d38fff8e` (hcl with
  16-byte batched copies). [verify_receipt.py](verify_receipt.py): 979462f7c + the three patches reproduces r3's 270
  sources.

## Gates and measurements (four-card rank harness, m2 flags + `OWNRT_TP_HC_SPLIT`)

**Smoke** ([logs/s1.log](logs/s1.log), r1, `hc`): rank 1, 16 prompt rows, 8 halves.
- rc 0, 0 timeouts, but **card 1 != card 0 in `blk.42.hc.f.act`**. The assembled `blk.42.hc.f.low` was equal on both
  cards at the dump, so one card's act had read the peer's rows of the low early.
- The protocol code is the exchange kernel's. The difference is the store pattern: one 4-byte peer store per row, from
  41-640 groups across all Xe-cores and interleaved with weight streaming, instead of contiguous ranges from 2-16
  groups. The p2p qualification ([research/p2p/direct-store-2026-10-28](../../p2p/direct-store-2026-10-28/RESULT.md))
  covered 8-group contiguous stores only.

**Stress.** Five variants, each run as reference (`hs`, the separate exchange) and with the tail. Every comparison
covers the full state, every token, rank 1's exported draft-input row of every half, and both requests of the
two-request arms. Logs: [logs/st1-compare.txt](logs/st1-compare.txt), [logs/st2-compare.txt](logs/st2-compare.txt).

| variant | rank | prompt | halves | `hcl` (r2) vs reference | `hc` (r3) vs reference | card 1 == card 0 (`hc`) |
| --- | --- | --- | --- | --- | --- | --- |
| a | 1 | 128 rows token by token | 1,024 | equal (1079/1079, 1,152 exports, tokens) | **differ** (841 buffers, exports from row 144, tokens) | equal |
| b | 1 | 512 batched + 384 second request, prefill split | 768 | equal (both requests, 1,280 + 1,152 exports) | **differ** (500 + 619 buffers, exports from row 702) | equal |
| c | 1 | 960 rows token by token | 512 | equal (1,472 exports) | **differ** (932 buffers, exports from row 220, tokens) | equal |
| a | 0 | 128 rows token by token, `h` | 1,024 | equal (1029/1029, 71/71 draft, draft tokens) | **differ** (707 buffers) | equal |
| b | 0 | 384 batched + 256 second request, `hmcn`, prefill split | 512 | equal (both requests) | **differ** (707 + 137 buffers) | equal |

- About 5,200 halves ran with the `hcl` tail (3,392 on rank 1, about 1,790 on rank 0), with 0 differences.
- The same stress caught the `hc` race in 5 of 5 arms, so the test can see this class of error.
- r3's `hcl` (the 16-byte copy) was also equal to the reference in all four timing arms (64 halves each, both ranks;
  [logs/t1-compare.txt](logs/t1-compare.txt)).
- 0 exchange timeouts in every arm; kernel log clean before and after every arm.

**Half wall time** (medians, [results/t1-halves.json](results/t1-halves.json), [results/st-halves.json](results/st-halves.json)):

| rank | separate exchange (`hs`) | `hcl` r3 (16-byte copy) | `hcl` r2 (scalar copy) | `hc` (spread) |
| --- | --- | --- | --- | --- |
| 1 | 8.534 / 8.534 | 9.027 / 9.024 (+0.49) | 9.215-9.236 (+0.66) | 10.21-10.23 (+1.67) |
| 0 | 7.677 / 7.670 | 8.133 / 8.130 (+0.46) | 8.303-8.313 (+0.62) | 9.17-9.20 (+1.50) |

No end gate: the lever lost in the harness.

## What is left of F4

- The other exchange families (25 / 23 attention row splits, 25 / 23 compact expert-down, 18 / 18 GDN gated, 7 / 5 QSA,
  1 argmax) have the same choice. Either their peer stores spread over the producer's groups, which is unsafe (above),
  or they funnel through one group, which is serial. Not converted.
- One untested refinement of `hcl`: groups that make no peer store could use a device-scope release fence instead of
  the system-scope one, since only the last group writes to the peer. Applied only to the HC low (640 bytes per card,
  where the serial copy is short), its ceiling is about one exchange launch per site: about 0.05-0.1 ms per half on
  rank 1. Not built.
- The separate exchange kernel itself passed every reference comparison here (the stress references: about 5,200 halves,
  176 / 161 exchanges each). Its 2-16 contiguous-store groups are the form qualified on 2026-10-28. The race above is a
  reason not to widen that form to many scattered groups without the same reference stress.

## Files

- [engine-xtail.patch](engine-xtail.patch), [verify_receipt.py](verify_receipt.py); build receipts in [results/](results/).
- Harness (copy of hc-split's, adds `xt=TOKENS` and `tpwarn` (a card mismatch is recorded instead of halting the phase)):
  [run_phase.sh](run_phase.sh), [launch_phase.sh](launch_phase.sh), [compare.sh](compare.sh),
  [compare_driver.py](compare_driver.py), [halves.py](halves.py), [klog.py](klog.py), [archive_runs.sh](archive_runs.sh),
  [drivers/](drivers/).
- Raw runs: `/mnt/raid-models/ownrt-experiment-archives/2026-10-31/xtail-runs` (s1, st1, st2, t1; 1,324 files, `.sha256`
  beside it). Build r3 and its source tree: `.../2026-10-31/engine-builds/xtail-r3` (814 files). The `/dev/shm` copies
  are removed.
