# Laguna S 2.1 on 4x Intel B70 — Optimization Roadmap

> **Closed historical roadmap.** The published benchmark convention reported
> `102.971435596 tok/s` on 2026-07-26; a later audit recomputed the conventional
> 99-interval rate as `101.941721240 tok/s`. This file preserves the campaign's
> chronological plan and should not be read as current work. Start from
> [RESUME.md](RESUME.md), the
> [qualified result packet](../../results/laguna-s-2.1-int4-b70/README.md),
> [standalone reproducibility packet](../../repro/laguna-s-2.1-int4-b70-102tps-20260726/README.md),
> [final record](notes/2026-07-26-width12-dflash-fp8-w8a16-record.md), the
> [accounting correction](notes/2026-07-26-throughput-window-accounting-correction.md),
> [campaign transfer ledger](notes/2026-07-26-campaign-transfer-ledger.md), and
> the [KV-cache precision decision](notes/2026-07-26-kv-cache-precision-decision.md).
> Any “current rung” wording below is historical.

Objective: **maximize exact, honest single-session decode tok/s** for poolside
Laguna S 2.1 (INT4) on four Intel Arc Pro B70s, as an ongoing multi-week grind.
Also serve it as the working coding model.

## Non-negotiable standard (see memory: laguna-optimization-standard)
- **Exact target verification** on every promoted result (DFlash output ==
  target greedy, bitwise). Never sacrifice quality.
- **No cheating**: one active generation; fresh cold prompts; `cached_tokens=0`;
  no prefix cache / history / n-gram / warmed continuation; no benchmark routing;
  full run identity (commits, flags, kernel SHAs, topology).
- Grind the full ladder; kill a lever only with a measurement; no premature
  "best we can do." Submit verified localmaxxing records when a real matching
  record is beaten (surface payload for user OK first).

## Model facts
- 117.6B total / ~8.5B active MoE; 48 layers; hidden 3072; 256 experts / top-10
  sigmoid + 1 shared; GQA 48Q/8KV head_dim 128; 12 full + 36 sliding(512) layers;
  vocab 100352; GPT-2 BPE. INT4 = group-32 W4A16 on experts+most MLP, BF16 on
  attention/layer-0-MLP/lm_head, offline Hadamard rotations. FP8 KV scheme.
- Matched draft: `Laguna-S-2.1-DFlash-INT4` (BF16 draft is INCOMPATIBLE — 0% accept).
- Measured B70 bandwidth 579 GB/s/card. Roofline ~420-515 tok/s nonspec (8B active INT4).

## Progress ledger
| Date | Result | tok/s | Exact? | Notes |
|---|---|---:|---|---|
| 2026-07-21 | first TP4+EP4 INT4 load | — | — | loads, fits ~27.5 GiB/card |
| 2026-07-22 | target-only eager | 13.8 | yes | |
| 2026-07-22 | target-only PIECEWISE | 19.4 | yes | +41% graph |
| 2026-07-22 | DFlash m7 (matched INT4 draft) | 48.98 | **NO** | 48.8% accept; INEXACT (M=8 GEMM/chunk-prefill/nondeterministic-reduce vs q=1) — diagnostic only |
| 2026-07-22 | exact target-only q=1 (deterministic) | 12.56 | YES | valid exact nonspec baseline |
| 2026-07-22 | exact DFlash (serialized M=1 verify) | 7.45 | YES | 7/7 token-match; serialization slow |
| 2026-07-22 | **exact batched DFlash — RECORD cmrw7cn1k** | **33.09** | YES | approved; full-512, 13/13 x2 fresh starts, cross-req+rollover exact; async-sched race fixed |
| 2026-07-22 | batched-exact DFlash partial gate | 37.59 | partial only | obsolete 7-prompt/128-era diagnostic; not valid under the full-512 contract |
| 2026-07-22 | direct-M8 remote-route zeroing | 32.59 | YES | 13/13 full-512; 95 fill launches/cycle removed, but 1.496% slower |
| 2026-07-22 | deterministic PIECEWISE graph | 17.52 | **NO** | 1/13 vs teacher; AOT cache selected non-fixed artifact on restart; reverted |
| 2026-07-22 | deterministic exact graph (root-caused) | 30.99 | (chain incomplete) | **RULED OUT** -6.33% vs record. Inductor reassociates a CHAIN of BF16 boundaries (QKnorm/softplus/o_proj/post-attn-rms); each pin fragments graph. Kept: qkv shape-guard fix + AOT cache-identity hardening (laguna-exact-aot-v2 refuses stale artifacts). Eager stays record path. |

| 2026-07-22 | fused M8 expert transaction (W1+SiLU+W2) | 33.01 | YES (13/13 x2) | exact but NOT a record: lower start 33.008 < 33.086, 2.7% start variance. W2 expert-slot serialization lost route-parallel occupancy despite 6→2 launches. Default-off. Next: route-parallel W2 + occupancy. |
| 2026-07-22 | **fused W1+SiLU + route-parallel W2 — RECORD cmrwlyxez** | **33.27** | YES (13/13 x2) | +0.55% over prior; lower start 33.268 > 33.086; spread 0.108%; route-parallel W2 restored occupancy the full-fusion lost. APPROVED. |
| 2026-07-22 | **M8 route-interleave GEMM occupancy — RECORD cmrwot894** | **33.44** | YES (13/13 x2) | +0.51%; lower start 33.439>33.268; W1/W2 N-tile interleave raised EU active ~44->48%; 64/64 exact. APPROVED. |
| 2026-07-22 | DFlash depth sweep {4-10} | 33.44 (d7 best) | d7 exact | NO RECORD: d7 optimal. Exact only d5-7 (d4=12/13, d8-10=0/13: exact M=8 verifier caps draft depth at 7). Deeper barely helps (emitted/cyc 3.70->3.84 as accept collapses). Profile: biggest unopt kernel = BF16 attn QKV+O 2.92ms/cyc. |
| 2026-07-22 | BF16 attn QKV+O occupancy (N-interleave) | 33.44 | YES (exact both starts) | NEGATIVE: slowed 3/4 projections. Attn projections are SMALL GEMMs (EU ~10-11%, GQA-tiny K/V) — interleave technique doesn't transfer from large experts. Default-off. Next: attn non-GEMM FUSION (1.42ms). |
| 2026-07-23 | attn QKNorm+RoPE fusion | 33.19 lower | YES (13/13 x2) | STANDALONE ENDPOINT NEGATIVE: lower start 33.191 <33.439 with a wide 3.1% spread, despite an exact 144→48 launch component win. Retained default-off and later retested only inside a preregistered stack crossover. |
| 2026-07-22 | DFlash depth 4-10 sweep | 32.19 best exact | YES at depth 5/6/7 | depth 7 remains best exact but below record; depth 4 was 12/13; depths 8-10 exceeded exact M<=8 target guards, were 0/13, and fell to 4.94-6.11 tok/s. No two-start gate or payload. |
| 2026-07-23 | BF16 router/top-k specialization | 32.31 candidate | YES (13/13 phase 1) | COMPONENT WIN / ENDPOINT LOSS: removed 0.45-0.48 ms/cycle in isolation and won 10/13 paired rows, but the frozen candidate headline was -1.9985% versus its adjacent control. Preregistered early stop; no B2/A2 or payload. Do not stack without a new isolating design. |
| 2026-07-23 | shared-elementwise component bundle | component only | YES, exhaustive 4-card gate | Two native operations preserve literal BF16 rounding, remove 94 launches/cycle, and save 0.699-0.723 ms/cycle on every card. Promoted only as part of the following frozen stack endpoint. |
| 2026-07-23 | **shared-elementwise + QKNorm/RoPE stack — RECORD cmrx6p5dv** | **33.895** | **YES (52/52 ABBA)** | APPROVED. Conservative candidate 33.895 (support 34.551) beat adjacent controls 32.827/33.273, won 12/13 and 13/13 rows, and saved 3.490/4.015 ms target-cycle time. All requests cache-zero; long-next 8/8 and rollover 4/4. +1.364% over cmrwot894. |
| 2026-07-23 | routed-W1 N128 campaign | — | — | Long multi-abort campaign (peer loader, sycl-ls, UMF, XCCL log framing, NTFS3 post-reboot, device-lost incident). Recovery gate passed; no endpoint record. |
| 2026-07-23 | shared gate/up/down native M8 MM | — | mixed | Component lane; counter failure and threshold miss. Not promoted. |
| 2026-07-24 | **Breakable M8 PIECEWISE graph — RECORD cmrzjb7i9** | **92.164** | **YES (52/52 ABBA)** | **STEP CHANGE, +171.9%.** Conservative lower graph start 92.164 (support 92.761) vs eager controls 34.491/34.591. Won 13/13 and 12/13 rows; saved 55.049/54.220 ms per target cycle; acceptance drift <0.000308. Each start captured/replayed exactly once on all four ranks, audited 146/145 topology. Supersedes the earlier "graph RULED OUT" finding, which applied only to the non-breakable deterministic variant. |
| 2026-07-24 | M8 actual-offline raw parity | — | — | Ten preregistration revisions and a long abort chain (driver-config serialization, eager contract, hybrid slot schema, ZMQ path, runtime capture monitor, target-hidden evidence, segmented eager label order). Live-capture materialization eventually passed. Tooling lane, no endpoint. |
| 2026-07-25 | **persistent exact-attention metadata — RECORD cmrzrd4tf** | **94.920** | **YES (52/52 ABBA)** | APPROVED, current record. Conservative lower candidate 94.920 (support 95.067) vs metadata-off controls 92.550/92.878. Won 13/13 rows in both adjacent pairs, +2.561%/+2.356% headline, saved 0.911/1.648 ms per aggregate target cycle. Cross-leg exactness 39/39, long-next 8/8, rollover 4/4, all cache-zero. p10 65.964; full-512 wall 50.165. |
| 2026-07-25 | routed-W1 N32 component | — | YES (exact) | **TERMINAL COMPONENT NEGATIVE.** Bitwise exact and won 31/31 paired timing blocks, but the paired median saving was 0.028110 ms against a required floor of 0.20 ms per 47-layer cycle. Too small to justify a noisy endpoint campaign. Closes lever 5. |
| 2026-07-25 | DFlash context-KV workspace | — | **component PASS** | **IN FLIGHT.** Exact four-card component gate passed and promoted; sealed offline audit corrected the projected-V view-offset rule. TP4 runtime integration gate has consumed 4 one-shot packets, all failing closed in the harness before any token was generated. Fifth packet prepared, awaiting adversarial review. |

## Lever ladder (grind order; each exact + quality-gated)
1. **[DONE] DFlash verifier exactness and batching** — q=8 verifier == q=1
   target greedy, with one paged-decode pass, batched M=1 numerical lanes,
   fixed-rank sums, and deterministic direct MoE.
2. **[DONE; APPROVED] First verified record** — full-512 exact DFlash at
   33.085825 tok/s, LocalMaxxing `cmrw7cn1k006jnz01gq2z981v`.
3. **[DONE; APPROVED] MoE/EP launch/occupancy rebalance** — fused W1+SiLU,
   route-parallel W2, and M8 N-tile/route interleave produced the approved
   33.438927 tok/s predecessor, LocalMaxxing `cmrwot89400gqnz014oodtlbp`.
4. **[DONE; APPROVED] Exact launch-reduction stack** — literal-BF16
   shared-elementwise operations plus Q/K RMSNorm and RoPE reduce launches
   while retaining every rounding boundary. The preregistered A-B-B-A endpoint
   promoted the lower 33.894985 tok/s candidate, LocalMaxxing
   `cmrx6p5dv001bo4017hb7sixz`.
5. **[CLOSED; TERMINAL NEGATIVE] Shared-expert and routed-W1 occupancy** — the
   N32 policy is bitwise exact and won 31/31 paired timing blocks, but its
   paired median saving of 0.028110 ms per 47-layer cycle missed the 0.20 ms
   floor by an order of magnitude. Shared gate/up/down native M8 MM also closed
   on a counter failure and threshold miss. Do not reopen without a new
   isolating design.
6. **[DONE] INT4 expert GEMM efficiency / occupancy** — N64 route-interleaved
   W1/W2 workgroups raised EU activity and produced the current record.
7. **[DONE; APPROVED — THE BIG WIN] Graph coverage** — the *Breakable* M8
   PIECEWISE graph works where the deterministic non-breakable variant did not.
   It produced `92.164` tok/s on 2026-07-24 (LocalMaxxing `cmrzjb7i906x4o401egrnm05m`),
   a +171.9% step change over the 33.895 eager stack, saving ~55 ms per target
   cycle with acceptance drift below 0.000308 and exactly one capture/replay
   per rank on the audited 146/145 topology. Persistent exact-attention
   metadata then took it to the current `94.920` record. The earlier
   "RULED OUT" entry in the ledger above refers only to the non-breakable
   deterministic graph at 30.99 tok/s and is superseded.
8. **[DEPTH SWEEP DONE] Better speculation** — depth 7 remains best exact.
   Depths >7 require widening or serializing all M>8 target verifier boundaries
   before acceptance policy or tree/multi-branch drafting can be promoted.
9. **FP8 KV for long context** — capacity (2x tokens/card) for real coding sessions;
   measure speed tradeoff (BF16 slightly faster at 8K).
10. **Quantization headroom (careful, quality-gated)** — if quality holds, reduce
   remaining BF16 bytes/token to raise the roofline itself. Only behind a real
   quality gate; never a silent lossy swap.
11. **[CURRENT RUNG] DFlash context-KV workspace** — the draft's six-layer
   context-KV precompute allocates fresh intermediate tensors every proposal
   cycle. Distinct from the record, which touches only target q2-q8 attention
   metadata. Exact four-card component gate has **passed**; the TP4 runtime
   integration exactness gate is the blocker. See `RESUME.md`.

## Reusable assets
- vLLM branch `experiment/laguna-s-2.1-xpu-bringup-20260721`; XPU kernels
  `experiment/laguna-s-2.1-fwht-20260721` (attention tuples compiled, H128 FWHT).
- Weights on **local NVMe**: `/mnt/fast-ai/llm-models/laguna-s-2.1/{int4,dflash-int4}`
  (68 G target + 2.1 G draft). Migrated off the USB drive on 2026-07-23; the
  external copy is backup only. See `notes/2026-07-23-laguna-usb-backup-only-nvme-migration.md`.
- Gates/tools under `experiments/laguna-s-2.1-xpu-b70/tools/`.
- Bring-up + result notes under `notes/` (dated).
