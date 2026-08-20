# DFlash speculative decoding works on the B70 — Qwen3.6-27B, 2.1–4.3× over no-spec

> **Evidence: `community-reported`; not run in the reference lab.** One host, one
> config, single B70. DFlash is lossless (the target model verifies every token),
> so output quality = Qwen3.6-27B's; only speed is affected.

Pinned contributor write-up:
[`results/mtp-spec-decode-b70.md`](https://github.com/bosd/trx50-arc-b70-benchmarks/blob/master/results/mtp-spec-decode-b70.md).

## What this is

**DFlash** (z-lab, [arxiv 2602.06036](https://arxiv.org/abs/2602.06036)) is a
speculative-decoding method that drafts with a lightweight **block-diffusion**
model instead of an MTP/EAGLE head. Intel's `llm-scaler-vllm` added DFlash support
("verified with Qwen3.6-27B and Muse-Glimmer-30B"). This report pairs the target
**`Qwen/Qwen3.6-27B`** with the drafter **`QuixiAI/Qwen3.6-27B-DFlash`**
(a fork of `z-lab/Qwen3.6-27B-DFlash`, `DFlashDraftModel`, 5 layers, 3.46 GB) and
measures it on one B70.

## Reported setup

- One Arc Pro B70 (32 GB), TRX50 / Threadripper 9960X, Fedora 44, kernel 7.1.8, `xe`.
- Public `intel/llm-scaler-vllm:0.21.0-b3.1`, `ZE_AFFINITY_MASK` pinned to one B70.
- Target `Qwen/Qwen3.6-27B` **online INT4** (`--quantization sym_int4`), draft the
  QuixiAI DFlash model, enabled with
  `--speculative-config '{"method":"dflash","num_speculative_tokens":15,"model":"/draft"}'`.
- Target+drafter resident = **21.4 GiB** on the card. Single stream, temp 0.

## Reported measurements (server, same session, same prompts)

| Config | decode tok/s |
| --- | ---: |
| no-spec baseline | **28.8** |
| **+ DFlash (technical prompt)** | **60.7** (2.1×) |
| **+ DFlash (code prompt, Fibonacci)** | **~123** (4.3×) |

Cumulative draft acceptance over a run: **1497 / 5475 = 27.3%** (per-position
front-loaded: pos-0 ~0.40, tail ~0 — i.e. it lands the first 1–2 tokens reliably
and the block-diffusion tail rarely, still a net win at n=15). Output verified
coherent (correct Python, correct prose).

## Notes for reproducers

- vLLM loads the DFlash drafter via its **EAGLE** code path ("Detected EAGLE model
  … sharing target embed/lm_head") — it works, but that's the integration point;
  it is not a bespoke block-diffusion runner. Acceptance/speedup are real regardless.
- The QuixiAI/z-lab model card warns it's "still under training, engine support may
  not be fully available (causal SWA layers)" — on b3.1 it nonetheless loads and
  accelerates. Treat as experimental.
- Speedup is prompt-dependent (like all spec-decode): predictable code → higher
  acceptance → up to 4×; general prose → ~2×.
- `lmx` client-side timing undersells bursty spec-decode; trust server-side.

## Interpretation

DFlash is a **third working spec-decode path on the B70** alongside MTP — and on
Qwen3.6-27B it beats our MTP numbers for the same model (MTP-on ≈ 52 t/s; DFlash
60–123). Unlike MTP (which needs the nextn head baked into the checkpoint), DFlash
uses a **separate small drafter** you can swap, which is a nice modularity win. For
a *dense* 27B on one B70, DFlash-INT4 at 2–4× no-spec is the fastest single-card
config we've measured for this model.
