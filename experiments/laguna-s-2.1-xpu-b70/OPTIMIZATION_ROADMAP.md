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
| 2026-07-22 | exact DFlash (serialized M=1 verify) | 7.45 | YES | 7/7 token-match incl rollover; but serialization kills speed (host 50%+collectives 35%) |
| 2026-07-22 | batched-exact DFlash | **37.59** | **YES** | 7/7 cold token-match incl rollover; 30.981% acceptance; 3.1566 emitted/cycle; 98 collectives/cycle; candidate record, not submitted |

## Lever ladder (grind order; each exact + quality-gated)
1. **[DONE] DFlash verifier exactness and batching** — q=8 verifier == q=1
   target greedy, with one paged-decode pass, batched M=1 numerical lanes,
   fixed-rank sums, and deterministic direct MoE.
2. **[CANDIDATE; CLAUDE GATE] First verified record** — identity and realistic
   cold suite captured at 37.586 tok/s; do not submit without Claude review.
3. **[READY] MoE/EP overhead** — remove the remaining 47 layer-level EP
   all-gather + rank-sum pairs and persist/fuse the direct M8 expert sequence.
   The exact direct-route contract is now component- and model-gated.
4. **Attention** — BF16 Q/K/V/O bandwidth; sliding-window(512) decode efficiency;
   full-attn layers.
5. **INT4 expert GEMM efficiency / occupancy** — DFlash M=7/8 batches work (helps
   the M=1 occupancy starvation we hit on DeepSeek); tune the group-32 W4A16 GEMMs.
6. **Graph coverage** — widen PIECEWISE/full graph capture; cut host/launch overhead.
7. **Deeper/better speculation** — DFlash depth tuning, acceptance improvement,
   tree/multi-branch drafting (exact-verified).
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
