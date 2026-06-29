# 2026-06-29 in-graph late-bonus verifier audit

Purpose: decide whether to spend GPU/build time on a replacement for the
existing `LLAMA_SPEC_VERIFY_LATE_HEAD_BONUS` path.

## Context

The current promoted record path already uses same-graph verifier sampled IDs:
the target verifier emits rows for `[sampled, draft0, draft1, draft2]`, then
`LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1` consumes the compact sampled-ID buffer.
This keeps the bonus-token pipeline intact and avoids full logits transfer.

The old `LLAMA_SPEC_VERIFY_LATE_HEAD_BONUS=1` experiment marked the final draft
token as non-output, verified only draft rows first, and ran a separate
head-only graph for the bonus token only after full draft match. It was correct
but slower, because the second graph/scheduler/copy/sync cost outweighed the
saved verifier output row.

## Audit Result

A same-graph side channel is technically possible but is not a high-confidence
next record lane as-is.

Findings:

- `res->t_h_nextn` is created before `inp_out_ids` output filtering, so the
  hidden state for a non-output final draft row exists in the verifier graph.
- Existing sampled-ID exposure is output-row based:
  `llama_batch_allocr` counts only `batch.logits/output` rows, `out_ids` maps
  only those rows, and `llama_get_sampled_token_ith()` resolves through
  `output_ids`.
- A non-output final draft row therefore cannot be retrieved through the normal
  sampled-token accessor.
- A safe implementation would need an explicit extra sampled-ID side channel:
  reserve one extra `sampling.sampled` slot, build an argmax for the final
  hidden row, copy it to that extra slot, and add a narrow accessor consumed
  only after full draft match.

## Decision

Do **not** implement this as the next Gemma record attempt unless a design also
avoids computing the bonus LM-head row on non-full-match steps.

Reason: a same-graph side channel cannot know whether the draft fully matched
until after sampled IDs are read. If it computes the bonus sampled ID
unconditionally, it effectively reintroduces the fourth LM-head row that the
current record path already computes, just through a more complex side channel.
The existing separate late-head graph proved that avoiding the row only after
full match is semantically correct, but its second-graph overhead loses.

The useful future idea is conditional/row-adaptive verification that preserves
the current bonus pipeline while avoiding unnecessary verifier rows. That is a
deeper scheduler/graph design, not a small sampled-ID plumbing patch.

## Source Snapshot

Before this audit, the active dirty llama.cpp stack was preserved:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260629-ingraph-bonus-preedit.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260629-ingraph-bonus-preedit.diffstat`
