# SC117 QSA attention at long context — closeout (2026-10-25)

<!-- campaign-closeout -->

## Question and identity

At 3,000 tokens of context, the SC117 service decoded at 36.4 tok/s against 46.9 at suite lengths. The question was
which exact changes recover long-context decode.
- Model and engine: SC117 Qwen3.8 Flash-Next IQ3_S on our own engine, F32 exact mode, two B70 cards (23:00.0 rank 0,
  47:00.0 rank 1).
- Engines: `15e894805502` through `b15e3468c587`.
- Workload: one summary request over a 3,027-token prompt, profiled on rank 0 with `OWNRT_DECODE_PROFILE=3`. That mode
  gives per-pass device times; request profiles land under `req-N/rank0/`.

## Outcome

Accepted (exact):
- **Parallel attention admit.** One 256-lane work-group per row replaces a single work item scanning up to 2,051
  selected slots. Rank 0: 998 → 18 µs per step at 3K.
- **QSA select with one subgroup per block item.** Rank 0: 945 → 371 µs per step at 3K.
- Together:
  - 3K-context decode 36.4 → 45.4 tok/s, and 1K 41.2 → 48.6;
  - prompt reading 45.7 → 34.3 s at 3K and 17.4 → 11.2 s at 1K;
  - suite outputs byte-identical, F32 oracle zero differences, prefill gate 13/13.

Rejected, all exact but slower. The tiles pass itself stays at about 914 µs per step at 3K:
- one work-group per KV head looping its 12 query heads: 2,913 µs;
- staged slot ids and 8 K rows requested before scoring: 1,079 µs;
- 256-lane work-groups (8 subgroups, one dimension per lane): 1,597 µs.

## What worked

A per-pass profile before any rewrite. The attention site is three launches (admit, tiles, combine). The first
rewrite, grouped heads, aimed at the tiles pass by assumption, while the per-pass split showed admit was the cost. Both
accepted fixes replace a serial per-item scan with a parallel scan or reduction whose result does not depend on order:
a minimum, an any-of, and an integer sum.

## What failed or remains uncertain

- The tiles pass is latency-bound per work-group, and every restructure that lengthened per-work-group chains or raised
  register use lost.
- Not tried:
  - a multi-row attention kernel for batched prefill (prefill replays attention per row: 52 ms per 32-row chunk on
    rank 1 at 3K);
  - a flash-decoding layout with K/V tiles in local memory shared across the 12 query heads of a KV group.

## Evidence and patches

- [p49_qsa_kernel.hpp](../../engine/src/stage2/packet194-expert-diet-engine/p49_qsa_kernel.hpp): `admit_fast`, and the
  opt-in tile variants with their measured results in comments.
- [specialised_submit.cpp](../../engine/src/stage2/packet194-expert-diet-engine/specialised_submit.cpp): `select_rows`.
- Profiles: [15e89480-ctx3k](b-prefill/profiles/15e89480-ctx3k-decode-device-rank0.jsonl) (before) and
  [7c353573-ctx3k](b-prefill/profiles/7c353573-ctx3k-decode-device-rank0.jsonl).
- Results table: [../../research/2026-10-25-decode-roofline.md](../../research/2026-10-25-decode-roofline.md).
- Closed arms: [DO-NOT-REPEAT.md](DO-NOT-REPEAT.md).

## When to revisit

- The tiles pass becomes the largest long-context cost after other work; at 3K it is about 6% of rank 0's busy time.
- A local-memory K/V tile design that keeps one work-group per (head, tile) and its current parallelism.
- Batched prefill of long prompts becomes the priority: a native multi-row attention kernel.
