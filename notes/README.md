# Notes

This folder is the chronological lab notebook. Prefer adding a new dated note
or a dated addendum over editing old conclusions in place.

## Current Qwen Entry Points

- [2026-06-20-master-plan.md](2026-06-20-master-plan.md): current baseline-first
  plan for Qwen3.6-35B on 4x B70.
- [2026-06-16-qwen36-current-handoff.md](2026-06-16-qwen36-current-handoff.md):
  detailed handoff with accepted, rejected, and interrupted work.
- [2026-06-21-qwen36-phase3-copy-skip.md](2026-06-21-qwen36-phase3-copy-skip.md):
  metadata-copy and GPU-side counter shortcuts, both rejected for now.
- [2026-06-20-research-plan-replayssm-and-speed.md](2026-06-20-research-plan-replayssm-and-speed.md):
  ReplaySSM/spec-decode plan and caveats.
- `codex-brief-*.md`: short task briefs for delegation. Keep these brief and
  operational.

## Writing Rules

- Record the full benchmark identity before interpreting speed.
- Link every patch or code change to its result summary, even if the result is
  negative.
- Keep failed ideas visible unless a later note clearly supersedes them.
- Put exact paths to important `data/` summaries and `patches/` artifacts in
  the note.
- Separate observations from decisions. A failed quality gate can still be a
  useful result.

## Promotion Path

1. Capture the run output in `data/`.
2. Write or update a note here with the result, identity, and decision.
3. Save the patch in `patches/` if code changed.
4. Promote only verified wins into `results/`, `repro/`, or production docs.
