# Laguna S 2.1 on 4x Intel B70 — Optimization Roadmap

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
| 2026-07-23 | attn QKNorm+RoPE fusion | 33.19 lower | YES (13/13 x2) | NEGATIVE: lower start 33.191 <33.439, WIDE 3.1% spread. PATTERN: fusions add variance & miss; occupancy changes are tight & win. Pivot to occupancy-only. Default-off. |
| 2026-07-22 | DFlash depth 4-10 sweep | 32.19 best exact | YES at depth 5/6/7 | depth 7 remains best exact but below record; depth 4 was 12/13; depths 8-10 exceeded exact M<=8 target guards, were 0/13, and fell to 4.94-6.11 tok/s. No two-start gate or payload. |

## Lever ladder (grind order; each exact + quality-gated)
1. **[DONE] DFlash verifier exactness and batching** — q=8 verifier == q=1
   target greedy, with one paged-decode pass, batched M=1 numerical lanes,
   fixed-rank sums, and deterministic direct MoE.
2. **[DONE; APPROVED] First verified record** — full-512 exact DFlash at
   33.085825 tok/s, LocalMaxxing `cmrw7cn1k006jnz01gq2z981v`.
3. **[DONE; APPROVED] MoE/EP launch/occupancy rebalance** — fused W1+SiLU,
   route-parallel W2, and M8 N-tile/route interleave produced the current
   two-start 33.438927 tok/s lower result, LocalMaxxing `cmrwot89400gqnz014oodtlbp`.
4. **[NEXT] Attention and router residual** — BF16 QKV+O is 2.918838
   ms/cycle; the largest single named kernel in the corrected residual is
   TopKGating at 0.560374 ms/cycle. Retain exact arithmetic and the full gate.
5. **[DONE] INT4 expert GEMM efficiency / occupancy** — N64 route-interleaved
   W1/W2 workgroups raised EU activity and produced the current record.
6. **Graph coverage** — first fix AOT cache identity/artifact selection and
   locate the first eager-vs-compiled tensor divergence. Fixed-rank reductions
   alone produced only 1/13 teacher matches and were reverted.
7. **[DEPTH SWEEP DONE] Better speculation** — depth 7 remains best exact.
   Depths >7 require widening or serializing all M>8 target verifier boundaries
   before acceptance policy or tree/multi-branch drafting can be promoted.
8. **FP8 KV for long context** — capacity (2x tokens/card) for real coding sessions;
   measure speed tradeoff (BF16 slightly faster at 8K).
9. **Quantization headroom (careful, quality-gated)** — if quality holds, reduce
   remaining BF16 bytes/token to raise the roofline itself. Only behind a real
   quality gate; never a silent lossy swap.

## Reusable assets
- vLLM branch `experiment/laguna-s-2.1-xpu-bringup-20260721`; XPU kernels
  `experiment/laguna-s-2.1-fwht-20260721` (attention tuples compiled, H128 FWHT).
- Weights on external drive: `.../laguna-s-2.1/{int4,dflash-int4}`.
- Gates/tools under `experiments/laguna-s-2.1-xpu-b70/tools/`.
- Bring-up + result notes under `notes/` (dated).
