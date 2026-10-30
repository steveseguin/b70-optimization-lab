# Four cards at 131,072 tokens of context, exact (2026-10-29)

**Question.** The four-card layout (two pipeline ranks, each split exactly across two cards; flags `tptsxqc`) decoded
SC117 at 78.29–78.62 tok/s at 65,536 tokens of context. The per-card plan already fit 131,072 (QSA split), but two
checks outside the kernels refused it. Can the four-card service run at 131,072 exactly, and how does it compare with
the 3-target + draft layout at 262K on the 121,854-token prompt?

**Answer.** Yes, exactly.
- **What capped it:** the engine's admitted-context list (131,072 only for pipeline/provider processes) and the one-card
  plan check that ran before the TP transform (rank 1 one card at 131,072: 34.14 GB, over the 32.21 GB cap). Plus, in
  the lab service, `chat.py`'s context list and the missing 131,072 state oracle.
- **What changed (engine `aafd258dd5ea`):** a `--tp-replicate` rank also admits 131,072, and its admission is the
  per-card TP plan (`write_tp_plan`, still 30 GiB per card). The one-card total is still written to `plan.json`. Every
  other cap and floor is unchanged, and a one-card rank is still refused at 131,072.
- **Per-card plan at 131,072:** rank 1 **31,421,793,604 B**, rank 0 **26,089,091,084 B** (+ draft on card 0), cap
  32,212,254,720. Measured card-0 census: rank 1 31,442,515,332 B (770 MB headroom), rank 0 29,774,565,098 B
  including the draft.
- **Gates (15 harness comparisons, all pass):** TP-131072 equals TP-65536 and one card at 65,536. Every buffer is
  bitwise equal, or (the context-sized KV, pooled-key and raw-key buffers) holds the 65,536 bytes followed by zeros.
  Tokens and draft tokens are equal, and batched equals token-by-token reading at 131,072.
- **Service at 131,072, two fresh servers:** the startup state equals the 4096 and 65,536 oracles. The second server
  reproduces the 131,072 oracle the first recorded. All 5,965 suite outputs equal B19.
  - Suite median **78.23 / 78.51 tok/s** (mean of medians 78.37). For comparison, 78.29–78.62 at 65,536.
- **121,854-token prompt / 512 outputs:** all 512 output ids equal the retained 3+1 262K long512 reference (default
  routing, `bf1f0867d1bd…`; the 2+1 128K screens gave the same ids).
  - **TTFT 355.8 / 355.1 s** against 250.7 s for the 3+1 262K layout (240.96–250.75 s across the cut screens).
  - **Decode 75.97 / 76.29 tok/s** (all 511 intervals) against 48.30 (44.99–48.52).
  - Request time 363.4 / 362.6 s against 261.3 s: the 3+1 layout reads long prompts faster; this layout writes 1.6×
    faster. With this TTFT gap, the four-card TP layout finishes sooner only once an answer is longer than about 14K tokens.
- **Persistent card-1 thread, re-tested at 65,536 (four fresh servers A/B/A/B):** 78.76 against 78.50 tok/s (1.0033×),
  faster on 47 of 48 prompt pairs, rank-1 p90 no longer worse. All outputs equal B19.
- Kernel log clean throughout. `sc117-lan` not touched. No incidents.

Binary `aafd258dd5ea…` (build r1, [receipt](../../../engine/receipts/aafd258dd5ea.json)), built from `engine/src` into
`/dev/shm/engine-build-ctx131072-20261029-r1`; engine commit `3b44b97e4` (`main.cpp`, `rank.hpp`). Previous binary
`5921bb96f630` (fault-ladder). F32, split 23, B19 flags, arm `tptsxqc`.

## 1. What capped the context, and what changed

| Where | Cap | Change |
|---|---|---|
| `main.cpp` `parse` (split 23 with the rank-0 draft) | 131,072 admitted only for `pipeline_enabled()` / `provider_only` | also for `tp_replicate` |
| `main.cpp` GSQ real-context check | same | also for `tp_replicate` |
| `main.cpp` `target_scratch_bytes` | bounded 8 MiB scratch at 131,072 only for pipeline stages (else 256 MiB legacy) | also for `tp_replicate` (same bound as 65,536) |
| `rank.hpp` `run_rank` → `write_plan` | one-card plan refused above 30 GiB **before** the TP transform (rank 1: 34.14 GB) | not refused for a TP rank (still written); `write_tp_plan` after the TP transform admits each card at 30 GiB |
| lab `chat.py` (copy) | contexts 4096/32768/65536 (262144 PP4 only) | 131,072 only with two TP cards on each rank |
| lab `service.py` (copy) | per-context F32 state oracle required; the lab never records one | at 131,072 also compared with the 65,536 oracle; the 131,072 oracle recorded once on explicit opt-in (`SC117_LAB_RECORD_ORACLE`) after the 4096 and 65,536 comparisons |

Unchanged: the runtime arena admission (30 GiB per card at every allocation), the adapter's census cap, MemAvailable,
root and `/dev/shm` floors, `rope-262144`, the kernels' 262,144 capacity limit, the 512-row raw ring and the draft prefix rows.
Split 24 and one-card ranks stay refused at 131,072.

## 2. CPU plan check ([evidence/probes/](evidence/probes/), `OWNRT_PLAN_ONLY=1`, arm `tptsxqc`)

| Rank | Context | One card (not admitted under TP) | TP, per card | Headroom to 32,212,254,720 |
|---|---:|---:|---:|---:|
| rank 1 | 65,536 | 32,199,218,796 | 30,423,549,252 | 1.79 GB |
| rank 1 | **131,072** | 34,136,987,244 | **31,421,793,604** | **790 MB** |
| rank 0 | 65,536 | 26,401,823,300 | 25,208,287,244 (+ draft) | — |
| rank 0 | **131,072** | 27,953,715,780 | **26,089,091,084** (+ draft) | — |

The 131,072 rank-1 figure equals the qsa-split projection to the byte. Measured card-0 census (256-row prefill): rank 1
31,442,515,332 B, rank 0 29,774,565,098 B including the draft (28,713,406,186 at 65,536).

## 3. Rank harness gates ([results/gates.json](results/gates.json), [logs/](logs/))

1,100 prompt rows (256-row chunks; the raw ring wraps twice) then 16 decode halves. Rank 1 on 23+47 (and on its service
cards 43+47), rank 0 on 23+27 (`hmcn`: hits, misses and cancels; `m`: all misses), one card on 23. Every position written
is below 65,536, so a 131,072 run must hold exactly the 65,536 state.
[xctx_compare.py](xctx_compare.py) treats a buffer as equal when it is bitwise equal, or when it is twice as long and its
first half hashes to the 65,536 buffer and the rest is zero. Fixed-size buffers, the 512-row ring included, must be bitwise
equal. The first device run of the new path was the smallest smoke (16 rows, 4 halves; `k1-smoke`).

| Comparison | Rank 1 | Rank 0 target / draft |
|---|---|---|
| smoke: TP-131072 vs TP-65536 | 1058 + 21 | 1009 + 20 / 67 + 4 |
| one card at 65,536, new binary vs `5921bb96f630` (bitwise) | 1079/1079 | 1029/1029, 71/71 |
| TP-65536 vs one card at 65,536 (bitwise) | 1079/1079 | 1029/1029, 71/71 |
| **TP-131072 vs one card at 65,536** | **1058 + 21** | **1009 + 20 / 67 + 4** (`hmcn` and `m`) |
| **TP-131072 vs TP-65536** | **1058 + 21** | **1009 + 20 / 67 + 4** |
| TP-131072 token by token vs one card at 65,536 / vs TP-131072 batched (bitwise) | 1058 + 21 / 1079/1079 | — |
| TP-131072 on 43+47 vs on 23+47 (bitwise) / vs one card at 65,536 | 1079/1079 / 1058 + 21 | — |

"+ N": prefix-and-zero buffers. Rank 1: the 7 QSA layers' keys, values and pooled keys. Rank 0: the 5 QSA layers' keys,
values, pooled and raw keys (rank 0 has no ring), and the draft's 4 QSA buffers. Nothing differs. Decode tokens and draft
tokens are equal; card 1 equals card 0 on every buffer both hold; 0 exchange timeouts.
Harness decode halves are a little slower at 131,072 with the same positions: rank 1 10.35 against 10.19 ms, rank 0
9.30 against 9.17 ms. Not investigated; the suite shows no matching loss.
Raw runs (sha256-verified): `/mnt/raid-models/ownrt-experiment-archives/2026-10-29/ctx131072-runs-{k1,k2}/` (208 and
583 files, 11.38 and 32.91 GB). The six lab servers' work directories: `…/2026-10-29/ctx131072-suite-20261029/` (1,893
files, 834 MB).

## 4. Lab service at 131,072: two fresh servers ([results/suite/summary.json](results/suite/summary.json))

Same procedure as fault-ladder section 5 ([suite.sh](suite.sh), [run_arm_suite.sh](run_arm_suite.sh)): lab service on
127.0.0.1:18171, one fresh transient unit per server (`Restart=no`, `KillMode=process`, no SIGKILL,
`LimitNOFILE=1048576`, nice 19, CPUs 0-3,16-19), all four card locks held by `sc117-tp-svc-ctx-locks-20261029`,
`NEOReadDebugKeys=1 EnableDeferBacking=0`, binary `aafd258dd5ea`, `SC117_CONTEXT=131072`.

**Startup gates, each server:**
- F32 self-tests equal the B19 record.
- The state after the self-test equals the 4096 oracle (`de4b2aa4…`, 20 + 28 buffers compared as prefix + zeros) and the
  65,536 oracle (`90244b48…`, split 24, 20 + 21), with 0 differences on both ranks.
- Server 1 then recorded `f32-state-oracle-ctx131072.json` ([evidence/](evidence/f32-state-oracle-ctx131072.json)), as
  the LAN service recorded its 65,536 one. Server 2 reproduced it exactly (0 differences).
- The batched-prefill gate passed 13/13 cases on each server.

| Server | Median tok/s | Mean | Range | Outputs | Ready after | TTFT, 3,490 tokens |
|---|---:|---:|---:|---|---:|---:|
| tptsxqc-r1-c131072 | **78.23** | 78.58 | 75.66–82.58 | = B19, all 12 | 1,084 s | 9,935 ms |
| tptsxqc-r2-c131072 | **78.51** | 78.76 | 75.95–82.89 | = B19, all 12 | 973 s | 9,933 ms |

- All 5,965 ids, hashes and per-prompt MTP guesses and hits equal B19. `cached_tokens=0`. The 3,490-token prompt's 64
  ids hash to `29426ae7332a…`, as at 65,536.
- At 65,536 the same flags gave 78.62 / 78.29 (fault-ladder, binary 5921bb96f630). Same-session 65,536 servers are in
  section 6.

## 5. The 121,854-token / 512-output request ([long_probe.py](long_probe.py))

The retained HTTP body `pp4-review-2026-10-28/inputs/long-body.json.gz` with `max_tokens` 512. Tokenized by the lab
`chat.py`, it equals the long512 screens' `prompt.i32` token for token ([copy](evidence/long512-prompt.i32), 121,854 ids).
Sent once per server, after the suite, cold.

| | TP2×PP2 at 131,072, server 1 | server 2 | 3+1 at 262K, AOT screen (same ids) | 3+1 cut screens (reference-route tie sort) |
|---|---:|---:|---:|---:|
| TTFT (s) | **355.79** | **355.10** | 250.74 | 240.96 / 250.75 |
| decode, all 511 intervals (tok/s) | **75.97** | **76.29** | 48.30 | 44.99 / 46.53 |
| request (s) | 363.37 | 362.65 | 261.33 | 252.33 / 261.74 |
| MTP hits / guesses | 418 / 511 | 418 / 511 | — | — |
| output ids | **= `bf1f0867d1bd…` (all 512)** | **= (all 512)** | `bf1f0867d1bd…` | `ee09ec505382…` |

- **Outputs:** both servers equal the 3+1 262K AOT screen's 512 ids (default routing), which the 2+1 128K long512
  screens also produced. The cut16/equal16 screens ran the opt-in reference-route tie sort, which differs from both from
  output 22 on. That is a different routing tie policy, not a mismatch of this layout.
- **TTFT** is about 105 s (42%) longer than on 3+1, and about the same as the 2+1 128K layout (358.6 s). Decode at
  121,854 positions: rank-1 half 11.20 ms, rank-0 speculative half 9.96 ms (about 10.4 / 9.2 at 3.5K).
- Prompt reading runs at 342 tokens/s, with the two ranks' chunks overlapping (read one after the other they would take
  about twice as long). On 1,100 harness rows the ranks take about the same time: rank 1 3.49 s, rank 0 3.23 s (2.29 s
  prefill + 0.94 s draft replay). So both stages must get faster to cut TTFT. Each TP rank still issues both cards'
  prefill from one host thread (decode uses one thread per card).

## 6. Side step: the persistent card-1 thread, re-tested on the per-card-context path (65,536)

`OWNRT_TP_PERSISTENT_THREAD=1` was neutral (0.998×) and had a worse rank-1 p90 before the fault-ladder fix
([persistent-thread](../persistent-thread-2026-10-29/RESULT.md)). Re-tested with four fresh servers in this order:
tptsxqc-r1, tptsxqcp-r1, tptsxqc-r2, tptsxqcp-r2. Same chain, same binary `aafd258dd5ea`, 65,536. `tptsxqcp` is
`tptsxqc` plus the flag ([arm_env.py](arm_env.py)).

| Server | Median tok/s | Mean | Range | Outputs | Ready after | TTFT, 3,490 tokens |
|---|---:|---:|---:|---|---:|---:|
| tptsxqc-r1-c65536 | 78.47 | 78.87 | 76.04–82.85 | = B19, all 12 | 667 s | 9,830 ms |
| **tptsxqcp-r1-c65536** | **78.76** | 79.01 | 76.19–82.99 | = B19, all 12 | 612 s | 9,821 ms |
| tptsxqc-r2-c65536 | 78.53 | 78.76 | 75.97–82.86 | = B19, all 12 | 637 s | 9,822 ms |
| **tptsxqcp-r2-c65536** | **78.76** | 78.99 | 76.10–83.08 | = B19, all 12 | 683 s | 9,824 ms |

- **Pair means: 78.50 against 78.76 tok/s, 1.0033×.** The flag is faster on 11, 12, 12 and 12 of the 12 prompts in the
  four cross-pairs (per-prompt median 1.0012–1.0030, range 0.998–1.007).
- **Tails** ([results/suite/tails.json](results/suite/tails.json), every decode half of the 13 client requests): rank 1
  median 10.231 / 10.242 against 10.270 / 10.275 ms. Rank 1's p90 is no longer worse: 10.404 / 10.415 against
  10.433 / 10.452 ms. Rank 0 median −0.017 ms. No half above twice the median, and none above 200 faults.
- So with the libsycl cache defect gone, the persistent thread is a small, steady win: +0.3%.
  - Its outputs, startup state oracles and prefill gates all pass.
  - Its bitwise rank-harness gates ran without `OWNRT_TP_CARD_CONTEXT`. The combination has not had its own harness gate.
- At 131,072 the two `tptsxqc` servers measured 78.23 / 78.51 against 78.47 / 78.53 here: no measurable cost of the
  larger context on the suite.

## Next

1. **Prompt reading at long context** is where the 3+1 layout still wins (TTFT 355 against 251 s on 121,854 tokens).
   - Both TP ranks read a chunk in about the same time, so both need to get faster.
   - Per-card submission threads for TP prefill (decode has them; prefill issues both cards from one host thread).
   - Then per-chunk rank busy times on the long request, to see how much pipeline bubble is left between the ranks.
2. **Persistent thread:** gate `OWNRT_TP_PERSISTENT_THREAD=1` together with `OWNRT_TP_CARD_CONTEXT=1` in the rank harness
   (rank 1 batched and token by token; rank 0 `hmcn`/`x`/`m`), then move the four-card flag set to `tptsxqcp` (+0.3%).
3. **262,144 on four cards does not fit rank 1.** Its per-card plan grows 998 MB per 65,536 positions, to about 33.4 GB
   at 262,144 (cap 32.21 GB). Rank 0 fits (27.85 GB per card). It needs more of rank 1's per-card state split, or a
   lighter rank-1 layer share.
4. **Service switch** (owner's call, unchanged): 131,072 now runs on the four-card lab service. Sessions, checkpoints
   and continuation are still refused under TP.

## Files

- Engine (commit `3b44b97e4`): `gsq-rco-iq3s/dense-packed-block/engine/build/source/main.cpp`,
  `gsq-rco-iq3s/state-bundle/build/source-v4/rank.hpp`; receipt [aafd258dd5ea](../../../engine/receipts/aafd258dd5ea.json).
- Lab: [lab/](lab/) (service copy with the 65,536 bridge and the one-time 131,072 oracle; `chat.py` copy; adapter),
  [arm_env.py](arm_env.py) (`ARM_CONTEXT`, arm `tptsxqcp`), [run_phase.sh](run_phase.sh) (`ctx=`),
  [compare_phase.sh](compare_phase.sh) and [xctx_compare.py](xctx_compare.py), [plan_probe.py](plan_probe.py),
  [make_launch.py](make_launch.py), launch JSONs, [suite.sh](suite.sh), [run_arm_suite.sh](run_arm_suite.sh),
  [long_probe.py](long_probe.py), [suite_compare.py](suite_compare.py).
- Evidence: [evidence/](evidence/) (probes, compact harness evidence `k1/`, `k2/`, the 131,072 oracle, the long512
  prompt), [results/](results/) (`gates.json`, `suite/`), [logs/](logs/).
