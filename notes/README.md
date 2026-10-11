# Notes

This folder is the chronological lab notebook. Prefer adding a new dated note
or a dated addendum over editing old conclusions in place.

For the latest conclusions, start with the
[model effort index](../docs/model-effort-index.md),
[result packets](../results/README.md), and
[research workflow lessons](../docs/research-workflow-playbook.md).
The dated notes below retain their original experiment context. A historical
handoff or service command does not describe what is running now;
[CURRENT.md](../CURRENT.md) owns recorded host state.

## Gemma Entry Points

- [../results/gemma4-26b-a4b-q8-b70/HANDOFF.md](../results/gemma4-26b-a4b-q8-b70/HANDOFF.md):
  pause/resume bookmark, production backend recipe, smoke commands, and the
  remaining useful optimization work.
- [../results/gemma4-26b-a4b-q8-b70/production-service.md](../results/gemma4-26b-a4b-q8-b70/production-service.md):
  persistent llama.cpp backend operation for Gemma 4 26B Q8.
- [../results/gemma4-26b-a4b-q8-b70/README.md](../results/gemma4-26b-a4b-q8-b70/README.md):
  Gemma 4 26B A4B Q8 result packet, current strict record, service lane, and
  archived invalid/diagnostic paths.
- [../results/gemma4-26b-a4b-q8-b70/research-plan.md](../results/gemma4-26b-a4b-q8-b70/research-plan.md):
  experiment queue, exhausted neighborhoods, and next patch targets.
- [../experiments/gemma4-26b-a4b-q8-b70/sweeps/](../experiments/gemma4-26b-a4b-q8-b70/sweeps/):
  chronological sweep notes for valid wins, losses, and failed source patches.
- [2026-07-02-gemma-125-rerun-variance-diagnostic.md](2026-07-02-gemma-125-rerun-variance-diagnostic.md):
  why the exact 125 tok/s Gemma repro reran at about 120 tok/s; records the
  identity diff, per-prompt movement, and duplicate-prompt nondeterminism
  diagnostic. The duplicate-prompt data is diagnostic-only, not promotable.

## Qwen Entry Points

- [2026-06-20-master-plan.md](2026-06-20-master-plan.md): historical baseline-first
  plan for Qwen3.6-35B on 4x B70; use the
  [result packet](../results/qwen36-35b-quark-int8-b70/README.md) for its later outcomes.
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
- When an investigation ends, put its conclusion, limits and source links in
  the lane handoff or negative-result ledger. Add reusable lessons to the
  workflow playbook; keep the raw history available through those links.

## Promotion Path

1. Capture the run output in `data/`.
2. Write or update a note here with the result, identity, and decision.
3. Save the patch in `patches/` if code changed.
4. Promote only verified wins into `results/`, `repro/`, or production docs.
