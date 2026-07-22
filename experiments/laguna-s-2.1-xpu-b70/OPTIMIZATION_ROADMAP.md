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
| 2026-07-22 | **fused W1+SiLU + route-parallel W2** | **33.267564** | **YES (13/13 x2)** | lower of 33.303424/33.267564; cache-zero, cross-request, rollover, and cross-start exact. 6→4 launches/layer and 10x W2 work availability vs serialized fusion. Payload staged, not submitted. |

## Lever ladder (grind order; each exact + quality-gated)
1. **[DONE] DFlash verifier exactness and batching** — q=8 verifier == q=1
   target greedy, with one paged-decode pass, batched M=1 numerical lanes,
   fixed-rank sums, and deterministic direct MoE.
2. **[DONE; APPROVED] First verified record** — full-512 exact DFlash at
   33.085825 tok/s, LocalMaxxing `cmrw7cn1k006jnz01gq2z981v`.
3. **[DONE; STAGED] MoE/EP launch/occupancy rebalance** — retaining fused
   W1+SiLU while restoring route-parallel W2 produced a two-start exact lower
   result of 33.267564 tok/s. The payload is staged for Claude; it is not yet an
   approved LocalMaxxing row. The remaining 47 layer-level EP transactions are
   causally separated by layer dependencies.
4. **Attention** — BF16 Q/K/V/O bandwidth; sliding-window(512) decode efficiency;
   full-attn layers.
5. **[NEXT] INT4 expert GEMM efficiency / occupancy** — test the audited
   W2-only N64 route-interleaved workgroup enumeration without changing
   arithmetic; if neutral, screen N128+interleave before N32 and avoid GRF128.
6. **Graph coverage** — first fix AOT cache identity/artifact selection and
   locate the first eager-vs-compiled tensor divergence. Fixed-rank reductions
   alone produced only 1/13 teacher matches and were reverted.
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
