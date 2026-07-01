# 2026-07-01 - Top2 logging reopen preedit snapshot

Status: abandoned before source edits.

Why this exists:

- The prior verifier top2/margin diagnostic did not produce usable top2 rows.
- A preedit snapshot was taken before attempting a narrow logging-only reopen.
- A subagent review then identified a better next lane: direct sampled-ID egress
  for the normal full-bonus verifier path. That lane targets measured sampled
  extraction overhead while keeping acceptance semantics unchanged.

Artifacts:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-top2-logging-reopen-preedit-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-top2-logging-reopen-preedit-source.diffstat`

Decision:

- Do not pursue this top2 logging reopen now.
- Preserve the snapshot so the active workspace has no stale untracked work and
  future agents can see why this branch was skipped.
- Next experiment should use the active source checkout directly and preserve a
  new preedit snapshot under a direct-egress label.
