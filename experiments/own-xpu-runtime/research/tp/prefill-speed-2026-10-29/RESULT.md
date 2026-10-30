# Four-card prompt reading at 131,072: 354 → 250.5 s to the first token, exact (2026-10-29/30)

**Question.** On the four-card layout (two pipeline ranks, each split exactly across two cards; flags `tptsxqc`, binary
`aafd258dd5ea`) a 121,854-token prompt took 355 s to its first token, against 241–251 s on the 3 targets + 1 draft 262K
layout. Where does the time go, and can exact changes close the gap?

**Answer.** The four-card layout now reads the 121,854-token prompt in **250.5 / 250.8 s** (two fresh servers) against
**353.6 s** for the current flags on the same binary, and 241–251 s on the 3+1 262K layout (250.7 s AOT screen; 241.0 s
with the cut-16 screen). Decode after it is unchanged (76.3 tok/s), and all 512 outputs equal the 3+1 reference.
- **Bottleneck, measured:** rank 0 was the critical path. Per 256-row chunk it spent 518 ms on its prefill and 229 ms
  replaying the MTP draft row by row (256 commands of 0.89 ms): 747 ms × 476 chunks = 355 s. Rank 1 needed 515 ms per chunk
  and waited about 230 ms. The ranks were already pipelined one chunk apart.
- **Inside a chunk:** the TP prefill is mostly device-bound. Its one large host-paced piece was `moe_combine`, replayed row
  by row (78–86 ms per chunk). The draft rows are device-bound (0.79 ms each even with no host waits): each prompt row
  computed a full layer whose outputs nothing reads.
- **Built (opt-in, engine r7 `b51c9e8d803e`):** a multi-row `moe_combine` for prefill, once-per-chunk exchange zeroing,
  batched lookup uploads, one draft command per chunk, and KV-only draft prompt rows (17 of 46 sites).
- **Long request, measured:** rank 0 466.5 ms prefill + 60.3 ms draft per chunk (526 ms, was 747); rank 1 468 ms
  (idle 27.5 s, was 110 s).
- **Gates:**
  - Build r6 passed 38 rank-harness comparisons but failed the service's startup gate: a request reset zeroed the native
    `moe_combine`'s ones buffer. The harness never read a prompt after a reset.
  - A new two-request harness case (prompt → decode → reset → prompt → decode, with the allocation inventory and a ones
    check) fails on r6 and passes on r7.
  - On r7, the 38 comparisons rerun all equal. All three new servers passed the startup gate 13/13. Every suite output
    equals B19.

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

## 3b. The reset seam, closed on build r7 `b51c9e8d803e` (2026-10-30)

**A harness case that sees the bug.** Both drivers gained `--second-prompt N` (`run_phase.sh` extra `sp=N`): request A
(1,100 rows batched, 16 decode halves) → RESET (op 11, each reset dumps the request's state, its draft state and the
reset-time allocation inventory before zeroing) → the shared region zeroed as the lab adapter does → request B (600 rows
with other token ids and rows, 16 decode halves) → RESET. The compare checks request B like request A, plus:
- the allocation inventory of both requests (`request-state-inventory.json`, every standalone non-weight allocation the
  new paths touch: all prefill shadows, positions, tokens, slot rows, `ordered-mixture`, operator scratch): equal to flags
  off on every common allocation except the exchange control words (`*:tp-exchange-control`, wait/poll statistics);
- the ones invariant: every `prefill:moe-ones` holds only 1.0f at every reset ([inventory_check.py](inventory_check.py)).

| Comparison (two requests) | Rank 1 | Rank 0 target / draft | Inventory | Ones |
|---|---|---|---|---|
| **r6 `300e6f8c46ad` flags on vs flags off (must fail)** | A 1079/1079; **B 938 of 1079 differ, tokens differ** | A 1029/1029, 71/71; **B 888 of 1029 differ** | **B: 36 / 161 allocations differ** | **zero at the second reset, both cards** |
| r6 flags off vs r7 flags off (the reference itself) | A, B 1079/1079 | A, B 1029/1029, 71/71 | equal | — |
| r7 smoke (40 + 40 rows, 16-row chunks) on vs off | A, B 1079/1079 | A, B 1029/1029, 71/71, tokens equal | equal (57 / 282) | 1.0f at both resets |
| **r7 on vs off** | **A, B 1079/1079, tokens equal** | **A, B 1029/1029, 71/71, tokens equal** | **equal (57 / 282)** | **1.0f at both resets** |
| r7 on vs one card at 65,536 (prefix + zeros) | A, B 1058 + 21 | A, B 1009 + 20 / 67 + 4 | — | — |
| r7 off vs one card at 65,536 | A, B 1058 + 21 | A, B 1009 + 20 / 67 + 4 | — | — |

So the new case fails on r6 exactly where the service gate failed (the request after a reset) and passes on r7.

**The 38 comparisons of section 3, rerun on r7** ([rerun38.py](rerun38.py); runs `p1`, `p2`): every new-binary run
replaced by the r7 run with the same flags (6 smokes, 3 rank-1 and 7 rank-0 runs at 1,100 rows), the archived
`aafd258dd5ea` and one-card runs as references: **38/38 equal**. [results/gates.json](results/gates.json) now holds 84
comparisons, all equal, plus the 4 rows of the r6 expect-fail phase (2 differ as required, 2 reference rows equal).
0 exchange timeouts or aborts; kernel log clean before and after every arm.

## 4. Service at 131,072, fresh servers

Lab services on 127.0.0.1:18171 ([suite.sh](suite.sh), [run_arm_suite.sh](run_arm_suite.sh): one fresh transient unit per
server, `Restart=no`, `KillMode=process`, no SIGKILL, `LimitNOFILE=1048576`, nice 19, CPUs 0-3,16-19; all four card locks held
by `sc117-tp-svc-pfs-locks-20261029`; `NEOReadDebugKeys=1 EnableDeferBacking=0`). From the r7 chain on, a server is timed
only after its startup batched-prefill gate passed 13/13 with batched reading on. Order A, B, B, each once, no retries
([results/suite/summary.json](results/suite/summary.json)):

| Server | Binary | Startup gate | Suite median (mean) tok/s | Suite outputs | TTFT, 3,490 tokens | **121,854 / 512: TTFT** | decode after it | request | outputs vs 3+1 262K |
|---|---|---|---:|---|---:|---:|---:|---:|---|
| A `tptsxqc-r1` (current flags) | r6 | 13/13 | 78.34 (78.70) | = B19, all 12 | 9.94 s | 356.6 s | 75.95 tok/s | 364.1 s | all 512 equal |
| B `tptsxqck-r1` (fix) | r6 | **FAILED, 6 of 9 batched cases** | 78.71 (78.95) | = B19 | 35.6 s (token by token) | not run | — | — | — |
| **A `tptsxqc-r2`** (current flags) | **r7** | 13/13 | 78.46 (78.71) | = B19, all 12 | 9.91 s | **353.6 s** | 76.36 tok/s | 361.2 s | all 512 equal |
| **B `tptsxqck-r2`** (fix) | **r7** | **13/13** | 78.56 (78.90) | = B19, all 12 | **7.36 s** | **250.5 s** | 76.28 tok/s | **257.5 s** | **all 512 equal** |
| **B `tptsxqck-r3`** (fix) | **r7** | **13/13** | 78.72 (78.97) | = B19, all 12 | **7.35 s** | **250.8 s** | 76.26 tok/s | **257.8 s** | **all 512 equal** |
| 3+1 at 262K (retained screens) | — | — | — | — | — | 250.7 s (AOT); 241.0 / 250.8 s (cut screens) | 48.3 tok/s (45.0 / 46.5) | 261.3 s | reference |

- **TTFT 353.6 → 250.5 / 250.8 s (−29%, 1.41×)**, with the same 512 output ids (`bf1f0867d1bd…`), MTP 418/511 hits and
  `cached_tokens=0` on every server. The 3,490-token prompt: 9.91 → 7.36 s.
- The 512-token request now finishes in 257.5 / 257.8 s against 261.3 s on the 3+1 AOT screen (TTFT 250.7 s). The 3+1
  cut-16 screen still reads 3.9% faster (TTFT 241.0 s), but it decodes at 45.0 tok/s against 76.3. Counting first-token
  time plus answer length over decode rate, the four-card layout finishes first for any answer length against the AOT
  screen, and for answers longer than about 1,060 tokens against the cut-16 screen.
- **Timeline of the long request** ([analyze_long_trace.py](analyze_long_trace.py); results/long-trace-*.json):

| Per chunk (476) | A r7 (current) | B r7 (fix), server 1 / 2 |
|---|---:|---:|
| rank 0 prefill busy | 514 ms (244.8 s) | 465 / 466 ms (221.3 / 221.6 s) |
| rank 0 draft replay | 228 ms (108.5 s, 122,207 commands) | 61 ms (29.2 s, one command per chunk) |
| rank 0 critical path | 742 ms | 526 / 527 ms |
| rank 1 busy / idle | 515 ms / 107.8 s | 467 / 468 ms; idle 27.5 / 27.6 s |

  The projection made before the r7 servers (523.6 ms per chunk, 249 s; [results/projection.json](results/projection.json))
  was within 0.5%.
- Decode is unchanged: suite medians 78.46 (A) against 78.56 / 78.72 (B), one A and two B servers; the flags touch only
  prompt reading. All 5,965 suite ids, hashes and MTP guesses/hits equal B19 on every server.
- B `tptsxqck-r1` (r6) is the failed gate of 2026-10-29 ([logs/incident-b1-prefill-gate.txt](logs/incident-b1-prefill-gate.txt)):
  its reset zeroed the native `moe_combine` ones, as section 3b reproduces in the harness.
- Kernel log clean before, after ready, before the long request, after the suite and after every server. No engine process
  left; all card locks free. Raw server directories (sha256-verified):
  `/mnt/raid-models/ownrt-experiment-archives/2026-10-29/prefill-speed-suite-20261029/` (r6 servers) and
  `…/prefill-speed-suite-20261030/` (r7 servers).

## Incidents (host-side only, no device faults)

1. Phase g1: `run_phase.sh` was edited (a new extra) while the phase was running it; bash stopped at the end of the arm
   loop with "unexpected EOF". All seven arms and their checks had completed ([logs/incident-g1-script-edit.txt](logs/incident-g1-script-edit.txt)).
   Later phases ran from frozen copies (`logs/run_phase-g*.sh`).
2. r3 (KV-only, first form) refused at its first chunk command: the derivation found `streams` live at row start
   because the merge stage's plan entries carry no I/O. Fixed in r4 (merge I/O from `direct()`).
3. r5 refused at its first chunk command: the `qsa_prepare` wiring check expected 4 inputs; the plan builder appends
   `active` and `error`. Fixed in r6.
4. Server B1: the service's startup gate failed (section 4). The server was stopped gracefully; the chain halted.
5. Phase t2 stopped itself before its third arm on the MemAvailable floor (61.8 < 64 GB): the t1 archive was still
   hashing with its 28 GB in /dev/shm. No device effect; the remaining arms ran as t2b after the archive. Later archives
   ran in their own transient units and completed before the next phase.

## Next

1. **Service flags (owner's call; `sc117-lan` not touched):** add the five flags to the four-card set (arm `tptsxqck`,
   engine `b51c9e8d803e` or later). They change prompt reading only.
2. **Rank 0 and rank 1 are now nearly balanced** (526 against 468 ms per chunk). On rank 0, about 35 ms per chunk can go
   without kernel work:
   - the PLE/begin/commit/broadcast row replays (13 ms, both cards near idle);
   - the lookup rows computed on the host with the cards idle (15.6 ms; compute them while the draft chunk runs);
   - the draft staging (6 ms).
   That would bring rank 0 to rank 1, about 223 s.
3. **Both ranks together:** the prefill is device-bound at about 466 ms per chunk on each pair of cards. The next lever is
   inside the kernels: replicated work (HC, shared expert, router about 26% of a layer, done on both cards), and the
   exchange count (69 / 75 pairs per chunk).
4. **Harness coverage:** keep the two-request case (`sp=N`) in every prefill gate. The 38 one-request comparisons could
   not see a buffer that a reset zeroes.

## Files

- Engine (lab builds r1–r7 from `engine/src`, receipts `da3962e387cf`, `84e1beeb2476`, `035fae939623`, `1203bfaa8fae`,
  `639ecc563bc6`, `300e6f8c46ad` (gated in the harness, failed the service gate), **`b51c9e8d803e`** (r7: the ones
  rewritten every chunk; all gates and the service A/B/B)): `prefill_engine.hpp` (host trace, lookup batch, moe rows, xzero), `main.cpp`
  (per-card submission counter), `stage2/packet9-kopt4/kernels.{hpp,cpp}` (`epilogue_f32_rows`), `adapter.cpp` (moe rows
  admission), `prefill_wire.hpp` (op 29, draft tokens), `native_controller.hpp` (one draft command per chunk), `rank.hpp`
  (op 29 handler), `mtp.hpp` (`replay_chunk`, KV-only liveness, draft host trace).
- Lab: [run_phase.sh](run_phase.sh) (extras `ht lb mn xz dc ko sp=N`), [tp_rank0_driver.py](tp_rank0_driver.py)
  (`--draft-chunk`, `--second-prompt`), [tp_rank1_driver.py](tp_rank1_driver.py) (`--second-prompt`), [inventory_check.py](inventory_check.py),
  [rerun38.py](rerun38.py), [xctx_compare.py](xctx_compare.py) (request B), [compare_phase.sh](compare_phase.sh) (absolute run paths), [analyze_host_trace.py](analyze_host_trace.py),
  [analyze_long_trace.py](analyze_long_trace.py), [summarize_harness.py](summarize_harness.py), [gates_summary.py](gates_summary.py),
  [keep_evidence.sh](keep_evidence.sh), [arm_env.py](arm_env.py) (arms `tptsxqcf`, `tptsxqck`), [lab/](lab/) (adapter passes
  the new keys; `adapter6_tp.py.vs-ctx131072.patch`), suite scripts.
- Evidence: [evidence/](evidence/) (m1, m2, g1, g3, g5, t1–t3, p1, p2 compact runs; g2/g4 refusals), [results/](results/), [logs/](logs/).
  Raw runs (sha256-verified): `/mnt/raid-models/ownrt-experiment-archives/2026-10-29/prefill-speed-runs-{m1,m2,g1,g2-s3-r0-ko,g3,g4-s5-r0-ko,g5,t1,t2,t3,p1,p2}/`.
