# Gemma 4 26B Q8: Tail-only direct-confidence producer screen (negative)

Date: 2026-07-02

## Purpose

Test whether the MTP draft direct-argmax score path can be made useful by
computing top2 score payloads only for later draft positions. Prior
`LLAMA_MTP_DRAFT_DIRECT_ARGMAX_SCORES=1` / logit-gap tests paid top2 overhead
for every unrolled draft step. The new source patch keeps the existing fixed
4-slot sampled-token stride by padding early ID-only rows, then emits top2 rows
only at/after `LLAMA_MTP_DRAFT_LOGIT_GAP_MIN_START_POS`.

This is still a fresh-response / cold-suite experiment: no prompt cache, no KV
reuse, no repeated-output history claim. Speculative tokens remain verified by
the Q8 target model.

## Source snapshot

- Before this experiment:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-pre-next-verifier-source.patch`
- Tested patch:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-tail-only-direct-confidence-source.patch`
- Diffstat:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-tail-only-direct-confidence-source.diffstat`

Patch summary:

- `src/models/gemma4-assistant.cpp`: added
  `LLAMA_MTP_DRAFT_LOGIT_GAP_MIN_START_POS` awareness in the fused MTP draft
  direct-argmax producer; early unroll positions can emit ID-only argmax and be
  padded to the score-mode row shape, while later positions emit top2 IDs/logits.
- `ggml/src/ggml-sycl/pad.cpp`: generalized SYCL pad from F32-only to F32/I32 so
  int sampled-token rows can be padded on device.
- Build target: `build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server`.
- Build result: passed. The UI npm engine warning was non-fatal; SYCL AOT and
  final `llama-server` link succeeded.

## Screen command shape

Four one-GPU lanes were run concurrently with the current Gemma record recipe:
UD-Q8_K_XL target/verifier, Q4_0 MTP draft, FA-on, 32K context, VMM enabled,
`n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH=1024`, fixed realistic prompt
suite, `MAX_TOKENS=128`, `CANARY_REPEATS=16`, `REALISTIC_GATE=1`.

Labels:

- control: `gemma4-q8-gpu0-tailconf-control-strict128-20260702T025330Z`
- old all-step score path: `gemma4-q8-gpu1-tailconf-scoreall-gap0-strict128-20260702T025330Z`
- new tail-only score path, no gap filtering: `gemma4-q8-gpu2-tailconf-tail3-gap0-strict128-20260702T025330Z`
- new tail-only score path, gap filter: `gemma4-q8-gpu3-tailconf-tail3-gap050-strict128-20260702T025330Z`

Note: this screen ran before the harness was updated to capture
`LLAMA_MTP_DRAFT_LOGIT_GAP_MIN_START_POS` in `launcher_identity`, so the labels
and this ledger's lane definitions are the source of truth for the start position. The harness fix
is included with this experiment record.

## Results

All lanes passed the realistic final gate and had `cached_tokens=0` for every
request. No lane is a LocalMaxxing candidate because none beat the current
`124.97714084813418 tok/s` record and the best candidate did not beat the
same-window control.

| lane | gate | cached | median tok/s 1-100 | p10 | mean | full median | TTFT ms |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| control | pass | zero | 120.49223560283977 | 108.57983808176438 | 119.17242150904775 | 116.8653962737558 | 179.59842894924805 |
| all-step score, gap=0, start=1 | pass | zero | 116.8013887203036 | 107.4443126885242 | 117.68843887118629 | 116.25781640250761 | 179.53148850938305 |
| tail score, gap=0, start=3 | pass | zero | 118.4709837563259 | 103.80896546508197 | 117.25518358744229 | 118.06917186648833 | 178.72784700011835 |
| tail score, gap=0.50, start=3 | pass | zero | 117.52940584638576 | 104.33404484318791 | 117.15958246709043 | 117.59299931042318 | 178.4581090323627 |

## Interpretation

The implementation works mechanically: score-mode sampled-token rows can be
mixed with padded ID-only rows without breaking the cold-suite gate. It also
recovers part of the old all-step top2 overhead (`116.80 -> 118.47` median in
this same-window screen).

It does not produce a performance win. The no-score control remains faster
(`120.49` median in the same screen), and the real gap filter lane is slower
than both the control and the no-filter tail-score lane. This matches the prior
conclusion that simple MTP draft confidence filtering is not the next record
lever for this recipe.

## Decision

Closed negative / infrastructure only.

- Do not promote or submit.
- Preserve the patch snapshot for future confidence-gating work.
- Keep the harness reproducibility fix for `LLAMA_MTP_DRAFT_LOGIT_GAP_MIN_START_POS`.
- Prefer deeper verifier-cost work next: reduce verifier row/output work or the
  backend sampled-output extraction boundary, rather than adding draft-side
  confidence filters.
