# DeepSeek V4.1 Flash: required operator/format × native support table

First bounded task from [deepseek-v41-onboarding.md](deepseek-v41-onboarding.md),
2026-11-08. CPU-only audit; no GPU admission, no admission-guard relaxation.

**Identity (owner-confirmed this session, resolving onboarding gate 1):**
`unsloth/DeepSeek-V4.1-Flash-1017-GGUF`, variant **UD-IQ2_XXS** — six shards
(165.3 GB backbone + one 135.2 GB engram tensor), plus
`dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf` (8.0 GB draft) and
`mmproj-BF16.gguf` (0.97 GB vision). All local bytes sha256-verified against
HF LFS; census: `../../data/deepseek-v41-flash-iq2xxs-census-20261108.json`.
Reference graph reader: llama.cpp `src/models/deepseek4.cpp` (arch
`deepseek41`), KV state in `src/llama-kv-cache-dsv4.h`, engram/PLE lookup in
`src/models/qwen4exp.cpp` (same `per_layer_token_embd.weight` mechanism).

## GGUF tensor formats (measured census vs engine decoders)

Engine decoder inventory: `engine/src/stage2/packet2/kernels/math.hpp`
(`enum class Type`, `layout()`, `decode()`, `gemv_row()`); SC117 retained
kernels in `engine/src/gsq-rco-iq3s/`. Backbone = 165.3 GB over shards 2–5
(shard 1 is metadata-only, 0 tensors/96 KVs — Unsloth split convention).

| GGUF type | Bytes in artifact | Native decode today | Gap | Smallest missing fixture |
| --- | ---: | --- | --- | --- |
| F32 | 0.7 GB (norms, sinks, biases) | ✅ | — | — |
| BF16 | 0.2 GB | ✅ | — | — |
| Q8_0 | 5.4 GB (embd, LoRA a/b, attn_kv) | ✅ | — | — |
| Q6_K | 2.2 GB (incl. output head) | ✅ | — | — |
| Q5_K | 135.2 GB (**engram table**) | ✅ decode exists | usage is row-gather, not GEMV | gather 176 B rows by index from mmap'd file; compare vs llama.cpp PLE lookup rows |
| Q2_K | 1.5 GB (1 tensor) | ❌ no match in `engine/src` | decoder + gemv | CPU `decode()` of one Q2_K superblock row vs llama.cpp `dequantize_row_q2_K` on real shard bytes |
| IQ2_S | 65.3 GB | ✅ (`math.hpp` {256,82}) | — | — |
| IQ2_XS | 7.9 GB | ❌ absent | decoder + gemv | single-row codebook decode vs llama.cpp reference |
| **IQ2_XXS** | **38.5 GB** | ❌ absent | decoder + gemv; **bulk of attention/shared tensors** | single-row decode vs reference, then packed `gemv_row` fixture |
| IQ1_S | 17.7 GB (20 tensors) | ❌ absent | decoder + gemv | single-row decode vs reference |
| IQ3_XXS | 26.0 GB | ✅ | — | — |
| IQ4_NL_4_4 | 7.6 GB (dspark only) | ❌ absent | 4×4-interleaved layout decode | one expert row decode; dspark is a separate later gate |

## Operators (deepseek41 graph vs engine op set)

Engine op set today: `plan.hpp` Builder (`hc`, `gdn`, `qsa`, `moe`, `ple`,
`route` softmax+top-10, `argmax`), contract in `kernels/api.hpp`.
llama.cpp reference: `src/models/deepseek4.cpp` (function lines cited).

| Required operator | llama.cpp source | Native support | Gap | Smallest missing fixture |
| --- | --- | --- | --- | --- |
| HC pre/post/mix, 4 streams | `build_hc_pre:281`, `build_hc_post:413` | ✅ `hc()` in plan.hpp | — | — |
| **HC Sinkhorn norm, 20 iters, eps 1e-7** | `build_hc_sinkhorn:308` | ❌ | new op | 4×5120 stream vector through 20 Sinkhorn iters vs CPU reference, bit-exact F32 |
| Compressed-KV attention (HCA: 512-latent KV, q-LoRA 1280, output LoRA 1024, 8 output groups) | `build_hca_attention:776`, `build_hca_compressed_kv_from_state:472` | ❌ (GDN/QSA exist; no MLA-latent path) | new attention family | one layer, 40-token prompt, BF16 KV: layer output vs pinned same-GGUF llama.cpp logits |
| **CSA + LID indexer** (candidate blocks 8, top_k 512/2048, key 128, source layers) | `build_csa_lid_attention:715`, `build_lid_top_k:592`, `build_top_k_mask:679` | ⚠️ closest: `qsa_select`/`qsa_attention` (budget 2048, head 128) | DSv4 indexer semantics differ (block-level, shared source layers) | index-select fixture: fixed pooled keys → expected block IDs, tie-order pinned |
| Sliding window 128 + attention sinks | `build_attention:867` (sinks tensor in census) | ❌ | window/sink semantics in attention op | covered by the HCA fixture's masks |
| Yarn RoPE (16× from 64 K, β32/1, compress base 160000) | `ggml_rope_ext` calls, deepseek4.cpp | ⚠️ engine has fixed rope tables (`rope-262144.bf16`) | yarn-scaled table generation | rope table rows vs `ggml_rope_ext` yarn output |
| Sigmoid route, top-6, weights-norm ×1.5, 384 experts | MoE section of deepseek4.cpp; census `exp_probs_b` biases | ❌ contract is softmax+top-10+renorm (api.hpp) | route op variant | one router logits vector → ids/probs vs reference; bias `exp_probs_b*` applied |
| MoE experts mid=2304 + per-layer swiglu clamps | census: `swiglu_clamp_exp/shexp` arrays (40 vals) | ⚠️ `moe()` exists (512/top-10/640) | dims + clamp op | single expert gate/up/down row + clamp vs dequant reference |
| Engram hash + lookup (ngram 4, 2 layers, 8 heads, 48 head offsets) + gate/conv | `qwen4exp.cpp` PLE path; metadata `ple.*`/`engram.*` | ⚠️ `ple()` exists for resident tables | **135 GB NVMe-backed store + prefetch admission** (api.hpp: "separately admitted stable device-addressable mapping") | hash fixed token triple → row IDs; gather rows from mmap; compare vs llama.cpp rows |
| Output LoRA head (hidden→20480 via rank 1024) | `build_hc_head:450` + output LoRA | ❌ plain `output.weight` gemv only | two-stage head | dot through a/b pair vs reference |
| DSpark draft (3 blocks, 128 experts top-3, markov 256, noise token) | dspark GGUF (verified) | ❌ | separate draft program (packet56/58 pattern) | later gate; not blocking text decode |

## Admission / resource deltas (vs `reusable-onboarding-audit.md` gates)

- `deployment/prepare.py::load_profile` requires `qwen4exp`/4096/F32 → new
  `deepseek41` capability path required (audit gate 2). `parse_placement`
  `layer < 48` admits 40 layers unchanged.
- Wire F32 stream cap 64 KiB: HC stream boundary here is 4×5120×4 B = 80 KiB →
  needs the negotiated/versioned mapping the audit's gate 4 describes.
- Placement: 165.3 GB ÷ 6 B70 ≈ 27.6 GB/card packed — inside the 31 GB
  planning bound; six-stage policy absent (audit gate 3); ring CPU fixtures
  already cover 6 owners.
- KV is ~80 KB/token BF16 (latent 512+512 × 40 layers) → BF16-KV standing
  rule holds; 32 K ctx ≈ 2.6 GB/slot.
- Engram host economics: ~320 random 176 B rows/token (~60 KB) — latency-bound;
  row indices are hash-known one step ahead → prefetch is the planned lever.
  16 GB host RAM forbids full shadowing; mmap + bounded page cache only.

## Suggested next bounded tasks (pick one each)

1. Q2_K decoder + CPU gemv fixture (smallest format gap; unblocks 1 tensor).
2. IQ2_XXS decode + packed gemv fixture (highest value; bulk format).
3. HC-Sinkhorn CPU fixture (pure arithmetic, no formats needed).
4. Route-variant fixture (sigmoid top-6 norm×1.5; pure arithmetic).
5. Engram hash→row gather fixture against local shard 6 (mmap read-only).

No source, capability check, service or host setting was changed for this
table. References: census JSON above;
[port map + code-level surface](../../notes/2026-11-08-deepseek-v41-flash-port-map.md);
llama.cpp `deepseek4.cpp` at pinned local clone `7d7f02875`.
