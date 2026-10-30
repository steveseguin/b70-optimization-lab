# Four-card prompt reading at 131,072: the bottleneck, five opt-in changes, and a service gate failure (2026-10-29)

**Question.** On the four-card layout (two pipeline ranks, each split exactly across two cards; flags `tptsxqc`, binary
`aafd258dd5ea`) a 121,854-token prompt took 355 s to its first token, against 241–251 s on the 3 targets + 1 draft 262K
layout. Where does the time go, and can exact changes close the gap?

**Answer (stopped at a gate failure; no TTFT measurement of the fix yet).**
- **Bottleneck, measured:** rank 0 is the critical path. Per 256-row chunk it spends 518 ms on its prefill and 229 ms
  replaying the MTP draft row by row (256 commands of 0.89 ms), 747 ms × 476 chunks = 355 s. Rank 1 needs 515 ms per
  chunk and waits about 230 ms. The ranks are already pipelined one chunk apart.
- **Inside a chunk:** the TP prefill is mostly device-bound (the host waits on the cards 331 / 376 ms of 492 / 508 ms).
  Its one large host-paced piece is `moe_combine`, replayed row by row (78–86 ms). The draft replay is device-bound
  (0.79 ms per row even with no host waits): each prompt row computes a full layer whose outputs are never read.
- **Built (opt-in, exact in 38 rank-harness comparisons):** a multi-row `moe_combine` for prefill, once-per-chunk exchange
  zeroing, batched lookup uploads, one draft command per chunk, and KV-only draft prompt rows (17 of 46 sites).
  Harness per chunk: rank 0 492 + 210 → 437 + 60 ms, rank 1 508 → 466 ms.
- **Service:** server A (current flags, this binary) reproduced the baseline: TTFT 356.6 s, decode 75.95 tok/s, all 512
  outputs equal the 3+1 262K reference. Server B (the fix) **failed the service's batched-prefill startup gate**: a
  request reset zeroed the native `moe_combine`'s ones buffer, which the harnesses (one prompt per process, no reset)
  never exercised. Stopped there as instructed. The one-line fix is in `engine/src` (build r7 `b51c9e8d803e`), not
  device-gated.
- Projection, **not a measurement** ([results/projection.json](results/projection.json)): about 249 s TTFT on the long
  request, against 241–251 s on 3+1.

## 1. The measured bottleneck

**Retained long request** ([analyze_long_trace.py](analyze_long_trace.py) on both ctx131072 servers' `native-result.json`
rank traces; [results/bottleneck.json](results/bottleneck.json)):

| Per 256-row chunk (476 chunks) | Server 1 | Server 2 |
|---|---:|---:|
| rank 0 prefill busy (median) | 518.6 ms | 518.0 ms |
| rank 0 draft replay (256 one-row DRAFT commands, 0.89 ms each) | 228.0 ms | 227.0 ms |
| **rank 0 critical path per chunk** | **746.8 ms** | 745.4 ms |
| rank 1 prefill busy (median) | 516.9 ms | 517.1 ms |
| totals: rank 0 prefill / draft / rank 1 busy / rank 1 idle | 246.4 / 109.1 / 245.2 / 109.8 s | 246.1 / 108.7 / 245.3 / 109.0 s |

- The ranks are already pipelined one chunk apart: rank 0 runs draft(k−1) then prefill(k+1) while rank 1 runs prefill(k)
  (`native_controller.hpp`), and rank 1's chunk k starts 5 µs after rank 0's chunk k ends.
- **Rank 0 is the critical path**: 747 ms × 476 = 355.5 s. Its per-row MTP draft replay (122,205 commands, 109 s) is
  30% of TTFT. Rank 1 waits about 230 ms in every chunk.

**Host versus device inside a chunk** (one short device run per rank, profile-free: `OWNRT_PREFILL_HOST_TRACE=1`, host
clocks only; rank harnesses at 131,072, 1,100 rows; [results/harness-timing.json](results/harness-timing.json)):

| Per full chunk | Rank 0 | Rank 1 |
|---|---:|---:|
| wall | 492 ms | 508 ms |
| host blocked on the cards (at the exchange drains) | 331 ms | 376 ms |
| host active | 160 ms | 130 ms |
| of which `moe_combine` replays (256 rows × 2 commands, per layer and card, one host thread) | 86 ms | 78 ms |
| inputs (rank 0: embedding/PLE rows computed on the host, 1,024 synchronous uploads; cards idle) | 16.8 ms | 3.1 ms |
| exchange pairs per chunk (each: drain, 2 synchronous uploads, drain) | 69 | 75 |
| submissions per card | 15,374 | 15,855 |
| draft replay, per row (per-row path): inputs / issue / blocked | 0.04 / 0.23 / 0.52 ms | — |

- The TP prefill itself is mostly device-bound. Its one large host-paced piece is `moe_combine`, replayed row by row:
  while the host issues one card's 512 commands, the other card is idle.
- The draft replay is device-bound too: issued without any host waits (one command per chunk) it still takes 0.79 ms per
  row. What makes it slow is the work each row does (a full layer: selection, attention, routed FP8 experts, shared
  expert), not the host.
- A head-off prompt row of the draft leaves only its KV/index-key append and the position commit. The rest of the row
  is overwritten by the next row or decode step before anything reads it, the same reason prompt rows skip the head.

## 2. What was built (engine `300e6f8c46ad`; the ones fix in r7 `b51c9e8d803e`; all opt-in, default paths unchanged)

| Flag | Rank | Change |
|---|---|---|
| `OWNRT_PREFILL_MOE_NATIVE=1` | both | `moe_combine` for all M rows in two launches per card: `epilogue_f32_rows` (the F32 slot sum, the same per-element expression as `CombineF32`) into an M-row mixture, then the unchanged generic/ew `moe_combine` with tokens=M (row r's elements at r·width+k). The adapter admits moe_combine rows only with the flag. |
| `OWNRT_PREFILL_XZERO_ONCE=1` | both | the prefill exchange slots (one pair per slot per chunk) zeroed once per chunk on both cards, instead of two synchronous uploads and a second drain per pair; every pair still starts drained, epoch 1. |
| `OWNRT_PREFILL_LOOKUP_BATCH=1` | 0 | the same lookup rows, same order and history, written with one upload per lookup and card. |
| `OWNRT_DRAFT_CHUNK_REPLAY=1` | 0 | the draft replay of a chunk in one rank-0 command (op 29, `prefill_wire.hpp`): rank 1's rows from the reverse buffer, the confirmed tokens in the prefill header's unused tail; each row's BF16 inputs staged in pinned memory and loaded by an ordered copy before the row's prepared commands; extent admission per row as before; one error read per chunk. |
| `OWNRT_DRAFT_CHUNK_KV_ONLY=1` | 0 | with chunk replay: a head-off prompt row issues only the draft sites its lasting state needs (17 of 46 non-head sites), by backward liveness over the draft plan from the persistent KV buffers (merge stage I/O taken from `direct()`; `qsa_prepare` per output, so `qgate` and `iq` are skipped; `begin`/`commit` always). The derivation refuses to run if any other value is live at the start of a row ([draft-chunk-sites.json](evidence/g5/g5-r0-ko/draft-chunk-sites.json)). |
| `OWNRT_PREFILL_HOST_TRACE=1` | both | diagnostic host timing (above). |

Kept per prompt row: the merge stage, `begin`, `hc.a` (norm, low, act, gate, mix), `qsa.k/v/ik`, `prepare`, `pool`,
`commit`. Skipped: `hc.a.inject`, `qsa.qgate/iq/select/attention`, the output projection, `hc.f`, router, routing, the
routed and shared experts, `moe`, `ffn.combine` (and the head, as before).

**Harness timing at 131,072** (full chunks after the first; [results/harness-timing.json](results/harness-timing.json)):

| | Rank 0 chunk | Rank 0 draft / 256 rows | Rank 0 total | Rank 1 chunk |
|---|---:|---:|---:|---:|
| flags off | 492 ms | 210 ms (per-row) | 702 ms | 508 ms |
| + moe native, xzero, lookup batch, chunk replay | 434 ms | 201 ms | 635 ms | 465 ms |
| **+ KV-only draft rows** | **437 ms** | **60 ms** | **497 ms** | **466 ms** |

## 3. Rank-harness gates (38 comparisons, all equal; [results/gates.json](results/gates.json)); the service gate is in section 4

Rank harnesses at 131,072, 1,100 prompt rows in 256-row chunks (the raw ring wraps twice), 16 decode halves; rank 1 on
23+47, rank 0 on 23+27 with hit/miss/cancel (`hmcn`) and all-miss (`m`) speculation. Every new path ran first as the
smallest smoke (40 rows in 16-row chunks, 4 halves). Final binary `300e6f8c46ad` (phase g5):

| Comparison | Rank 1 | Rank 0 target / draft |
|---|---|---|
| flags off vs previous binary `aafd258dd5ea` (archived ctx131072 k2 runs) | 1079/1079 | 1029/1029 / 71/71, tokens equal |
| flags on vs flags off | 1079/1079 | 1029/1029 / 71/71, tokens equal |
| flags on, batched vs token by token | 1079/1079 (and vs the previous binary's tbt run) | 1029/1029 / 71/71, tokens equal |
| flags on vs one card at 65,536 (prefix + zeros) | 1058 + 21 | 1009 + 20 / 67 + 4 (`hmcn` and `m`) |
| flags on, all-miss `m` vs previous binary | — | 1029/1029 / 71/71 |

- The draft's 71 buffers are compared after the decode halves, so the KV-only rows must leave every buffer exactly as the
  full replay does once decode has run, and the 16 draft guesses must be equal; they are.
- The same comparisons also passed on the intermediate builds (g1 r2 four flags, g3 r4 KV-only with prepare unrefined).
- 0 exchange timeouts or aborts. Kernel log clean before and after every arm.

## 4. Service at 131,072, fresh servers

Fresh lab services at 131,072 on binary `300e6f8c46ad` ([suite.sh](suite.sh), [run_arm_suite.sh](run_arm_suite.sh); all
four card locks held by `sc117-tp-svc-pfs-locks-20261029`; `NEOReadDebugKeys=1 EnableDeferBacking=0`,
`LimitNOFILE=1048576`; order A, B1, B2; [results/suite/summary.json](results/suite/summary.json)):

| Server | Startup batched-prefill gate | Suite median (mean) tok/s | Outputs | TTFT, 3,490 tokens | 121,854 / 512: TTFT, decode, outputs |
|---|---|---:|---|---:|---|
| A `tptsxqc-r1` (current flags) | 13/13 | 78.34 (78.70) | = B19, all 12 | 9.94 s | **356.6 s**, 75.95 tok/s, all 512 = 3+1 262K reference (`bf1f0867d1bd…`) |
| B1 `tptsxqck-r1` (the fix) | **FAILED: 6 of 9 batched cases** | 78.71 (78.95) | = B19, all 12 | 35.6 s (read token by token after the failed gate) | not run (server stopped) |
| B2 `tptsxqck-r2` | — | — | — | — | not started (chain halted) |

- A's long request matches the retained ctx131072 servers (355.8 / 355.1 s) and has the same timeline: rank 0 247.2 s
  prefill + 109.0 s draft replay, rank 1 245.1 s busy and 110.7 s idle ([results/long-trace-tptsxqc-r1-c131072.json](results/long-trace-tptsxqc-r1-c131072.json)).
- **B1's gate failure** ([logs/incident-b1-prefill-gate.txt](logs/incident-b1-prefill-gate.txt), [prefill-gate.json](results/suite/arm-tptsxqck-r1-c131072/prefill-gate.json)):
  every case that reads at least one full chunk (258, 259, 514, 581 tokens with 256-row chunks; 53 and 40 tokens with
  13- and 7-row chunks) differs from token by token in tokens, MTP guesses and all persistent state of both ranks. The
  three cases below the bulk threshold pass.
  - Cause: `request_reset` zeroes every live non-weight allocation and restores only the engine's one-row `one`. The
    M-row ones of `OWNRT_PREFILL_MOE_NATIVE` were written once, at allocation, so after the first reset every batched
    `moe_combine` used a zero mixture.
  - The rank harnesses read one prompt per process before any reset, so all 38 comparisons could pass. The service gate
    (reset before every case) is the one that sees it.
  - Fix (engine/src, build r7 `b51c9e8d803e`): the ones are rewritten at every chunk. Built, **not device-gated**.
- B1's 12 suite prompts (60–90 tokens, read token by token either way) equal B19, so decode with the five flags set is
  unchanged (78.71 against 78.34 tok/s on one server each: no speed claim).
- Kernel log clean before, after ready, after the suite and after the halt. B1 stopped gracefully (Result=success);
  no engine process left; all card locks free.
- Raw server directories (638 files, 316,976,698 B, sha256-verified): `/mnt/raid-models/ownrt-experiment-archives/2026-10-29/prefill-speed-suite-20261029/`.

## Incidents (host-side only, no device faults)

1. Phase g1: `run_phase.sh` was edited (a new extra) while the phase was running it; bash stopped at the end of the arm
   loop with "unexpected EOF". All seven arms and their checks had completed ([logs/incident-g1-script-edit.txt](logs/incident-g1-script-edit.txt)).
   Later phases ran from frozen copies (`logs/run_phase-g*.sh`).
2. r3 (KV-only, first form) refused at its first chunk command: the derivation found `streams` live at row start
   because the merge stage's plan entries carry no I/O. Fixed in r4 (merge I/O from `direct()`).
3. r5 refused at its first chunk command: the `qsa_prepare` wiring check expected 4 inputs; the plan builder appends
   `active` and `error`. Fixed in r6.
4. Server B1: the service's startup gate failed (section 4). The server was stopped gracefully; the chain halted.

## Next

1. **Gate r7, then the A/B.** Smallest smoke, then add to the rank harness what the service gate does: two batched prompts
   in one process with a RESET between them (rank 0 and rank 1), compared bitwise with token by token. Then fresh
   servers A, B, B at 131,072: startup gate 13/13, TTFT and decode on the 121,854 / 512 request, outputs against the
   long512 reference, suite = B19. Projection about 249 s ([results/projection.json](results/projection.json)).
2. **After that rank 0 still sets the pace** (about 524 against 473 ms per chunk, projected). Remaining exact host-side
   pieces on rank 0, per chunk: the PLE/begin/commit/broadcast row replays (13 ms, both cards near idle), the lookup
   rows computed on the host with the cards idle (15.6 ms; compute them while the previous draft chunk runs), and the
   draft staging (6 ms, now overlapped per row).
3. **Draft rows at 0.23 ms:** a multi-row form of the 17 kept draft sites (merge, hc.a, k/v/ik, prepare, pool) would
   take most of the remaining 60 ms per chunk.

## Files

- Engine (lab builds r1–r7 from `engine/src`, receipts `da3962e387cf`, `84e1beeb2476`, `035fae939623`, `1203bfaa8fae`,
  `639ecc563bc6`, `300e6f8c46ad` (gated in the harness, failed the service gate), `b51c9e8d803e` (the ones fix, not device-gated)): `prefill_engine.hpp` (host trace, lookup batch, moe rows, xzero), `main.cpp`
  (per-card submission counter), `stage2/packet9-kopt4/kernels.{hpp,cpp}` (`epilogue_f32_rows`), `adapter.cpp` (moe rows
  admission), `prefill_wire.hpp` (op 29, draft tokens), `native_controller.hpp` (one draft command per chunk), `rank.hpp`
  (op 29 handler), `mtp.hpp` (`replay_chunk`, KV-only liveness, draft host trace).
- Lab: [run_phase.sh](run_phase.sh) (extras `ht lb mn xz dc ko`), [tp_rank0_driver.py](tp_rank0_driver.py)
  (`--draft-chunk`), [compare_phase.sh](compare_phase.sh) (absolute run paths), [analyze_host_trace.py](analyze_host_trace.py),
  [analyze_long_trace.py](analyze_long_trace.py), [summarize_harness.py](summarize_harness.py), [gates_summary.py](gates_summary.py),
  [keep_evidence.sh](keep_evidence.sh), [arm_env.py](arm_env.py) (arms `tptsxqcf`, `tptsxqck`), [lab/](lab/) (adapter passes
  the new keys; `adapter6_tp.py.vs-ctx131072.patch`), suite scripts.
- Evidence: [evidence/](evidence/) (m1, m2, g1, g3, g5 compact runs; g2/g4 refusals), [results/](results/), [logs/](logs/).
  Raw runs (sha256-verified): `/mnt/raid-models/ownrt-experiment-archives/2026-10-29/prefill-speed-runs-{m1,m2,g1,g2-s3-r0-ko,g3,g4-s5-r0-ko,g5}/`.
