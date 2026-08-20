# DFlash speculative decoding works on the B70 — Qwen3.6-27B, 2.1–4.3× over no-spec

> **Evidence: `community-reported`; not run in the reference lab.** One host, one
> config, single B70. The contribution and its cited source snapshot do not
> include raw server logs, response payloads, token IDs, or a fixed-suite result.
> Target verification is a property of the decoding design; it is not an
> artifact-backed claim here that this run was token-exact or quality-equivalent.

Pinned contributor write-up:
[`results/mtp-spec-decode-b70.md`](https://github.com/bosd/trx50-arc-b70-benchmarks/blob/fda0d86c47ff02d8e36f813a8e0121a2152d4478/results/mtp-spec-decode-b70.md).

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

## Reported measurements (server, same session)

| Config | decode tok/s |
| --- | ---: |
| no-spec baseline | **28.8** |
| **+ DFlash (technical prompt)** | **60.7** (2.1×) |
| **+ DFlash (code prompt, Fibonacci)** | **~123** (4.3×) |

Cumulative draft acceptance over a reported run: **1497 / 5475 = 27.3%** (per-position
front-loaded: pos-0 ~0.40, tail ~0 — i.e. it lands the first 1–2 tokens reliably
and the block-diffusion tail rarely, still a net win at n=15). Output verified
coherent by the contributor (correct Python, correct prose); no response artifact
was supplied for independent checking.

## Notes for reproducers

- vLLM loads the DFlash drafter via its **EAGLE** code path ("Detected EAGLE model
  … sharing target embed/lm_head") — it works, but that's the integration point;
  it is not a bespoke block-diffusion runner. Acceptance/speedup are real regardless.
- The QuixiAI/z-lab model card warns it's "still under training, engine support may
  not be fully available (causal SWA layers)" — on b3.1 it nonetheless loads and
  accelerates. Treat as experimental.
- Speedup is prompt-dependent (like all spec-decode): the reported Fibonacci
  prompt reached ~4.3× and the reported technical prompt ~2.1×. These are
  prompt-selected observations, not a fixed-suite distribution.
- `lmx` client-side timing undersells bursty spec-decode; trust server-side.

## Maintainer control

The reference lab later tested the same public z-lab Qwen3.6 DFlash family on
the strict fresh Qwen suite. The original integration peaked at **49.994 tok/s**
and lost the device at k=15. A PR40898-style mixed sliding/full-attention repair
made the path functional but still peaked at **54.836 tok/s** at k=4, versus the
then-current **68.236 tok/s** Qwen3.6 record. Those controls used a different
runtime/checkpoint identity, so they do not disprove the contributor's numbers;
they do show that the 60.7/~123 rows are not portable B70 expectations.

Evidence:
[original local screen](../../../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-dflash-drafter-no-win.md)
and
[repaired local screen](../../../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-06-dflash-swa-pr40898-repair-no-record.md).

## Interpretation

The report is useful evidence that DFlash can execute and accelerate Qwen3.6-27B
on a single B70. Unlike MTP (which needs the nextn head baked into the checkpoint),
DFlash uses a **separate small drafter**. The reported 60.7/~123 tok/s rows should
remain contributor observations, not a project record or a direct baseline for
another checkpoint, runtime, prompt suite, or the current Qwen3.8 TP2 lane.
