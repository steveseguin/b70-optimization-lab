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
| Flash-Next UD-IQ3_XXS, 1×B70, portable source rebuild (packet178, binary `6fa840ab…`) | full512, 4096 ctx | 31.83 / 31.81 tok/s (two fresh loads, 2026-10-22) | not re-measured on this row | oracle-128 exact; all 12 `output_token_sha256` identical across loads and identical to the sealed packet165 line — the rebuild reproduces the published one-card line ([window record](../notes/2026-10-21-own-runtime-window-pin-guard-refusal.md), evidence `experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/evidence/device-p178-full512-A-{a,b}/`) |
| Flash-Next UD-IQ3_XXS, 1×B70, checkpoint engine (packet179, packet165 relink) | save at K=256, fresh-process restore, M=128 | restore 0.458 s + 6.78 s continuation vs 36.75 s cold prefix; reference load 31.85 tok/s | — | merged 384 tokens == uninterrupted reference at [0:384); two independent restores identical; oracle-128 exact; save 1.10 s / 68,756,516 B / 128 blobs. Same-generation resume only; manifest label stays `experimental` (evidence `…/packet179-session-swap/one-card/evidence/device-p179-checkpoint-A-b/`) |
| Flash-Next UD-IQ3_XXS, 1×B70, checkpoint engine v2 (packet180, binary `f68714ce…`, 2026-10-22) | save at K=256, restore + append a 126-token turn, M1=128; restore-then-save, resume M2=64 | restore 0.41–0.46 s; append prefill of the 127 remaining input tokens 5.59 s vs 16.0 s cold prefill of all 469 (2.66×); reference load 31.78 tok/s | — | append output == one-shot reference [0:128]; restore-then-save chain == reference [128:192]; repeat append identical and re-saved state byte-identical (128 blobs); inspect/delete tools passed; 36/36 gates (evidence `…/packet180-session-swap-v2/one-card/evidence/device-p180-lifecycle-A-b/`) |
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
  Its §7 gates 1–4 (restart-and-continue byte identity, repeat determinism,
  cold-start comparison, admission discipline) passed on device on
  2026-10-22 for the same-generation operation (table above; contract v1.2).
  packet180 (2026-10-22, same window discipline) added and qualified on
  device: appending a new turn to a restored session, restore-then-save,
  one manifest source of truth with a tamper refusal, a shared lock for
  save/restore/delete, and single-JSON / metadata-only inspect. The manifest
  label is still the string `experimental`; changing it is an engine string
  change carried by the next relink.

## Open items (tracked, in priority order)

1. **Two-card rebuilt-binary device qualification.** The portable source
   rebuild (42 TUs) produces a binary with a different hash than the sealed
   historical one, so it needs its own device packet. The **one-card** rebuild
   passed on 2026-10-22 (packet178, table above). The **two-card** rebuild has
   not been run on device; until it is, the two-card package's published
   results belong to the historical binary — stated on that package.
2. **Portability checks.** Clean-host replays and tested platform/driver
   installs are listed per package in its `missing` field; closing them
   outranks new hardware claims. The TP1 portability replay needs about
   92 GiB of host RAM (the two-card host has 15 GiB), so it waits for a
   suitable host.
3. **Session swap, next engine revision**: flip the manifest label string
   (packet181, built); then TP2 checkpoints (contract §10 item 1) and the
   ctxkeeper adapter. The append's 5.59 s on device is the cold expert cache
   of a fresh process (the reference's first 126 positions took 5.68 s), not
   a slower path; this engine steps every prompt position one at a time. Done on device 2026-10-22: same-generation resume
   (packet179) and append + restore-then-save + lock/manifest/inspect
   (packet180).

## Honest non-goals today

- No sampler: greedy argmax only (no RNG state exists in the engine).
- No multi-user controller: the packet165 controller is sequential;
  concurrency curves exist only for the vLLM FP8 packages.
- No context curve for the own-runtime full512 profiles: measured at 4096;
  other capacities are unmeasured, not claimed.
- No ctxkeeper adapter yet: append and restore-then-save are qualified
  on device, but ctxkeeper does not call the checkpoint operations; the
  manifest label is still `experimental` until the next relink changes it.
