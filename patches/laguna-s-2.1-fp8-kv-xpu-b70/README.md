# Laguna FP8 KV source patches

These patches apply on top of the sealed Laguna BF16 record vLLM source:

```text
base: e596ef1543466ae1a05e5bb8091f58872e2b18ba
head: c2dd002ff11a156392b8ba429ffd7259deae810c
```

Apply in order:

```bash
git checkout e596ef1543466ae1a05e5bb8091f58872e2b18ba
git am /home/steve/llm-optimizations/patches/laguna-s-2.1-fp8-kv-xpu-b70/*.patch
```

Patch 1 restores explicit FP8/E4M3 KV eligibility in the rewritten
FlashAttention backend. The lower XPU implementation already contains the
official vLLM XPU FP8 support: BF16 queries remain unquantized, calibrated K/V
descales are forwarded, and Xe2 reads/writes E4M3 cache values.

Patch 2 adds a default-off, fail-closed post-load audit. When
`VLLM_XPU_LAGUNA_FP8_KV_SCALE_AUDIT=1`, every target rank must match the pinned
48-layer checkpoint scale digest. Every DFlash rank must separately report its
six FP8 cache layers as unit-scale and uncalibrated. This prevents a successful
FP8 allocation from being mistaken for proof that calibrated scales loaded.

The active clean worktree is
`/home/steve/src/laguna-vllm-fp8-kv-20260727`. The XPU kernel tree remains the
unchanged clean record-derived
`/home/steve/src/laguna-xpu-kernels-width12-router-clean-20260726` at
`6f9dd3c3a7b1b677a992ca4f431a968408f9c816`.
