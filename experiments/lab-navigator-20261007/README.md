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

Use packs for actual coordinator questions and inspect their citations. Keep
one task and explicit source files for a local coding worker, with independent
patch acceptance. Defer another broad model-memory campaign until a practical
workflow has proved useful. LTX and Flash-Next remain parked and preserved.
