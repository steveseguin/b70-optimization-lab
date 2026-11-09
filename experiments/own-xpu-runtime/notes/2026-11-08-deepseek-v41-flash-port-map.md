# DeepSeek-V4.1-Flash-1017 → ownrt port map (2026-11-08)

Owner asked (2026-11-08): continue improving our own runtime, support
Qwen3.8-Flash-Next and DeepSeek V4.1 at different quants, keep it reusable
for fast future model onboarding. This note maps the deepseek41 lane against
what the runtime already owns. Objective lane priority 3 already lists
"DeepSeek V4 Flash". No GPU work here; reference numbers are llama.cpp
screens, not lab measurements.

## Reference state (advisory, not a lab record)

- Weights: Unsloth `DeepSeek-V4.1-Flash-1017-GGUF`, UD-IQ2_XXS, 6 shards,
  165.3 GB backbone + 135.2 GB Q5_K engram + 8.0 GB DSpark Q8_0 drafter,
  sha256-verified against HF LFS on `/mnt/fast-ai/llm-models/...`.
- llama.cpp master (7d7f02875, SYCL JIT) runs it on 6×B70: ~14.2 tok/s
  decode, 200→91 tok/s prefill (2K→12K tokens), 32K ctx, ub256 required
  (ub512 flash-attn workspace OOMs), `-fa on` mandatory (fa-off broken for
  this arch), engram on NVMe via mmap (`per_layer_token_embd.weight=CPU`).
  Oracle pack: `/mnt/fast-ai/bench-results/dsv41-oracle-pack-iq2xxs.json`
  (12 prompts, greedy, 128-token cap; KV was q8_0 — label as compressed-KV
  reference, recapture at BF16 if promoted to a gate).
- Intel landmines hit and worked around: AOT SYCL build segfaults
  (intel/llvm#23395 → JIT only), `SYCL_CACHE_PERSISTENT=1` segfaults
  (intel/llvm#22853 → never set), `-sm row` broken on 6 GPU.
- DSpark drafter on llama.cpp measured slower (12.3 vs 14.2 tok/s): drafter
  competes for the same cards; acceptance can't pay for it there. Our
  pipeline places the draft differently (packet32/36 pattern).

## Architecture census (from verified shard-1 metadata)

`general.architecture = deepseek41`, 748B-A16B, ctx 1M (yarn 16× from 64K,
β_fast 32 / β_slow 1, rope dim 64, θ 10000).

| Block | deepseek41 | Flash-Next (owned) | Reuse |
|---|---|---|---|
| Blocks | 40 | 48 | structural |
| Hidden | 5120 (out 20480 via output LoRA rank 1024) | 2560 | structural |
| Attention | latent KV: 1 KV head, k/v len 512, q LoRA 1280, 64 q heads, sliding window 128, per-layer compress_ratios (43) | GDN 36 + full 12, QSA | **new: MLA-latent path** |
| Sparse indexer | candidate blocks 8, top_k 512 / 2048 blocks, key len 128, source layers | QSA indexer budget 2048, head 128 | **high — same pattern** |
| MoE | 384 routed + 1 shared, top-6, expert FFN 2304, gate func 4, norm w/ scale 1.5, per-layer swiglu clamps | 512 routed top-10, FFN 640, shared | high — same machinery, new dims |
| PLE/engram | engram vocab 16M (compressed 99092, token_map 129280), per-layer input dim 256; PLE 2 layers, ngram 4, 8 heads/ngram, 48 head offsets | PLE layer 2, 20M vocab, ngram 3, 8 heads | pattern owned; **scale is new: 135 GB on NVMe, 16 GB RAM host** |
| Hyperconnections | 4 streams, **Sinkhorn 20 iters**, eps 1e-7 | 4 streams, low-rank 320 | owned + Sinkhorn is new |
| Draft (DSpark) | block 5, 128 experts top-3, markov_rank 256, noise token 128799, 3 target layers | native MTP 1 block + draft pipeline (53/63) | pattern owned |
| KV bytes/token | ≈80 KB BF16 (1 KV head, latent 512+512, 40 layers, compressed) | GDN state + KV | KV is **cheap**: 32K×2 slots ≈ 5 GB → BF16-KV standing rule holds easily |

## Staged packet plan (their gates)

**A. Identity & oracle (CPU-only, no GPU)**
- A1 identity packet: pin Unsloth revision, full tensor census of all 6
  shards + engram + dspark + mmproj (per-tensor ggml types — which tensors
  are IQ2_XXS vs Q5_K/Q6_K/Q8_0), tokenizer requirements, config snapshot.
  Mirror of stage2/packet1.
- A2 loader contracts: extend the existing GGUF IQ-grid + UD-mixture rows of
  DESIGN.md with the dsv41 census; bounded reads, coverage/duplicate/overlap
  validation; engram tables as a separate mapped store class (not weights).
- A3 CPU oracle `dsv41-iq2xxs-p1`: frozen-order CPU dequant + decode of the
  12-prompt suite. Cross-check against the llama.cpp oracle pack (independent
  code, same bytes); disagreements resolve to our CPU reference per the
  quantized-line rule.

**B. CPU engine (tiny dsv41 Engine)**
- B1 explicit node list: embedding → 40 blocks (latent-KV attention with
  indexer sparsity + sliding window → HC Sinkhorn mixing → MoE 384/top-6 +
  shared → engram inject) → norm → output LoRA head.
- B2 engram subsystem: hash/ngram gather over mmap'd Q5_K tables, prefetch
  policy, page-cache accounting on a 16 GB host. Deterministic replay
  boundary semantics (DESIGN.md expert-streaming section applies).
- B3 DSpark block on CPU: proposals, Markov/noise-token handling, acceptance
  vs target.

**C. Device kernels (measured levers, biggest first)**
- C1 **IQ2_XXS GEMV** — scoreboard has IQ2_S expert gate/up at 51 GB/s = 9%
  of the 590 GB/s ceiling; IQ2 grids are ~90% of this backbone. Every 100
  GB/s here is worth more than any other single lever in this lane.
- C2 latent-KV attention + indexer gather (sparse blocks, sliding window 128)
  with yarn tables; deterministic exp/log per identity v2.
- C3 HC Sinkhorn (20 iters, 4 streams) — fused, fixed-order.
- C4 MoE: route kernel (384 experts, func 4, norm/scale) + expert gate/up/down
  at FFN 2304 + per-layer swiglu clamps.
- C5 engram device path: UVA/mmap gather with async prefetch; next-token
  ngram rows are known one step ahead, so prefetch hides NVMe latency —
  the structural lever llama.cpp leaves unused.

**D. Placement & integration**
- D1 6-card census: 165.3 GB ÷ 6 ≈ 27.6 GB/card backbone; layer split per
  DESIGN.md preference (tensor split measured not worth it on Flash-Next:
  41 exchanges ≈ 1.53 ms/layer). 40 blocks / 6 cards = 6–7 blocks each.
- D2 six-process pipeline with draft overlap (extend packet32/36 two-card
  pattern; peer costs measured: 52 µs round trip).
- D3 whole-step capture after kernels settle (capture prerequisites in
  DESIGN.md unchanged).

**E. Records & gates**
- E1 12-prompt suite, 128-token cap, exact vs `dsv41-iq2xxs-p1`, median of
  99 intervals — headline vs the 14.2 tok/s llama.cpp screen.
- E2 context scaling 4K → 32K → (later) yarn 256K/1M with bit-exactness per
  packet44 pattern.
- E3 DSpark acceptance campaign (packet31/36 methodology), then serving
  (packet201 pilot pattern) only after the decode line is certified.

## Tensor census (2026-11-08, from verified local files)

Full JSON: `../data/deepseek-v41-flash-iq2xxs-census-20261108.json`.

- Split convention: shard 1 is metadata-only (0 tensors, 96 KVs, 10 MB);
  backbone = shards 2–5 (165.3 GB), engram = shard 6.
- Backbone type mix (bytes): IQ-family ≈ 155 GB = 94% of backbone (IQ2_S 65.3,
  IQ2_XXS 38.5, IQ3_XXS 26.0, IQ1_S 17.7, IQ2_XS 7.9), Q8_0 5.4 (embeddings,
  LoRA a/b, attn_kv), Q2_K 1.5, Q6_K 2.2 (incl. output head 0.54), F32/BF16
  ≈ 0.8 (norms, sinks, router biases). Kernel coverage needed: IQ1_S/IQ2_XXS/
  IQ2_XS/IQ2_S/IQ3_XXS/Q2_K GEMV + Q8_0/Q6_K utility — all inside the GGUF
  IQ-grid row already in DESIGN.md.
- Engram: ONE tensor `per_layer_token_embd.weight` (256, 768022850) Q5_K,
  135.2 GB. One row = one 176-byte Q5_K superblock. Per generated token:
  ~40 layers × 8 n-gram heads ≈ ~320 random rows ≈ ~60 KB — latency-bound,
  not bandwidth-bound (~1 MB/s at 14 tok/s). llama.cpp pays synchronous
  page-fault latency per row; prefetch is possible because row indices are
  hash functions of the just-decoded token, known before the layer runs.
- DSpark: 3 blocks × 128 experts (top-3); bulk = 9 expert tensors in
  IQ4_NL_4_4 (XMX 4×4-interleaved layout), 7.64 GB + Q8_0 MLA pieces.
- Naming is llama.cpp-convention MLA: `attn_kv` (512 latent), `attn_q_a/b`
  (1280 rank), `attn_output_a/b` LoRA, `attn_sinks`, `exp_probs_b` (384).

## Code-level port surface (from the packet58aj/packet165 sources)

The engine's model contract is `flash::Builder` (`packet3/step/plan.hpp`):
`hc()` / `gdn()` / `qsa()` / `moe()` / `ple()` emit `Launch` lists over a
`Directory` of typed tensors. deepseek41 plugs in as:

1. **Grids** — `packet2/kernels/math.hpp`: `enum class Type` (GGUF ids),
   `layout()`, `decode()`, `gemv_row()`. Today: F32/F16/Q8_0/Q3_K/Q6_K/
   IQ3_XXS/IQ4_NL/IQ3_S/IQ2_S/BF16. Add: **IQ2_XXS=16, IQ2_XS=17, IQ1_S=19,
   Q2_K=10, Q5_K=13, IQ4_NL_4_4=39** (dspark). Each needs decode + packed
   gemv_row + device kernel — that is kernel campaign C1, one grid at a time,
   IQ2_XXS first (bulk of backbone).
2. **Builder methods** — new `mla()` (q_a/q_b LoRA + 512-latent KV + sinks +
   yarn rope + sliding window 128 + indexer select; closest existing pattern
   is `qsa()`'s indexer→select→attend flow), `sinkhorn` step inside `hc()`
   (20 iters, 4 streams), DSv4 `route` (sigmoid + top-6 + norm×1.5 — current
   contract is softmax+top-10), per-layer swiglu clamp in `ffn()`.
3. **Engram** — `ple()` already hashes n-grams and `lookup`s
   `per_layer_token_embd.weight`; DSv4 needs the lookup backed by a 135 GB
   NVMe-mapped store with prefetch (the api.hpp contract's "separately
   admitted stable device-addressable mapping" hook is the admission point),
   ngram=4, 2 PLE layers.
4. **Placement** — `build()` hardcodes two cards (`1 - card` flips); 40
   blocks over 6 cards means generalizing begin/handoff/handoff_result to an
   N-card chain (6–7 blocks/card, ~27.6 GB each).
5. **DSpark** — separate draft program, same shape as the packet56/58 draft
   line: 3-block mini-deepseek41, IQ4_NL_4_4 experts, markov_rank 256.

## Risks (honest)

1. IQ2 kernel quality is the whole game; current IQ2_S path is 9% of
   roofline. If it can't be lifted, this lane caps near llama.cpp speed.
2. Engram on a 16 GB RAM host: 135 GB cannot shadow in RAM. mmap + prefetch
   is unproven here; measure random-row latency/IOPS on the 9100 PRO early
   (bounded, read-only probe) before committing C5's design.
3. 6-card orchestration is beyond the tested 2-card process pair; oneCCL
   census is open.
4. llama.cpp oracle pack used q8_0 KV; recapture at BF16 KV before any
   cross-runtime equality claim (KV bytes are cheap for this arch, so BF16
   fits).

## Next packet proposal

A1 (identity + tensor census) — CPU-only, local verified files, mirrors
stage2/packet1. No GPU, no downloads, no settings changes.
