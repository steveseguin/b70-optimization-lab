# Context research priorities after the checker review

**Closeout update:** the [two-call full-source screen](2026-10-07-full-source-screen-result.md)
completed at 24/24 on both documents in 27.75/34.86 seconds. Priority one is now
resolved for these short static questions: prefer complete source and stop
retrieval-interface tuning there. The [history extension](2026-10-07-history-state-study-result.md)
failed its fixed gate. The remaining priorities below are requirements for a
new application-driven study, not an automatically queued model campaign.

The practical question is when durable state improves answers or reduces total
cost enough to justify its machinery. The current historical-state study keeps
its [fixed eight trials and continuation rule](2026-10-07-history-state-study-plan.md).
These priorities do not change that experiment or admit another model run.
The [supporting CPU reviews](../data/2026-10-07-context-cpu-review/inventory.json)
preserve request sizing, completed-run retrieval costs, representation checks and
an exact 44-trial storage census. They did not inspect active history outputs.
Parent replay reproduced the full-source sizing and storage receipts exactly.

## First, establish the inexpensive baseline

The four temporal documents each contain about 1,500 source tokens. Including
all original questions, conventions and source gives a candidate prompt of about
3,300 tokens, comfortably inside both the 32,768-byte working limit and the actual
model window. A direct full-source answer is therefore the missing comparator
for the static final-answer task. Optimizing retrieval without it risks optimizing
an imposed protocol rather than the user's problem.

After resolving the registered branch, prepare a separate two-call screen on
t01-clinic and t02-theatre. Keep all source, questions, grading and the existing
medium-thinking 8,192-token answer policy; no retry, prompt tuning or truncation.
Record intermediate checkpoint quality as not applicable: a one-shot answer has
not demonstrated continuously correct state. It also sees questions with source
and has less total possible computation than the streaming methods. Report these
differences rather than calling it an isolation of the bookkeeping effect.

If direct answers are exact and much cheaper on both cases, prefer direct source
for these short static tasks and stop adding retrieval variants for that use.
If they fail, retain the failures and classify them before expanding the matrix.
Neither outcome establishes beyond-window performance. A two-call screen against
earlier runs supports descriptive costs, not a general speed claim.

## Second, state the representation's actual scope

The strongest repeated result is narrow: emitting three numeric updates avoids
re-emitting a 128-counter table. The original report task repeated exactly on a
fresh server and used about 21.6% less total elapsed time under quoted updates.
The new dispatch case failed archive checkpoint quality, despite 24/24 final
answers. It is not a second qualifying speed result. See the
[complete replication evidence](2026-10-07-sparse-state-replication-result.md).

The [semantic diagnostic](2026-10-07-context-semantic-result.md) covers aliases,
cancellations, reversals, literal-string recall and ownership joins. The maintained
table still represents numeric balances. Quote membership proves a source span
exists; it does not prove extraction is complete or its interpretation correct.
Current evidence does not establish a general factual-memory system.

Before designing a generic store, check whether ordinary status, owner,
superseded-decision and unknown/withdrawn facts from fixed existing histories can
be represented faithfully. Preserve source provenance and acknowledge uncertain
authorship. If those facts only survive through source retrieval, describe this
as a numeric bookkeeping optimization with source recall. Do not invent numeric
encodings merely to make the representation appear general.

The [representation review](../data/2026-10-07-context-cpu-review/representability-review.md)
checked existing policy histories, honestly labeled as agent-curated rather than
verified human material. String final answers are supported, but the numeric
table cannot faithfully store conditional policies or textual ownership facts.
The current grader permits null submissions yet cannot make null a correct
reference answer. A future task about genuinely unknown facts needs an explicit
new grading contract; this is not a defect in the current known-integer tasks.

## Third, measure a meaningful capacity boundary

A bounded prompt is not bounded total memory. Account separately for source
archives, event/receipt logs, full-state snapshots, process memory and GPU memory.
CPU sizing can measure disk amplification and actual token counts before another
long model run. It cannot estimate model latency from storage timings.
The [completed-run census](../data/2026-10-07-context-cpu-review/storage-census.md)
finds 15.2 MB across 44 trial directories, with model-call logs accounting for
54.2%. A final 128-counter table is about 1.9 KB while its trial evidence is about
1.3–1.4 MB. These disk measurements include intentional reproducibility overhead;
they are neither peak RAM nor a minimal production implementation estimate.

Any future capacity study must say whether it exceeds an artificial working
budget or the actual model context window, in tokenizer units with an answer
reserve. Increase relevant facts and overwritten histories rather than repeated
filler. Include a feasible below-window full-source comparison. Above the real
window, full-source is infeasible; truncating it creates a different task.
Stop scaling if independent references, output fit or a declared resource budget
cannot be maintained. More successful CPU fixtures do not themselves justify
another multi-hour model campaign.

## Cost interpretation

Across completed sparse trials, answering consumes roughly 55–94% of total
elapsed time. Retrieval-directed calls account for much of that, but about 97%
of answer completion tokens are reasoning. This is evidence about repeated model
work, not isolated HTTP or database latency. Bounded bulk fetch is a possible
later interface experiment, after the direct-source control. It must charge each
returned source batch against the existing retrieval limit and preserve complete
original text, provenance, prompt bounds and failure semantics.

The legacy 480K and million-token results remain separate from modern durable
checkpoint evidence: they use different protocols and have checker/cache limits.
Short assistant-authored and assistant-annotated diagnostics do not close that
gap or establish performance on a representative external corpus.
