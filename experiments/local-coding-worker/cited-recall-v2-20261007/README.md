# Cited recall protocol v2: references in, exact quotes out

This offline compiler removes the need for a model to reproduce source
whitespace. It does not retrieve documents, repair incomplete answers, assess
meaning, call a model, or perform external actions. There is no new recall
quality result. The original ten-question trial and its failed answer remain
unchanged: **do not rerun, repair, or regrade that trial through this compiler.**

Before any future qualification, create and independently review **fresh
questions** and a frozen source bundle. Preregister the model, prompt, output
budget, deadline, completeness gate and semantic rubric before inference. The
synthetic fixtures in the tests are implementation controls, not unseen
evaluation questions. A future harness must isolate its answer key and keep
source selection under trusted caller control; this directory does not build
that harness or establish contamination-free evaluation.

The trusted source bundle is UTF-8 JSON with exactly these fields:

```json
{
  "schema": "lab.cited-recall.sources.v2",
  "questions": [{"id": "NEW_01", "prompt": "What count was approved?"}],
  "corpus": {"DOC_A": "Approved count: 17.\n"}
}
```

Give the model the frozen questions and corpus with one-based line numbers.
Require one concise answer per question, in the supplied order; normally one
or two sentences. The model must return only JSON in this shape, without
Markdown fences or quoted source text:

```json
{
  "answers": [{
    "question_id": "NEW_01",
    "answer": "The approved count is 17.",
    "citations": [{"doc_id": "DOC_A", "start_line": 1, "end_line": 1}]
  }]
}
```

`compile_references(raw_refs, expected_question_ids, corpus)` is a pure
function. It requires complete, unique, ordered answers; nonempty answer
text and citation lists; known document IDs; and integer, non-boolean,
inclusive line ranges from 1 through the document's line count, at most
20 lines each. Unknown fields and model-supplied `quote` fields are refused,
even when a quote happens to match. Nothing is reordered, trimmed, filled
in, or silently repaired. IDs are dictionary keys, never paths or URLs.

The compiler copies lines into each citation's `quote`. Line semantics match
the original citation validator: Python `str.splitlines()`, then LF joining.
Blank lines, indentation, tabs and Unicode within lines are preserved. Input
line-ending bytes remain preserved in the raw source-bundle copy; quotes
normalize line separators according to that existing validator's convention.

```bash
python3 -B experiments/local-coding-worker/cited-recall-v2-20261007/compile_citations.py \
  --source-bundle /trusted/fresh-source-bundle.json \
  --raw-refs /trusted/untouched-model-output.json \
  --out /trusted/new-compilation-directory
```

Only the caller supplies filesystem paths. The output parent must exist and
the output directory must be new. Successful output contains byte-identical
`raw-refs.json` and `source-bundle.json`, `compiled.json`, and `receipt.json`.
The receipt binds raw input bytes, full questions, corpus, compiler source
and compiled output by SHA-256. Duplicate JSON keys, non-finite constants and
invalid UTF-8 are refused. Invalid inputs create no output directory. Existing
outputs are never overwritten; a directory left by an I/O error is retained
for inspection and cannot be reused. These ordinary file writes do not claim
crash durability or replace an independently verified backup.

**Exact quotes do not prove that an answer is true or that a citation supports
it.** Semantic support, relevance, contradictions, missing qualifications and
appropriate uncertainty require human or independent review against a fresh
rubric. Receipts explicitly report no semantic grade or model-quality result.

Run `python3 -B experiments/local-coding-worker/cited-recall-v2-20261007/test_compile_citations.py -v`.
Controls use fresh synthetic documents, including blank lines, indentation
and Unicode. They call the unchanged original validator's `check_responses`
function with synthetic questions only. Both a correctly supported fixture
and a deliberately false claim pass those mechanical checks, demonstrating
the semantic boundary. No original corpus, questions or observed answers are
processed by the tests.
