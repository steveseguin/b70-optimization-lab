# Pinned lab evidence navigator

This CPU-only tool retrieves original Markdown passages from an exact Git commit.
It makes no model requests and executes no retrieved instructions. It is useful
for building auditable evidence packs, not for declaring that an answer is complete.

```bash
mkdir -p /home/steve/lab-navigator-new
python3 tools/lab_navigator.py index --repo . --commit HEAD --out /home/steve/lab-navigator-new/index.sqlite
python3 tools/lab_navigator.py query --index /home/steve/lab-navigator-new/index.sqlite --query 'LTX packet 98 resume'
python3 tools/lab_navigator.py pack --index /home/steve/lab-navigator-new/index.sqlite --query 'durable context r4 cold cache result' --out /home/steve/lab-navigator-new/evidence.json
```

Indexes and packs require new output paths. Indexing reserves 50 GiB disk space
plus a bounded 512 MiB allowance. The first index contains 3,790 documents and
19,813 passages in 74,534,912 bytes; its source commit is
`1b9ff38fdc0918eeb2629e52f0fbf2c94ded2a1b`. Model weights, credentials,
untracked files and evaluation keys are excluded. A pinned CURRENT is a record,
not a live host check. Historical instructions and qualification claims remain
historical; the coordinator must check current policy, ownership and conflicts.

Each pack includes exact commit, blob ID, source SHA256, excerpt SHA256 and
original line numbers. Export checks source bytes against the Git blob ID.
These checks detect accidental index corruption; they are not a signature or
proof against replacement of the complete index and its identity metadata.
Original source and repository trust still matter. The index is disposable;
research source files are never rewritten or removed.

## Measured retrieval limits

The independently frozen evaluation has six development and six held-out
questions. The first ranking implementation was frozen without tuning after
development. All required spans appeared in the top eight for 4/6 questions
in each split: 7/11 development spans and 12/14 held-out spans. Held-out queries
found each required file, but two answers omitted a required passage. The
Flash-Next closeout and part of the worker comparison were development misses.
Do not infer absence of a constraint from a missing search hit. Open the full
source, refine a human query or use `--path-prefix` when completeness matters;
such follow-up is not counted in the frozen score.

[Evaluation protocol](evaluation/README.md), [configuration freeze](configuration-freeze.json)
and the `results/` artifacts preserve every returned passage and miss. This is
retrieval evidence, not a local-model memory or autonomous-worker qualification.
The other host's r4 memory confirmation remains incomplete: five completed
trials, one failed, six unstarted; no held-out result. Preserve exact source
archives alongside any summaries or structured memories.

## Next useful work

Use complete selected sources for actual coordinator questions and inspect their
citations. The subsequent [scoped worker attempt](../local-coding-worker/scoped-task-20261007/CLOSEOUT.md)
made no repair; further local-worker tuning and memory integration are parked.
LTX and Flash-Next remain parked and preserved.

## Complete sources and bounded reviews

The companion `tools/lab_evidence.py` reads original files from the indexed Git
commit and verifies the actual tree path, blob ID and bytes. This adds independent
Git binding beyond the original pack's internally consistent index checks. It
does not change search ranking or the frozen retrieval scores above.

```bash
python3 tools/lab_evidence.py read --repo . --index /home/steve/lab-navigator-new/index.sqlite --path CURRENT.md --outline
python3 tools/lab_evidence.py read --repo . --index /home/steve/lab-navigator-new/index.sqlite --path CURRENT.md --start-line 1 --end-line 100
python3 tools/lab_evidence.py review --repo . --index /home/steve/lab-navigator-new/index.sqlite --query 'full source history ownership joins' --include experiments/qwen38-27b-b70/notes/2026-10-07-full-source-screen-result.md --out /home/steve/lab-navigator-new/review.json
```

An index must match repository HEAD unless `--allow-stale` explicitly selects
historical evidence. Dirty working-tree state is recorded; reads still use
committed bytes. Rebuild into a new index path after committing new sources.
`--include` names up to 16 exact indexed documents separately from search ranks.
The default 64 KiB source budget admits whole selected documents first, in
selection order. If a document does not fit, exact matched ranges are merged and
admitted in source-line order. An oversized explicit-only document with no match
can be omitted completely; use `read` with explicit bounds to inspect it.

Every document includes an outline and exact omitted line ranges. Excerpts keep
original UTF-8 bytes, including CRLF and the final newline or its absence. An
independent 64 KiB context allowance tries complete AGENTS and AGENT_HANDOFF,
then the first 200 CURRENT lines. These are policy/status previews, not complete
authority: nested and external instructions, conflicts and live state still need
coordinator review. Budgets count excerpt bytes, not model tokens or JSON size.
Both commands separately refuse serialized output over 16 MiB, including outlines
and the final newline. They never silently truncate an outline. Exports refuse
existing paths and never execute source text.

The [practical review receipt](followup/results/practical-review.json) records a
manually selected decision review, not another evaluation or a quality score.
The complete short-source result supports closing retrieval-interface tuning for
those specific static questions. Exact historical numeric state did not prevent
incorrect ownership joins; source integrity and semantic correctness remain
separate checks. The [bounded toolchain audit](followup/toolchain-audit.json)
also preserves newly located runtime-version clues without certifying the
unrecovered strict LFM build environment.

## Project decision recall diagnostic

A separate [twelve-question application check](../project-decision-recall-20261007/RESULTS.md)
used five complete historical project records. Ordinary search/read answered all
twelve completely; a separately paged full-source attempt omitted one required
qualification despite citing the correct passage. The first full-source attempt
also exposed tool-display truncation and is preserved as a failed attempt.
This supports explicit completeness review and checking actual displayed ranges,
not new memory machinery or a local-model qualification. The
[reviewed decision brief](../project-decision-recall-20261007/DECISIONS.md)
provides the snapshot's answers with exact source links. These hosted assistant
attempts do not change this navigator's frozen retrieval scores.
