# Temporal development reference review

The four frozen source documents now have an agreed reference key. Two assistant
annotators separately read the raw text without an author's answer key or one
another's annotations. Their 201 posted events, 48 closing tables, 96 answers,
quote spans and answer-basis records agree exactly. No adjudication edit was
needed. The parent reviewed the narrative conventions, cancelled requests,
posted reversals, replacement balances and historical ownership interpretation.

The [adjudicated key](adjudicated.json) binds the exact source and both annotation
files by SHA-256. It reuses the existing semantic compiler's adjudication schema
as a compatibility interface. This is a separate temporal development packet;
it is not part of the older semantic experiment. All four documents compile and
pass that compiler's consistency checks. Those checks alone do not prove that
an annotation correctly interprets prose.

The separate [source replay](verify_references.py) reads explicit posting,
ownership and review-link lines, resolves the question targets, and compares
the full results against both annotations. Run it with:

```sh
python3 experiments/qwen38-27b-b70/data/2026-10-07-temporal-development/verify_references.py
```

Its [saved receipt](reference-check.json) confirms zero disagreements. All 16
historical/ownership answers in each document differ from the corresponding
counter's final balance. The questions span nine earlier closing batches per
document. This stronger temporal contrast was designed before model execution;
it is not evidence of general task representativeness.

The source author's separate [recalculation and interpretation review](parent-review-support.json)
agrees with both annotations. It is not a third blind annotation. It also records
two coverage limits: only 5 of 32 ownership joins require an owner different from
the final owner, and the theatre document repeats one counter/time target across
two questions. There are 63 distinct historical counter/time targets among 64
historical questions. Thirteen joins exercise a transfer effective in the requested
batch. No source or question was retuned after these checks.

These remain short, assistant-authored and assistant-annotated diagnostics with
a common controlled posting grammar. There is no independent human annotation,
external corpus, held-out evaluation or long-context result. Reference agreement
does not establish model quality. No live study is admitted by this packet;
execution requires a separate prospective plan, frozen wrapper, CPU checks and
the usual host admission. The original [authoring note](authoring-note.md)
preserves the source-delivery state before annotation.
