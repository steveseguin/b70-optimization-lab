# Four-card prefill overhead (2026-10-30/31): where the ~120 ms per chunk over a perfect split goes

Status: **done; lever 3 is committed to engine/src, default off.**

**Result: four-card long prompt 222.53 → 219.36 / 219.29 s, exact** (`OWNRT_PREFILL_GDN_REGS=1`, set
`tptsxqckhcbg`, build r6 `9885e8ad63fd`; fresh servers at 131072, both arms on r6).
- Decode is unchanged: 84.35 → 84.23 / 84.50 tok/s after the long prompt; suite median 87.43 → 87.61 / 87.62.
- Outputs equal the 3+1 262K reference, and the suite equals B19.

How we got there:
- Attribution is complete: M1/M4, a shape probe under batched prefill, and a drain trace.
- Lever 1, expert-parity assignment, is exact but slower, so it is closed. Its loss is explained by card imbalance.
- Lever 2, a row-parallel batched conv, is closed: no gain, and a race when the history is updated in place.
- Lever 3 keeps GDN state rows in registers across batched rows: exact; −4.6 / −8.3 ms per chunk on the harness.
- Lever 4 (replace the per-pair host drains) is closed at its measured ceiling: 0.9 / 1.6 ms per chunk.
- A codegen lesson is recorded in DO-NOT-REPEAT: a default-off branch in a shared generic kernel cost 1.4% of decode.

Lane: SC117 four-card TP (`tptsxqckhcb` on build `e6daa268a3a8`, commit 979462f7c, TTFT 222.5 s at 131072).
- Rank 0 runs on 23:00.0+27:00.0 (layers 0-22, lookups, MTP draft). Rank 1 runs on 43:00.0+47:00.0 (layers 23-47, head).
  The rank harness puts rank 1 on 23+47.
- A 131072-token prompt is 476 chunks of 256 rows, and TTFT ≈ 476 × the slower rank's chunk. In the long runs that is
  rank 1 at 466 ms and rank 0 at 446 ms (target chunk 414 ms plus the draft command).

## Attribution per 256-row chunk

| ms per chunk | rank 1 | rank 0 | how measured |
| --- | ---: | ---: | --- |
| one card, device (target only) | 674.5 | 589.4 | M1: `--timing class` + `OWNRT_SITE_TRACE=1`, every site its own class |
| perfect split (one card / 2) | 337.3 | 294.7 | |
| replicated work, excess over half | 49.0 | 48.3 | probe; HC 33 / 30, shared expert 11.6 / 10.3, the rest small |
| split work that does not halve | 31.5 | 36.6–38.0 | probe vs one card, per class (below) |
| route compaction (TP only) | 1.4 | 1.3 | probe |
| **= device busy per TP card (probe)** | **419.1 / 420.1** | **380.9 / 382.3** | card 0 / card 1 shapes, measured on 23:00.0 |
| exchange kernels, own + wait | 19.5 | 18.1 | M4 `OWNRT_TP_EXCHANGE_STATS=0`; experts 14.0 / 12.9 |
| card balance at the drains (Σ\|diff\|/2) | 3.9 | 5.4 | drain trace |
| drain turnaround (later card done → exchange issued) | ~2.3 | ~2.0 | drain trace |
| chunk inputs + final readback with the cards idle | 5.9 | 9.8 | host trace (final minus its blocked part) |
| not attributed | ~10 | ≈ −2 | rank 1; not drain or device restart: skipping the drains saves only 0.9 ms (Lever 4 ceiling) |
| **TP wall (prefill_chunk, host trace)** | **461–464** | **413–415** | A arms g1/u1/u2/p2 |

Split work that does not halve, per TP card ([results/p-r1-probe.json](results/p-r1-probe.json),
[results/p-r0-probe.json](results/p-r0-probe.json)):

| class | one card | per TP card | not halving, rank 1 / rank 0 |
| --- | ---: | ---: | ---: |
| routed experts (gate, up, down) | 352.5 / 288.7 | 198.5–199.3 / 170.4–171.8 | 22.3 / 26.1–27.4 |
| GDN recurrence (24 of 48 heads) | 48.3 / 47.5 | 31.0 / 30.9 | 6.9 / 7.2 |
| GDN conv (half the channels) | 7.8 / 7.6 | 7.5 / 7.4 | 3.6 / 3.6 (it does not shrink at all) |
| QSA attention (one KV group) | 17.3 / 11.8 | 9.9 / 6.9 | 1.2 / 1.0 |
| attention out-proj, QSA pool | | | −1.1 / −0.8, −0.9 / −0.7 |

- The probe runs card c's TP launches on one card. Its routes come from perturbed rows, since the peer's rows are never
  written. Replicated classes moved by −3.9 / −3.6 ms in total.
- The M=128 one-card proxy for the experts (24.5 / 6.6 ms) agrees on rank 1 but under-predicts rank 0.
- Each TP card runs 75 (rank 1) / 69 (rank 0) exchanges per chunk, moving 439 / 404 MB per card
  ([CPU work model](tp_work_model.py)).

**Card balance (drain trace, [results/p-r1-a-dt-drain.json](results/p-r1-a-dt-drain.json),
[results/p-r0-a-dt-drain.json](results/p-r0-a-dt-drain.json)).**
- `prefill_exchange` drains both cards before every pair, so the exchange statistics' wait (0.6 ms) cannot see a card
  that finished early.
- The drain trace polls both cards' last submissions and logs when each completes, when the drain returns, and when
  each exchange is issued.
- Rank 1: an early card idles 5.8 / 6.6 ms per chunk (balance 3.8 / 3.9 + turnaround 2.0 / 2.7). Neither card is
  systematically later.
- Rank 0: card 0 idles 11.6 ms against 3.2 ms for card 1. Card 1 (27:00.0) finishes later in 19 of 23 expert segments
  and 13 of 18 GDN segments, about 9 ms more card work per chunk. The probe gives both shapes equal work on one card, so
  this is card 27 itself, or real routes.
- The trace is exact (state and exports equal) and costs at most 2 ms of wall time.

## Lever 1: expert-parity assignment (`OWNRT_PREFILL_EXPERT_PARITY=1`), exact, closed

Each TP card computes the slots whose expert id has its parity, instead of compact slots c, c+2, ….
- Each expert's weights are read by one card, and its tiles are about twice as full.
- Implementation: a RouteParity kernel splits the routes, with skip routes for the other card's slots, which the
  expert-grouped bucket drops. Exchange mode 2 stores only the owned expsdown rows into the peer.
- Patch: [engine-expert-parity-r2.patch](engine-expert-parity-r2.patch). It also includes the r2-only `#if 1`
  tile-config sweep list.

Exactness: the s2 smoke, g1, u1, u2 and p2 matched 1079/1079 buffers + 1116 exports on rank 1 and 1029/1029 + 71/71 draft
on rank 0. The parity arm was also checked against token-by-token and against one card (patterns hmcn and m).

| arm, ms per chunk | rank 1 | rank 0 |
| --- | ---: | ---: |
| A (g1 / u1 / u2 / p2) | 464.1 / 465.1 / 463.1 / 461.2 | 414.3 / 413.7 / 412.9 / 414.5 |
| parity, T=4 tiles (g1 / p2 with drain trace) | 457.0 / 456.6 | 430.3 / 430.7 |
| parity, launch divisor 1 / 16 (u1) | 459.1 / 461.7 | 432.9 / — |
| parity, T=8 tiles, configs 6 / 4 (u2, build r2) | 482.8 / 502.4 | 442.6 / 464.2 |

**Why it loses (drain trace, p2).**
- Parity splits the expert work unevenly between the cards: Σ|diff| per chunk goes from 7.7 to 17.9 ms on rank 1 and
  from 10.7 to 36.0 ms on rank 0, almost all of it in the expert segments.
- Mean card work is the wall minus Σ|diff|/2. Parity saves about 12 ms of it on rank 1 but costs about 4.8 ms more on
  rank 0; the rank-0 cause is not measured.
- A balanced expert ownership, with whole experts assigned per layer and chunk to even out the slots, would be worth
  about 12 ms on rank 1 only.
- Ledger row: [service-speed DO-NOT-REPEAT](../../../gsq-rco-iq3s/service-speed/DO-NOT-REPEAT.md).

## Lever 2: row-parallel batched conv (`OWNRT_PREFILL_CONV_ROWS=1`, build r4 `da02f3346fe9`), closed

How the conv runs today:
- The generic conv kernel runs one lane per channel and loops the chunk's rows in sequence.
- The probe sized it at 7.5 ms per chunk per TP card (7.8 on one card). The conv has no output recurrence: row r reads
  only the inputs of rows r−3d … r.

The change: with the flag, one lane per (row, channel), the same four products in the same order, and the last row's
lanes write the final history ([engine-conv-rows.patch](engine-conv-rows.patch)).

| 1100-row harness, ms per chunk | A | conv rows |
| --- | ---: | ---: |
| rank 1 | 466.0 | 465.0 |
| rank 0 | 415.7 | 411.7 |
| one card (rank 1) | 688.2 | 690.4 |

- **No gain beyond noise.** The probe's conv time is its class-timing event duration, not what it costs in the stream.
  Small-kernel probe sizes are upper bounds.
- **Not exact as built.** The 16-row-chunk rank-1 smoke differs from two independent A references, from layer 32 on in
  the 8-row chunk. The two references (s2-r1-a and ps-r1-dt) agree with each other.
  - Cause: the conv history is updated in place. The last row's lanes write it while lanes of rows 0–2 may still be
    reading the old values. The original loop read before writing in the same lane.
  - The 256-row compares happened to be equal.
  - A correct version needs one head group per channel block that reads the old history first. Not pursued, since it
    gives no gain.
- Ledger row: [service-speed DO-NOT-REPEAT](../../../gsq-rco-iq3s/service-speed/DO-NOT-REPEAT.md).

## Lever 3: GDN state rows in registers across batched rows (`OWNRT_PREFILL_GDN_REGS=1`, build r5 `66524d88054d`)

What the consumer kernel does today:
- The prefill GDN recurrence is round2's consumer kernel (`round2_submit.cpp` `gdn_device`, after the GDN_PREP
  producer). It runs one 32-lane subgroup per state row (h, j); 6144 on one card and 3072 per TP card.
- For every row of the chunk it reloads the 128-float state row from global memory and stores it back. A device-scope
  subgroup barrier follows each row.

The change:
- With the flag, over two or more rows, each subgroup keeps its state row in registers between rows.
- The kept values are rounded exactly as the store/load round trip rounds them (`Args::rnd`: identity in F32, the
  BF16 bits otherwise). The row is stored after the last row only, and the per-row barrier is gone.
- Each subgroup owns its state row, so this is safe even when the in and out banks alias. Every row's output is
  unchanged. Decode (one row) never sets the flag.
- About 15 lines in `kernels.hpp`, `adapter.cpp` and `round2_submit.cpp`
  ([engine-prefill-levers.patch](engine-prefill-levers.patch) holds levers 2 and 3).

| 1100-row harness (q1), ms per chunk | A1 | B1 | A2 | B2 | change |
| --- | ---: | ---: | ---: | ---: | ---: |
| rank 1 (TP) | 465.3 | 459.5 | 466.2 | 460.3 | **−5.9** |
| rank 0 (TP) | 418.6 | 407.0 | 415.9 | 409.8 | **−8.9** |
| one card (rank 1) | 690.1 | 678.3 | | | **−11.8** |

Exactness:
- Rank 1: 1079/1079 buffers + 1116 exports equal, in A1/B1, A2/B2 and A1/A2.
- Rank 0: 1029/1029 + 71/71 draft equal in both pairs.
- One card on vs off equal.
- Both 16-row smokes (8-row tail chunk) equal to the independent A references (ps-r1-dt, s2-r0-a).
- 0 kernel-log faults.

### Servers at 131072 on r5, A/B/B (both arms on r5; [results/suite-r5/](results/suite-r5/))

Every server passed its 13/13 startup gate. 15 kernel-log checks, 0 faults.

| server | A `tptsxqckhcb` | B1 `tptsxqckhcbg` | B2 `tptsxqckhcbg` |
| --- | ---: | ---: | ---: |
| TTFT, 121,854-token prompt | 224.35 s | **221.51 s** | **221.33 s** |
| decode after it (all 511) | 83.12 tok/s | 82.55 | 83.34 |
| 512 outputs = 3+1 262K reference | yes | yes | yes |
| MTP hits / guesses | 418 / 511 | 418 / 511 | 418 / 511 |
| 3,490-token TTFT | 6.676 s | 6.586 | 6.587 |
| 12-prompt suite median (B19 ids/sha/MTP equal) | 86.29 | 86.08 | 86.21 |
| rank 1 busy per chunk | 470.2 ms | 464.3 | 463.9 |
| rank 0 critical per chunk (prefill + draft) | 464.9 ms | 459.1 | 459.0 |

**Codegen regression in r4/r5.** r5's default path is about 1.4% slower than the committed binary.

| decode-half median, same harness (ms) | rank 1 | rank 0 |
| --- | ---: | ---: |
| e6daa268a3a8 | 9.31 | 8.42 |
| r3 | 9.33 | 8.43 |
| r4 | 9.46 | 8.53 |
| r5 | 9.48 | 8.54 |

- The default prefill chunk is about 3–4 ms slower too.
- r4 added the conv-rows branch, which is never taken with the flag off, inside the generic `ng::group()`. Decode's
  norm, mix and activation ops run that same kernel.
- Lesson recorded in DO-NOT-REPEAT. Lever 3 was therefore rebuilt clean.

### r6 `9885e8ad63fd`: HEAD + lever 3 only ([engine-gdn-regs.patch](engine-gdn-regs.patch); `adapter.cpp`, `kernels.hpp` flag and validate, `round2_submit.cpp`)

- **Exactness (e1), all equal:**
  - both 16-row smokes against the independent A references;
  - 1100-row on/off on both ranks;
  - r6's default state against r3 / e6daa268a3a8 (1079 + 1116 exports, 1029 + 71 draft);
  - pattern m against g1;
  - sp=64 on/off on both ranks, both requests, ones and inventories;
  - one card on/off.
- **Decode gate (e2, hard limit 0.3%; [decode_gate.py](decode_gate.py)).** r6 A against e6daa268a3a8 A, interleaved
  ×2, all four cards held: rank 1 9.333 vs 9.328 ms (**+0.06%**), rank 0 8.419 vs 8.413 ms (**+0.07%**). Passed.
- **Prefill per chunk (e2, 1100-row harness), r6 A → B:** rank 1 462.1 → 457.4 (**−4.6**), rank 0 412.6 → 404.2
  (**−8.3**). e6daa268a3a8's own A is 463.4 / 411.4. The e2 compares (e6 vs r6 A, r6 A vs B, e6 vs r6 B) are all
  equal.

### Servers at 131072 on r6, A/B/B (both arms on r6; [results/suite/](results/suite/), [results/suite/summary-r6.json](results/suite/summary-r6.json))

Every server passed its startup gate. 20 kernel-log checks, 0 faults. Long-request timelines:
[results/long-trace-tptsxqckhcb-r2.json](results/long-trace-tptsxqckhcb-r2.json),
[-r3](results/long-trace-tptsxqckhcbg-r3.json), [-r4](results/long-trace-tptsxqckhcbg-r4.json).

| server | A r2 `tptsxqckhcb` | B r3 `tptsxqckhcbg` | B r4 `tptsxqckhcbg` |
| --- | ---: | ---: | ---: |
| **TTFT, 121,854-token prompt** | **222.53 s** | **219.36 s** | **219.29 s** |
| decode after it (all 511) | 84.35 tok/s | 84.23 | 84.50 |
| 512 outputs = 3+1 262K reference (`bf1f0867d1bd`) | yes | yes | yes |
| MTP on the long request (hits / guesses) | 418 / 511 | 418 / 511 | 418 / 511 |
| 3,490-token prompt TTFT | 6.611 s | 6.509 | 6.501 |
| 12-prompt suite median (ids, sha, MTP = B19) | 87.43 tok/s (yes) | 87.61 (yes) | 87.62 (yes) |
| rank 0 prefill per chunk (median) | 446.2 ms | 440.0 | 440.3 |
| rank 0 draft chunk (median) | 13.8 ms | 13.7 | 13.7 |
| rank 0 critical per chunk | 459.9 ms | 453.7 | 453.8 |
| rank 1 busy per chunk / idle in the prompt | 466.4 ms / 0.03 s | 459.8 / 0.03 | 459.6 / 0.03 |

- A on r6 reproduces the committed lane: 222.50 s, 84.4–84.6 tok/s, suite 87.5. The default path is clean.
- B saves 6.6 ms per chunk on rank 1, which sets the pace, and 6.2 ms on rank 0. Rank 0 now trails rank 1 by only about
  6 ms per chunk, so a further cut on rank 1 alone is worth at most about 3 s.
- Work directories are archived (sha256) at `.../2026-10-31/prefill-tp-overhead-suite-r6`. r5's servers are at
  `.../2026-10-31/prefill-tp-overhead-suite-r5`.

## Lever 4 ceiling: no host drain before the exchange pairs, closed (2026-10-31)

Question: the ~2 ms turnaround plus the ~10 ms rank-1 remainder (about 0.13 ms per pair) might be the host drain and
the device restart before every exchange pair. If so, a receiver-ready handshake inside the exchange kernel would
remove them.

Ceiling measurement:
- Diagnostic: the timing-only `OWNRT_PREFILL_DRAIN_SKIP=1` skips the card-0 drain before each pair.
- Build: r7 `9139cd812e2d` = HEAD + [engine-drain-skip-diagnostic.patch](engine-drain-skip-diagnostic.patch); not
  committed.
- Bar (coordinator's rule): build the handshake only if the ceiling is ≥ 8 ms per chunk on both ranks.

| 1100-row harness, ms per chunk (A/B/A/B; A = tptsxqckhcbg) | A1 | skip1 | A2 | skip2 | ceiling |
| --- | ---: | ---: | ---: | ---: | ---: |
| rank 0 (TP, 131072) | 404.24 | 403.40 | 404.97 | 402.67 | **1.6** |
| rank 1 (TP, 65536, shadow packing off in both arms) | 458.27 | 457.40 | 459.48 | 458.49 | **0.9** |

- **Closed.** Ledger row in [service-speed DO-NOT-REPEAT](../../../gsq-rco-iq3s/service-speed/DO-NOT-REPEAT.md).
- The ~10 ms left unattributed on rank 1 is not drain or restart cost.
- Without packing, skipping the drains was exact: all compares equal, including exports. The peer can be at most one
  exchange ahead, and every unpacked role's last reader precedes the next write.
- With rank 1's shadow packing the first attempt was not safe. Phase k1's 16-row smoke hit a sticky rank error (no
  device fault, no exchange timeout), because packed live ranges assume peer stores land at the drained exchange.
- 0 kernel-log faults in k1 and k2.

## Remaining plan (not built)

Rank 0 now trails rank 1 by only about 6 ms per chunk (459.8 vs 453.7 critical; the critical figure includes the draft
chunk). So a lever that helps rank 1 alone is capped at about 6 ms per chunk (about 3 s) until rank 0 also drops.

| lever | rank 1 | rank 0 | note |
| --- | ---: | ---: | --- |
| HC low/gate row split | about 12 measured (TTFT −5.6 s) | ≤ 31 sized | the HC-split agent's patch; the largest; both ranks |
| rank-0 lookup rows of chunk k+1 prepared while chunk k runs | — | ≤ ~5–7 | the cards idle 6.9 ms per chunk in rank 0's inputs phase (host lookups); exact (host only); unblocks the rank-1 levers |
| balanced expert ownership (whole experts per card, balanced per layer and chunk) | ~12 | ~0 | parity minus its imbalance; worth ≤ 6 until rank 0 drops |
| rank-1 input upload / output readback overlapped with the device | ~3–5 | — | 5.9 ms per chunk of idle host phases |
| copy-engine overlap of the expert exchange | ≤ 13–14 | ≤ 13 | **left alone**: BCS fault history |
| device-side drain handshake | 0.9 | 1.6 | closed (ceiling above) |

Suggested order:
1. Merge the HC split. It is the biggest, and it applies to both ranks.
2. Rank-0 lookup prefetch.
3. Balanced expert ownership together with the rank-1 host-phase overlap.

Each lever should be timed on the 1100-row harness, A/B/A/B, against the decode-half gate, before any build is
promoted.

## Builds and patches (r1–r5 from the private tree `/dev/shm/pto-engine-20261030`, r6 from `/dev/shm/pto-engine-20261031-gdn`; only lever 3 is committed to engine/src)

- r1 `09328de33c90`: parity. r2 `62119fe983ad`: parity and the tile sweep list. Both are archived.
- r3 `d6835fcb2967`, the probe build, adds three diagnostics, all default off:
  - `OWNRT_TP_SHAPE_PROBE` under batched prefill (compact extents, route compaction and slot rows for the probed card);
  - `OWNRT_PREFILL_DRAIN_TRACE`;
  - parity.
  Patch: [engine-pto-diagnostics.patch](engine-pto-diagnostics.patch). The default-path state equals e6daa268a3a8's
  (1079 / 1029 buffers).
- r4 `da02f3346fe9`: r3 plus lever 2 ([engine-pto-r4.patch](engine-pto-r4.patch)).
- r6 `9885e8ad63fd`: engine/src HEAD plus lever 3 only, from the clean private tree `/dev/shm/pto-engine-20261031-gdn`.
  Its receipt, `engine/receipts/9885e8ad63fd.json`, pins that tree. **This is the build to promote.**
  - The committed engine/src files (`adapter.cpp`, `kernels.hpp`, `round2_submit.cpp`) are byte-identical to the tree's.
  - The binary reads its rope table from the tree, so a durable copy should be rebuilt from engine/src.
  - [engine-gdn-regs-on-fc2-hcsplit.patch](engine-gdn-regs-on-fc2-hcsplit.patch) is the same change 3-way rebased onto
    the fc2 + HC-split tree. It merges with fc2's `gdnr` StaticState read and applies to the AOT agent's copy of that
    tree (`git apply --check`).
- r7 `9139cd812e2d`: HEAD (lever 3 included) plus the timing-only drain skip, from `/dev/shm/pto-engine-20261031-xk`
  ([engine-drain-skip-diagnostic.patch](engine-drain-skip-diagnostic.patch); not committed). Receipt
  `engine/receipts/9139cd812e2d.json`.
- r5 `66524d88054d`: r4 plus lever 3 ([engine-pto-r5.patch](engine-pto-r5.patch)). Its receipt,
  `engine/receipts/66524d88054d.json`, pins the private tree. The r4 receipt is stale, since lever 3 edited the same
  files after r4 was built.

## Files and archives

- Harness: copies from prefill-draft-batch-2026-10-30. Extras added: `st1`, `xs=N`, `xp`, `gd=N`, `ex=N`, `dt`, `cv`, `gx`, `xk`,
  modes `probe0|probe1`.
- Analyzers: [analyze_class_times.py](analyze_class_times.py), [analyze_exchange_stats.py](analyze_exchange_stats.py),
  [analyze_probe.py](analyze_probe.py), [analyze_drain_trace.py](analyze_drain_trace.py).
- Runs, raw (sha256-verified): `/mnt/raid-models/ownrt-experiment-archives/2026-10-30/prefill-tp-overhead-runs-*`
  (s1m1, s2, g1, d1, u1, u2, p1, p2, c1, q1), and under `2026-10-31/` (e1, e2). From c1 on, state bundles are dropped after
  each arm; the compares use state.json hashes.
- Builds: `/mnt/raid-models/ownrt-experiment-archives/2026-10-30/engine-builds/prefill-tp-overhead-20261030-r{1,2}`.
- Kept evidence (state hashes, host / drain traces, class times): [evidence/](evidence/). Kernel-log checks:
  [logs/](logs/).
