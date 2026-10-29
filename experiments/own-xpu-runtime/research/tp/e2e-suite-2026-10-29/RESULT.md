# Four-card TP2×PP2 on the 12-prompt suite (2026-10-29)

**Question.** The exact two-card split made each pipeline rank about 1.13× faster in isolation
([direct-exchange RESULT](../direct-exchange-2026-10-28/RESULT.md)). What does the whole service gain when both ranks
run on two cards each (four cards), on the frozen suite, against the same binary on two cards?

**Answer: 1.110× faster decode, with every output identical.** Median decode **73.53 tok/s on four cards** against
**66.25 tok/s** on two cards (same binary, same flags). Every prompt gained 10.8–12.2%. All 12 answers, all token ids
and all MTP hits are the same in the three arms and equal the B19 service receipt (66.21 tok/s).

## Arms (one fresh service launch each, run once, in this order)

| Arm | Cards (rank 0 / rank 1) | Median tok/s | Mean | Range | MTP acceptance | Median TTFT | Outputs |
|---|---|---:|---:|---:|---:|---:|---|
| A: two-card control | 23 / 47 | **66.23** | 66.50 | 64.13–69.87 | 4533/5954 = 0.7613 | 812 ms | = B19, all 12 |
| B: A + `OWNRT_NO_DRAFT_TIMING=1` | 23 / 47 | **66.25** | 66.51 | 64.06–69.91 | 0.7613 | 793 ms | = B19, all 12 |
| C: B + exact TP on both ranks | 23+27 / 43+47 | **73.53** | 73.94 | 71.00–77.94 | 0.7613 | 739 ms | = B19, all 12 |

- **C vs B: 1.110×** (mean 1.112×; per prompt 1.108–1.122×). **B vs A: 1.000×.** The isolated ranks projected about 1.14×.
- B saves 0.39 ms of draft time per step in the rank-0 lab, but decode does not move: the draft is off the critical
  path. It only shortens prompt reading (TTFT −2.4%). C reads prompts 6.8% faster than B (prompt tokens run as decode
  halves in every arm).

## Identity (all arms)

- Engine `16ed1ff1a20303697efeec469ddc2d62cb37b32419359e4a5179ab9c2e7f198d`: build r10 of the direct-exchange work.
  All 262 of its compiled sources equal `engine/src` at `0b7ab6f56`
  ([receipt](../../../engine/receipts/16ed1ff1a203.json)).
- Service: a lab copy of the LAN service and adapter6 ([lab/](lab/); diffs in `lab/*.patch`), one transient unit per
  arm (`Restart=no`, `KillMode=process`, no SIGKILL, `LimitNOFILE=1048576`, nice 19, CPUs 0-3,16-19) on 127.0.0.1:18171.
  The `sc117-lan` unit was not touched.
- Flags: the B19 unit's `OWNRT_*`/`SC117_*` set (commit `eb61e0d71`), F32, split 23, MTP, greedy, 512 cap. Every arm
  also sets `NEOReadDebugKeys=1 EnableDeferBacking=0` and runs without sessions, keeper or continuation
  ([arm_env.py](arm_env.py), `logs/arm-*-unit-env.txt`).
- Arm C adds `--cards 2 --tp-replicate` and `OWNRT_TP_EXCHANGE=direct OWNRT_TP_THREADS=1 OWNRT_TP_EXPERTS=compact
  OWNRT_TP_GDN=heads OWNRT_TP_SPLIT=.attention,.gdn.qkv`, `ZE_AFFINITY_MASK=0,1` / `2,3` in PCI order (rank 1's card 0
  is 43:00.0). Pairs share a PCIe root complex (23+27 on 0000:20, 43+47 on 0000:40), each card on its own root port.
- **Differences from B19, the same in all arms:**
  - **Context 32768.** TP excludes the QSA raw ring, so TP rank 1 at 64K plans 32,432,264,812 B and is refused at the
    30 GiB cap. At 32K it plans 31,345,940,076 B ([plan-probes.json](results/plan-probes.json); plan-only, no device
    contact). The ring is off in A and B too.
  - **Prompts read token by token** (`SC117_PREFILL_ROWS=0`): batched prefill is not built under TP yet.
- VRAM (card-0 census, rank 0 / rank 1): 28.76 / 31.26 GB on one card per rank; 28.29 / 30.78 GB per card under TP.

## Gates

- **Outputs:** A, B and C give identical token ids on all 12 prompts (5,965 tokens). Their hashes, ids and per-prompt
  MTP guesses and hits equal B19. `cached_tokens=0` on every request.
- **Startup, every arm:** the F32 self-tests equal each other and the B19 record. The post-self-test state equals the
  pinned 32K oracle and the 4096 oracle as prefixes: 0 differences on both ranks.
- **Arm C:** card 1 equals card 0 on all 710 (rank 0) and 785 (rank 1) buffers both hold in full. 0 exchange timeouts or
  aborts in 7,936 / 8,024 waits per card ([tp-evidence/](results/arm-C/tp-evidence/)). The monitor saw every card held
  only by its own rank.
- **New pairs, before their first engine run:** a 4 KB round trip, then a 10 KB chain (3 × 1,440 exchanges). Both pairs
  had 0 mismatches and 0 timeouts. Added cost: 1.57 µs (23+27) and 1.61 µs (43+47), against 1.63 µs on 23+47
  ([p2p/](p2p/), `results/p2p-*.json`).

## Incidents (no device fault)

The kernel log was clean before and after every arm and pair: no xe, GuC, CAT, reset or fault lines (`logs/kernel-log-*`).
1. The first pair-smoke unit exited 127 before any device work (relative script path); relaunched with an absolute path.
2. Arm C wrote `incident.json` ("rank teardown failure") at shutdown, after the suite, and exited 1.
   - Cause: the sealed P195 transport's one-card check `len(receipt["teardown"])==1`.
   - Both TP ranks exited 0 with two complete, safe teardowns each (one per card; 0 in flight, 0 live bytes), and the
     cards drained.
   - Fix before the next TP service run: the lab adapter must accept one teardown per card.

## Files

- [results/summary.json](results/summary.json) ([compare.py](compare.py)); per arm `results/arm-*/` (suite.json, run,
  plan, monitor, requests, gate JSONs, rank logs, journal); [run_arm.sh](run_arm.sh), [plan_probe.py](plan_probe.py).
- Raw run directories (491 files, 124,392,622 B; count, bytes and sha256 verified):
  `/mnt/raid-models/ownrt-experiment-archives/2026-10-29/tp-e2e-suite-20261029/`.

## Next

1. Accept per-card teardowns in the lab adapter, then move TP into the service path.
2. Batched prefill under TP (direct-exchange RESULT, route 1 or 2). 64K also needs either the ring under TP or
   Stage 3's halved QSA KV.
3. Stage 3 (QSA split), and moving the split point now that both stages run about 1.13× faster.
