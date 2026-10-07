# Project decision recall results

Ordinary search and source reading answered all twelve project questions with
all 38 required criteria. The separate complete-source delivery check answered
eleven fully: one answer omitted a required qualification that was present in
its own citation. This small screen supports using original sources with an
explicit completeness review. It does not establish a need for structured memory.

The [readable decision brief](DECISIONS.md) preserves the successful search
answers and links their exact historical sources. These are answers about a
frozen record, not instructions to operate a host or a claim about its current
state. The [original packet](README.md) describes the frozen input subset;
subsequent outcomes are recorded here separately.

## Outcomes

| Attempt | Complete questions | Essential criteria | Delivery and format |
| --- | --- | --- | --- |
| Original complete-source attempt | Unscored | Unscored | Tool display truncated; first submission also had an extra top-level JSON field and failed the required format |
| Ordinary search and read | 12/12 | 38 complete | Exact, relevant citations; answerer reported recovering truncated output with smaller reads |
| Separate paged complete-source check | 11/12 | 37 complete, 1 partial | All 19 pages reported visibly received; exact, relevant citations |

The failed first attempt is preserved, not replaced by the supplementary row.
The [transport plan](transport-plan.json) was recorded after the display failure,
before the parent inspected either first submission or score. It changed source
delivery only: the same five complete documents, twelve questions and 38
reference criteria were delivered in fixed order, with no selected excerpts or
answer-based tuning. Each of the 725 original lines was emitted exactly once.
No submission was repaired or retried after grading.

The original full response requested 50,000-token allowances but the interface
still reported truncation. Reader-side logs contained complete text, which is
not proof of complete model-visible delivery. The supplementary pages were at
most 5,489 serialized bytes. Their completeness is supported by exact replay and
the answerer's visibility report; an independently captured rendered transcript
is unavailable. Search also encountered truncation and reported recovery through
smaller reads. All source lines occur in its reader log, and its later split
reads cover the affected policy ranges. Keep emitted coverage distinct from
verified perception. [Visibility receipt](results/visibility.json).

## What failed in the answer

Question eight asks whether two differently scoped timing observations establish
a general speed conclusion. The paged answer correctly explained the different
settings, the single legacy pair, missing repeat confirmation, and the incomplete
r4 matrix. It omitted the separate warning that a correct final answer does not
establish correctness of every intermediate state. “Legacy-checker limitations”
was too vague to supply that required qualification. The exact quotation
contained it, but a quotation does not substitute for the answer's explanation.

The [frozen reference](reference.json) explicitly required that distinction before
any model response. This is an answer-completeness failure with evidence present,
not a lost source or an incorrect numeric store. Both answerers correctly used
JSON null for the two facts absent from the supplied corpus; null is a legitimate
reference value here, not a fabricated zero or an automatic wrong answer.

The independent reviews preserve each criterion, relevant citations, temporal
scope, unsupported-claim checks and exact excerpts from the answers:
[search](results/search/semantic-review.json) and
[paged complete source](results/full-paged/semantic-review.json).

## Observed cost and its limits

| Attempt | Reader operations including submit | Serialized response bytes | First reader response to submission |
| --- | ---: | ---: | ---: |
| Original complete source | 3 | 99,939 | 233.09 s |
| Search and read | 14 | 205,301 | 171.49 s |
| Paged complete source | 21 | 104,149 | 239.49 s |

These are reader operations, not model request counts. They include catalog and
submission receipts; repeated source text, line numbers and JSON add bytes.
The source corpus itself is 44,400 bytes. Search ultimately opened the entire
corpus, so its pass is not evidence of sparse retrieval efficiency. Its repeated
reads also make the returned text larger than the full-source payload.

Observed intervals include assistant/tool scheduling and exclude initial task
setup. The first two sessions ran concurrently; the supplementary session used
a different delivery interface. These times are not a controlled speed comparison.
Exact model snapshot, model input/output/reasoning tokens, cache reuse, monetary
cost and peak process memory are unavailable and remain null. No local model
server was started and no GPU settings were changed. The [resource census](resources.json)
separates source, records and implementation bytes; audit duplication is not a
minimal production-storage estimate.

## Practical workflow

1. Fix the question's date, project and decision scope. Use live authority and
   live checks for actual operations; a historical note alone cannot authorize them.
2. Start with original short sources. Use the existing
   [lab evidence reader](../lab-navigator-20261007/README.md#complete-sources-and-bounded-reviews)
   to open complete selected files or explicit ranges. Verify that the tool
   actually displayed them; source-byte limits do not guarantee display fit.
3. State the decision, applicable configuration, conditions, exceptions and
   evidence limits in the answer itself. For an unknown, state what the supplied
   corpus does not establish instead of guessing.
4. Check both citation validity and substantive completeness. A real, relevant
   quote can accompany an incomplete answer. Keep these checks separate.

Use the reviewed decision brief for this snapshot. Keep the existing source
navigator as the practical access path; the small readers in this experiment
are frozen evaluation apparatus, not a second production search framework.
No structured fact store, worker integration, additional seed matrix or local
model tuning follows from this result. A future memory experiment needs a real
retained-state or scale requirement that source access fails to meet, with a new
fixed task and independently checked references.

## Reproduction and provenance

The input freeze is commit `2426d0eb067ef3c8e7dd21eab9b311dcb02159fc`.
[freeze.json](freeze.json) binds all original source, question, reference, prompt,
review and reader files. The five documents are complete Git blobs at cutoff
`a96a072efa4a6611d79ef323bef507da42607885`, totaling 725 lines. They are
pre-existing agent-curated records with claimed owner input, not authenticated
human transcripts. New questions and grading are also assistant-produced;
reference review was independent of authorship, and the parent separately checked
the missing criterion. This is a selected development diagnostic, not a random
sample or a held-out benchmark.

Answerers used fresh hosted assistant sessions without inherited conversation.
Blinding was instruction-based on a shared filesystem, not an enforced security
sandbox. No local Qwen quality, autonomous worker readiness, generic memory
advantage, or beyond-window performance is established.

Run from the repository root:

```bash
python3 experiments/project-decision-recall-20261007/test_evidence.py
python3 experiments/project-decision-recall-20261007/audit.py --results
python3 experiments/project-decision-recall-20261007/audit_paged.py
```

All 25 reader/audit CPU tests passed; the separate page delivery passed seven
CPU controls. Both existing source-reader suites passed their 28 tests, and CI
now includes the decision reader tests. [Preservation](preservation.json) records
restored replay and binding checks. These commands replay stored evidence and
mechanical validity; they do not rerun model answers or automatically certify
semantic correctness. The [inventory](inventory.json) binds the preserved files.
