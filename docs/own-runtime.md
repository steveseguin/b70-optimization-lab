# The Own Xe Runtime (own-xpu-runtime)

A custom SYCL/Xe inference engine for Qwen3.8 hybrid-architecture models on
Intel Arc Pro B70 GPUs, built and validated in this repository under a
fail-closed packet campaign. It exists to prove two things at once: **speed**
(records on LocalMaxxing, sealed profiles) and **exactness** (every published
output byte-identical to its oracle or to an independent repeat run, with
receipts).

- Engine + campaign: [`experiments/own-xpu-runtime/`](../experiments/own-xpu-runtime/README.md)
  · [SCOREBOARD](../experiments/own-xpu-runtime/SCOREBOARD.md)
  · [DESIGN](../experiments/own-xpu-runtime/DESIGN.md)
- User-facing packages: [TP2 two-card](../packages/qwen38-flash-next-iq3xxs-ownrt-tp2-b70/package.json)
  · [TP1 one-card](../packages/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/package.json)
  (rendered on neural.download under *Qwen3.8 Flash-Next UD-IQ3_XXS — own runtime*)
- Reproduction bundles: [`repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/`](../repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/)

## Measured state (all with receipts; caps stated, not hidden)

| Lane | Profile | Decode | Prompt reading | Exactness |
|---|---|---|---|---|
| Flash-Next UD-IQ3_XXS, 2×B70 | full512, 4096 ctx, sealed packet165 | 58.557–58.632 tok/s (fresh suites); requalified 58.724/58.676 on 2026-10-20 | 75.884–75.973 tok/s | Oracle checks first 128 tokens; full 6,495-token arrays repeat-exact across loads and identical to the original sealed qualification |
| Flash-Next UD-IQ3_XXS, 1×B70 | full512, 4096 ctx, sealed packet165 | 31.510–31.782 tok/s; requalified 31.766/31.774 | 32.595–32.752 tok/s | same discipline |
| Flash-Next records (packet58as, approved on LocalMaxxing) | 128-token capped suites | 58.798109 (two-card) · 34.573038 (one-card) | — | capped-record scope stated on the package pages |
| Qwen3.8 27B (GGUF-comparable lane, packet44) | 128-token 12-prompt suite | 37.59/37.77 tok/s @ 4,096 ctx · 37.71/37.70 @ 32,768 ctx (llama.cpp reference on the same suite: 28.49) | — | 12/12 requests bit-exact at both capacities |

Strict quality promotion for the full512 profiles is pending and labeled as
such on the packages; oracle coverage beyond 128 tokens is an explicit,
declared gap.

## Why a custom engine

- **Architecture fit.** Qwen3.8 Flash-Next is a hybrid: 48 layers = 36 GDN
  (gated delta net, linear attention) + 12 QSA full-attention layers, a
  512-expert top-10 MoE, and a PLE early layer. The engine is designed
  around that structure (per-layer plan, resident expert cache, snapshot
  banks) instead of inheriting generic kernels.
- **Exactness as a gate, not a hope.** Sealed sources, admission-checked
  device windows, fresh-process determinism, oracle prefixes, and
  fail-closed comparisons. A run that cannot prove itself does not publish.
- **Own the whole stack.** Session checkpoint/restore, state residency and
  future context features need engine-level access that frontends do not
  expose. See [SESSION-SWAP-DESIGN.md](../experiments/own-xpu-runtime/SESSION-SWAP-DESIGN.md)
  — the checkpoint contract (save/inspect/restore/delete, compatibility
  checks, prefix-plus-delta rules) the ctxkeeper integration builds against.
  Labeled experimental until its restart-and-continue exactness test passes.

## Open items (tracked, in priority order)

1. **Rebuilt-binary device qualification.** The portable source rebuild
   (CPU-compile-validated, 42 TUs) produces a binary with a different hash
   than the sealed historical one; the engine binary is seal-pinned, so
   qualification means a new sealed packet. Until then, published device
   results belong to the historical binary — stated on the packages.
2. **Portability checks.** Clean-host replays and tested platform/driver
   installs are listed per package in its `missing` field; closing them
   outranks new hardware claims.
3. **Session swap v1** per the design contract above.

## Honest non-goals today

- No sampler: greedy argmax only (no RNG state exists in the engine).
- No multi-user controller: the packet165 controller is sequential;
  concurrency curves exist only for the vLLM FP8 packages.
- No context curve for the own-runtime full512 profiles: measured at 4096;
  other capacities are unmeasured, not claimed.
