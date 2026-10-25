# The Own Xe Runtime (own-xpu-runtime)

A custom SYCL/Xe inference engine for Qwen-like models on Intel Arc Pro B70
GPUs. The goal is reusable support for multiple quantizations, model variants
and card counts, with each optimization checked against its declared reference.
Internal output parity and independent-reference fidelity are separate gates.

## Current SC117 work — October 25

The SC117 IQ3_S F32 service observations improved from **27.92 to 47.89 tok/s**
using the conventional all-prompt median. All twelve retained output token
arrays match. This is not the certified class-balanced benchmark. Six of 5,965
teacher-forced CPU-reference positions still disagree; no broad bit-faithful or
no-added-quality-loss claim follows. The first complete four-card live-draft
suite measured **42.31 tok/s**, below the later two-card **47.97 tok/s** service
observation; their timestamp sources differ. All 5,965 output IDs match.

The newer two-step rolling scheduler passes the bounded correctness gate:
all 32 outputs, 2,065 target buffers and 73 draft allocations match while
consuming 35 actual speculative target rows. Both miss depths occurred, and
seven first-stage rollbacks preserved draft state. Diagnostic checks were
enabled, so this is not a speed result. Existing draft weights were used;
training is prohibited. See the [actual rolling proof](../experiments/own-xpu-runtime/research/continuation-2026-10-25/ring-rolling-depth2-proof/RESULT.md)
and [measured four-card suite](../experiments/own-xpu-runtime/research/continuation-2026-10-25/persistent-suite-b-proof/RESULT.md).

Start with the [evidence review and release direction](sc117-engine-review.md),
[canonical engine](../experiments/own-xpu-runtime/engine/README.md) and
[placement planner](../experiments/own-xpu-runtime/engine/planning/README.md).
The current source is available; the complete portable release remains open.
The historical Unsloth/BF16 profiles below use different weights and arithmetic.

- Engine + campaign: [`experiments/own-xpu-runtime/`](../experiments/own-xpu-runtime/README.md)
  · [SCOREBOARD](../experiments/own-xpu-runtime/SCOREBOARD.md)
  · [DESIGN](../experiments/own-xpu-runtime/DESIGN.md)
- User-facing packages: [TP2 two-card](../packages/qwen38-flash-next-iq3xxs-ownrt-tp2-b70/package.json)
  · [TP1 one-card](../packages/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/package.json)
  (rendered on neural.download under *Qwen3.8 Flash-Next UD-IQ3_XXS — own runtime*)
- Reproduction bundles: [`repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/`](../repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/)

## Historical measured state (different model and arithmetic)

These retained results use the earlier custom BF16 recurrent-state contract.
Matching its oracle or repeating the same output does not establish reference
FP32 fidelity. They are not performance results for current SC117 F32.

| Lane | Profile | Decode | Prompt reading | Exactness |
|---|---|---|---|---|
| Flash-Next UD-IQ3_XXS, 2×B70 | full512, 4096 ctx, sealed packet165 | 58.557–58.632 tok/s (fresh suites); requalified 58.724/58.676 on 2026-10-20 | 75.884–75.973 tok/s | Oracle checks first 128 tokens; full 6,495-token arrays repeat-exact across loads and identical to the original sealed qualification |
| Flash-Next UD-IQ3_XXS, 1×B70 | full512, 4096 ctx, sealed packet165 | 31.510–31.782 tok/s; requalified 31.766/31.774 | 32.595–32.752 tok/s | same discipline |
| Flash-Next UD-IQ3_XXS, 1×B70, portable source rebuild (packet178, binary `6fa840ab…`) | full512, 4096 ctx | 31.83 / 31.81 tok/s (two fresh loads, 2026-10-22) | not re-measured on this row | oracle-128 exact; all 12 `output_token_sha256` identical across loads and identical to the sealed packet165 line — the rebuild reproduces the published one-card line ([window record](../notes/2026-10-21-own-runtime-window-pin-guard-refusal.md), evidence `experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/evidence/device-p178-full512-A-{a,b}/`) |
| Flash-Next UD-IQ3_XXS, 1×B70, checkpoint engine (packet179, packet165 relink) | save at K=256, fresh-process restore, M=128 | restore 0.458 s + 6.78 s continuation vs 36.75 s cold prefix; reference load 31.85 tok/s | — | merged 384 tokens == uninterrupted reference at [0:384); two independent restores identical; oracle-128 exact; save 1.10 s / 68,756,516 B / 128 blobs. Same-generation resume only; manifest label stays `experimental` (evidence `…/packet179-session-swap/one-card/evidence/device-p179-checkpoint-A-b/`) |
| Flash-Next UD-IQ3_XXS, **2×B70**, checkpoint engine TP2 (packet184, binary `ebbc9b15…`, 2026-10-22) | save at K=256, fresh-process restore + 128 tokens; append a 126-token turn, restore-then-save, resume, repeat append | save 128.8 MB in 1.85 s; restore 2.32 s + first token 92 ms vs 59.3 s cold prefix; append 14 ms per token vs 6.16 s cold prompt; reference decode 59.6 tok/s | — | 11/11 + 23/23 gates; merged output and draft guesses equal the uninterrupted reference; re-saved state byte-identical to a one-shot run on both ranks (216 blobs); label `experimental-two-card`, contract `v1.2+p184` (evidence `experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/v5/evidence/device-{smoke,lifecycle}-B-p184/`) |
| Flash-Next UD-IQ3_XXS, 1×B70, checkpoint engine v3 (packet181, binary `0bf0a17a…`, 2026-10-22) | same lifecycle row as packet180 | restore 0.44–0.47 s; reference load 31.83 tok/s | — | 43/43 gates; every device-written manifest carries `label: "qualified-one-card"`, `contract: "v1.2+p181"`, `qualified_by` (packet179 + packet180); packet180's `experimental` files still restore (evidence `…/packet181-session-swap-v3/one-card/evidence/device-p181-lifecycle-A-b/`) |
| Flash-Next UD-IQ3_XXS, 1×B70, checkpoint engine v2 (packet180, binary `f68714ce…`, 2026-10-22) | save at K=256, restore + append a 126-token turn, M1=128; restore-then-save, resume M2=64 | restore 0.41–0.46 s; append prefill of the 127 remaining input tokens 5.59 s vs 16.0 s cold prefill of all 469 (2.66×); reference load 31.78 tok/s | — | append output == one-shot reference [0:128]; restore-then-save chain == reference [128:192]; repeat append identical and re-saved state byte-identical (128 blobs); inspect/delete tools passed; 36/36 gates (evidence `…/packet180-session-swap-v2/one-card/evidence/device-p180-lifecycle-A-b/`) |
| Flash-Next records (approved on LocalMaxxing) | 128-token capped suites | **63.611824 (two-card, packet195 diet chain, 2026-10-23, `cmvkniuvp003gng017f0s68rn`; supersedes packet190 62.345282, packet187 60.659520 and packet136 58.798109)** · **36.602512 (one-card, packet58-onecard-cache23-chain, 2026-10-23, `cmvkcqznb002lng01fsrhjn7t`; supersedes packet182c 35.926720 and packet58as 34.573038)** | — | capped-record scope stated on the package pages; one-card lever = packet176 copy-engine-free foreground token I/O on the packet58as spin line, then a 23.05 GB admitted device expert cache (plan re-partitioned on the record run's lifetime receipts); two-card lever = V3 (full target head on rank 1 + layers 24–25 on rank 0 + static snapshot) then k3x (GDN layer 26 on the boundary + kernel token I/O + async rank-0 prepare, export on the copy engine), then the bit-identical instruction diet of the expert gate/up kernel; outputs identical |
| Flash-Next UD-IQ3_XXS, **1×B70**, 23 GB expert-cache capacity screen (packet58-onecard-cache23, binary `083e3853…`, 2026-10-23) | K1a, K1b, then one load max/max23/max/max23/max, 12×128 each | max 35.892/35.929/35.925; **max23 36.546/36.569** (+1.72 %) | — | every view 12/12 exact, drift 0.01 %; **screen win**: +1.5 GB admitted device expert cache (21.55 → 23.05 GB, device plan re-partitioned from the packet182c lifetime receipts, DRM guard unchanged) cuts fills per token 15.45 → 13.46 (−12.9 %); chain bar (+2 %) missed by 0.2 %; record chain in preparation under the idle-lanes rule; evidence `experiments/own-xpu-runtime/stage2/packet58-onecard-cache23/screen/evidence/card0-58c23-v5-a/` |
| Flash-Next one-card expert kernel, 1×B70 micro (packet58-onecard-diet-micro, 2026-10-23) | exact instruction diet of the one-card halfcache gate/up kernel vs production: cold (384 real routes + scrub) and warm, both orders, fresh production control | **p58-diet 0.78× cold (57.2 vs 73.2 µs), 0.75× warm (36.9 vs 48.9 µs)** | — | byte-identical on every claimed stratum on device; 12–16 µs saved per layer on a line where 11.4 µs is +2 %; engine integration (packet58-onecard-diet-engine) in preparation; evidence `experiments/own-xpu-runtime/stage2/packet58-onecard-diet-micro/evidence/dietmicro-B1/` |
| Flash-Next UD-IQ3_XXS, 2×B70, **exact expert instruction diet in the record engine** (packet194, binary `b8482321…`, 2026-10-23) | one load k3x / k3x+diet / k3x / k3x+diet / k3x, 12×128 + incident64 per view | k3x 62.168/62.155/62.193; **k3x+diet 63.474/63.413** (+1.96 %) | — | every view 13/13 exact, draft proposals identical, drift 0.06 %; **screen win**: packet193's bit-identical gate/up instruction diet saves 10.8–11.8 µs per layer on both ranks (hit cycle 13.54 → 13.28 ms, miss 25.58 → 25.01); chain bar (+2 %) missed by 0.04 points; record bundle (packet195) in preparation under the idle-lanes rule; evidence `experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/v5/evidence/device-row1-bracket-k3x-diet-B-p194/` |
| Flash-Next expert kernels, 1×B70 micro (packet192 + packet193, 2026-10-23) | packet192: cold / L2-warm / no-load decomposition of the record gate/up and down kernels; packet193: exact instruction-diet candidates vs production, cold and warm, both orders | packet192: gate/up 73.8 / 46.4 / 44.7 µs, down 45.9 / 33.8 / 33.3 (instruction-issue bound); packet193: **exp-diet 0.78× cold / 0.77× warm** (57.9 vs 73.9, 36.0 vs 46.8 µs), epilogue 0.82/0.85, down-diet 0.96 | — | byte-identical on every claimed stratum (384 real routes, warm, real rows); exp-diet saves 11–16 µs per layer and is being integrated into the record engine (packet194); evidence `experiments/own-xpu-runtime/stage2/packet193-expert-diet/evidence/diet-B1/` |
| Flash-Next UD-IQ3_XXS, 2×B70, per-class attribution on the record line (packet191, binary `cd199292…`, 2026-10-23) | sites-on smoke, then one load off/on/off/on/off, 12×128 + incident64 per view | off 62.198/62.166/62.184; on 58.266/58.238 (recording cost 0.937) | — | every view 13/13 exact, drift 0.05 %; **class table withheld** (completeness kill rule: host layer scopes overlap and are not comparable to device kernel sums); raw per-layer class costs (µs, both ranks): dense 154, experts 105, route+small 76, HC 68, recurrence 30, QSA attention 17–20, norms 16; no measured excess over packet110 once the ~32 µs/layer recording cost is allowed for; evidence `experiments/own-xpu-runtime/stage2/packet191-k3x-class-attribution/v5/evidence/device-row1-bracket-sites-B-p191/` |
| Flash-Next UD-IQ3_XXS, 2×B70, **k3x screen** (packet189, binary `87eec645…`, 2026-10-22) | one load, V3/k3x/V3/k3x/V3, 12×128 + incident64 per view; fresh V3 reference = packet188 row 1 | V3 60.615/60.444/60.498 (fresh 60.505); **k3x 62.242/62.225** (+2.66 % over the fastest V3 view) | — | every view 13/13 exact, draft proposals identical, drift 0.28 %; **chain rule met**; k3x = packet188's k3 + trims with the 20,480-byte handoff export back on the copy engine (export 0.053 ms vs 0.592; boundary 1.48 ms vs 2.01); hit cycle 14.06 → 13.53 ms, misses 25.77 → 25.57; no kill rule fired; record bundle (packet190) in preparation; evidence `experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/v5/evidence/device-row1-bracket-v3k-k3x-B-p189/` |
| Flash-Next UD-IQ3_XXS, 2×B70, k3 + trims screen (packet188, binary `d7765245…`, 2026-10-22) | fresh V3 control, then one load, V3/k3+trims/V3/k3+trims/V3, 12×128 + incident64 per view | fresh V3 60.505; V3 60.526/60.536/60.540; **k3+trims 60.564/60.382** (−0.26 %) | — | every view 13/13 exact, draft proposals identical, drift 0.058 %; **loss as built**: the layer-26 kernels cost 0.459 ms at the rank-0 boundary (equal to the 0.46 ms saved on rank 1) and the 20,480-byte handoff export grew 0.54 ms because packet188's kernel-I/O key sent it through a per-byte kernel instead of the copy engine; hits broke even, misses +0.38 ms; the rank-0 trims remove 0.142 ms but rank 1 binds every V3 hit; **k3 with the export on the copy engine prices +2.7 % (packet189 k3x in preparation)**; evidence `experiments/own-xpu-runtime/stage2/packet188-twocard-k3-composite/v5/evidence/device-row2-bracket-v3k-k3trims-B-p188/` |
| Flash-Next UD-IQ3_XXS, 2×B70, S1 dense-scales screen (packet183, binary `36e476d1…`, 2026-10-22) | one load, expanded/S1/expanded/S1/expanded, 12×128 + incident64 per view | controls 58.617/58.587/58.630; S1 **54.987/54.985** (−6.2 %) | — | every view 13/13 exact, identical draft proposals, drift 0.072 %; **loss, S1 and S2 closed** (reading 46 fewer scale bytes per 256 weights and recomputing the scale cost as much as packet175b's opposite change: these lanes pay per-group inner-loop work, not bytes); evidence `experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/v5/evidence/device-metadata-v5-B-p183/` |
| Flash-Next UD-IQ3_XXS, 2×B70, **V3 screen** (packet186, binary `693cc194…`, 2026-10-22) | one load, un-split/V3/un-split/V3/un-split, 12×128 + incident64 per view, plus two fresh split-head bundle-8 controls | un-split 57.83/57.80/57.84; **V3 60.57/60.53**; split-head controls 58.60/58.44 | — | every view 13/13 exact, draft proposals identical, drift 0.26 %; **+3.3 % over the record line, chain rule met**; V3 = full target head on rank 1 + layers 24–25 on rank 0 for the verified token + static snapshot; hit cycle 14.78 → 14.06 ms; record bundle (packet187) in preparation (evidence `experiments/own-xpu-runtime/stage2/packet186-twocard-v3/v5/evidence/device-row{0,1,2,3}-*-B-p186/`) |
| Flash-Next UD-IQ3_XXS, 2×B70, un-split target head measurement (packet185, 2026-10-22) | five fresh loads, split/full/split/full/split head, 12×128 + incident64 each | split 58.601/58.536/58.621; full head on rank 1 **57.737/57.756** (−1.5 %) | — | every view 13/13 exact, drift 0.145 %; measured attribution: un-split cost on rank 1 0.222 ms, decoupled rank gap 0.851 ms, rank-0 suffix-head service 0.403 ms/cycle → **V3 GO** (full head on rank 1 + layers 24–25 on rank 0, packet186 in preparation); evidence `experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/v5/evidence/device-view4-production-B-p185/` |
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
  label became `qualified-one-card` in packet181 (device-qualified the same
  day); scope one card only, TP2 checkpoints not implemented, no ctxkeeper
  adapter yet.

## Historical follow-up list

This list describes the earlier Unsloth packets. Current priorities and known
SC117 restrictions are in the October 25 review above.

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
3. **Session swap, next engine revision**: TP2 checkpoints (contract §10
   item 1) and the ctxkeeper adapter (two-card host). The label flip is done
   (packet181). The append's 5.59 s on device is the cold expert cache
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
- No ctxkeeper adapter yet: append and restore-then-save are qualified on
  device and the saved-state label is `qualified-one-card`, but ctxkeeper
  does not call the checkpoint operations; two-card checkpoints do not exist.
