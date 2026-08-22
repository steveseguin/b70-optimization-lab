# neural.download packet standard (v1, 2026-08-22)

Purpose: every model on the neural.download page ships as a **packet** —
benchmarks, any required patches, and a reproducible recipe — so users get
wide variety with honest, measured expectations. Packets inherit the lab's
evidence standards; nothing on the page is a guess.

## Packet contents (one directory per entry, `repro/neural-download/<slug>/`)

1. **Identity** (`README.md` header + `manifest.sha256`)
   - Model family, size, quant(s); exact GGUF file name(s), byte size,
     SHA-256, source repo, pinned revision.
   - Packet base: pinned upstream `llama.cpp` commit, exact cmake configure
     line, toolchain (oneAPI version), target device (Intel Arc Pro B70,
     bmg-g31 AOT).
   - Companion files where applicable (vision mmproj, MTP/draft heads),
     each pinned and hashed.

2. **Recipe**
   - Exact server command(s): context size, KV cache type, flash
     attention, batch/ubatch, device selection. Copy-paste runnable.
   - Measured VRAM footprint at each published operating point.
   - Up to three operating points per model: **max-context**, **balanced**,
     **speed** — each with its own measured numbers. Never publish an
     operating point that was not actually loaded and measured on a B70.

3. **Benchmarks** (data JSON + summary table in README)
   - Decode: conventional 99-interval median tok/s on the 12-prompt
     realistic suite, cold server, `cached_tokens=0` verified per request;
     two fresh-server runs, both numbers published (band, not cherry-pick).
   - TTFT and prefill rate at a standard 512-token prompt.
   - For MoE models, note active-parameter count next to the rate so users
     understand why a 30B-A3B outruns a dense 27B.

4. **Quality and expectations**
   - Repeat determinism (8x same-prompt hash stability), arithmetic, copy,
     JSON-schema canaries; long-context needle at a depth appropriate to
     the published max-context point.
   - New families get **self-consistency + sanity canaries**, not oracle
     equality claims (there is no cross-model oracle). The README states
     explicitly what was and was not tested.
   - Known limitations verbatim (e.g. context ceilings by KV budget,
     quality class of the quant).

5. **Patches**
   - Default is stock pinned upstream. Any patch needed for bring-up or a
     material speed win lives in `patches/` with SHA-256s, applies cleanly
     to the pinned commit, and is a candidate for upstreaming. Packets say
     whether their numbers are stock or patched.

## Integrity rules (inherited from the lab standard)

- Every input pinned by SHA-256; model files sealed 0444 after verification
  with a `DOWNLOAD-MANIFEST.txt` in the model directory.
- Rates are conventional-median only; no legacy-inclusive accounting on the
  page. Failed runs are not silently rerun; bands reflect what happened.
- No packet publishes speculation-assisted rates as the headline unless the
  packet IS a speculation package (then both target-only and assisted rates
  appear, labeled).

## First wave (2026-08-22) and the question each packet answers

| Slug | Model | Lane | Question |
|---|---|---|---|
| `lfm2.5-2.6b` | LFM2.5 2.6B Q8_0 | novice | smallest honest single-command B70 recipe |
| `ornith-1.5-9b` | Ornith 1.5 9B Q8_0 | beginner-plus | recent one-card model; beginner package candidate |
| `nemotron-3.5-lightning-30b-a3b` | UD-Q4_K_M | mid MoE | does the family run on Intel without NVIDIA's NVFP4 runtime |
| `ornith-1.5-35b-a3b` | Q4_K_M | enthusiast MoE | validate the family + an outside one-B70 performance claim independently |
| `qwen3.8-27b-256k` | UD-Q4_K_XL vs UD-Q5_K_S fit-off + mmproj + MTP draft | flagship | highest quant that truly serves ~256K + vision + draft on one B70 |

Architecture notes established at intake: Ornith 1.5 = `qwen35moe`
(256 experts / 8 used, 41 layers, GQA 16/2, 262144 native) — supported by
today's upstream. Nemotron 3.5 Lightning and LFM2.5 arch strings to be read
from their GGUF headers at verification.
