# Authored semantic development packet

Date: 2026-10-07. Original scope: document authoring only. The authoring
requirements below preceded independent annotation and adapter implementation.
R4 subsequently closed with its recorded failure; its evidence remains unchanged.

Follow-up: two separate assistant annotations now agree on all 84 answers and
48 states. Six valid alias quote-span differences are preserved in the
[adjudicated reference](../data/2026-10-07-context-semantic-development/adjudicated.json).
The [separate prospective live plan](2026-10-07-context-semantic-live-plan.md)
defines a new development diagnostic; this packet does not enter frozen r4.

The [document packet](../data/2026-10-07-context-semantic-development/documents.json)
contains six manually specified cases, each with a stress version and a
plain-language control: twelve documents, four batches per document, seven
questions per document. Both variants in a pair have the same balance changes,
ownership changes, delivery seals and questions. The control removes distracting
or indirect wording. This equivalence is an authoring intention to be checked
independently, not an established result.

Every document starts with explicit postings for amber10 and birch11. Updates
use only literal integer set, addition and subtraction; there are no remove,
reopen, relative multiplication, implicit compensation or repeated identical
update sentences within a document. Questions explicitly name the requested
end-of-batch time. Historical checkpoints and ownership lookups vary across the
cases; a later review reference does not imply using the latest ticket owner.

| Pair | Language challenge |
| --- | --- |
| s01 | Hypothetical and cancelled-before-posting changes alongside actual postings |
| s02 | An unposted draft replaced before posting; a forecast without a posting |
| s03 | An already posted transaction reversed by an explicit later transaction, preserving historical states |
| s04 | Alias attribution with canonical counter names supplied in every affected batch |
| s05 | Nearby planned or forecast numbers competing with actual posting amounts |
| s06 | Ownership changes, cancelled transfers and a review-to-case-to-ticket historical join |

Stable document IDs use `s01-stress` and `s01-control` through `s06-stress` and
`s06-control`. Question IDs are stable within their pair and repeat across its
two variants so a paired comparison can address the same question. Each question
declares `answer_type` as `int` or `str`; historical questions can have either
type. The packet contains no expected answers, event annotations, marked update
spans or oracle. Literal source numbers are document facts, not answer metadata.

## Independent derivation before evaluation

An independent reviewer should derive the event inventory, end-of-batch states,
ownership timeline, and question answers from the raw document packet. That
review must not use the existing generated task oracle or execute ledger replay
as its sole answer derivation. A second review should resolve disagreements and
check the intended stress/control equivalence before a model sees either
variant. Preserve disagreements and any corrected packet as separate revisions;
bind a subsequent key to the exact document bytes. Do not silently replace
documents or a key after observing model results.

Separate extraction omissions, spurious events, wrong counter/operation/amount,
checker refusals, checkpoint-state errors and final-answer errors. A wrong event
can be overwritten later, so final-answer accuracy alone cannot establish
correct extraction. Likewise, a refusal caused by an unsupported interface is
different from misunderstanding an otherwise supported document.

The current ledger checks source provenance and arithmetic, not interpretation.
A quote is a whitespace-normalized substring. The canonical counter need only
appear in the same delivered batch; an amount may be found in the quoted
sentence or a counter-naming sentence in its paragraph. Empty event lists are
accepted. Therefore cancellation, attribution and nearby-number cases can
expose semantically wrong events that still satisfy provenance checks. This
packet neither strengthens those checks nor claims that quotation establishes
completeness or correct interpretation.

## Explicit interface and scope boundary

The current campaign accepts only its frozen generated task identities, and its
task verifier has a different schema. Its answering protocol also treats all
historical answers as strings. These documents are not directly runnable through
that interface: any future diagnostic adapter must explicitly support the
declared question types, keep answers private from model prompts, and preserve
raw document bytes. This authoring task does not implement such an adapter.

Cross-batch aliases lacking a canonical name in the affected delivery, duplicate
identical event occurrences, remove/reopen lifecycles and implicit retroactive
amendments are deliberately outside this packet. Adding them later requires
explicit interface work and its own tests, not relaxed interpretation of the
existing quoting guarantees.

These short, authored cases assess development behavior. They are not held-out
evidence, external documents, a broad semantic benchmark, a long-context test,
or evidence of production reliability. Matched controls do not substitute for
an independently authored confirmatory corpus.

## Following experiment, if justified

After semantic diagnosis, investigate sparse updates to substantially larger
state tables and measure reliability alongside cost. An eight-counter archive
emits a small state table, while quoted events include substantial source text;
a speed advantage for quoting is not assumed. Report ingestion and answering
costs separately, include all calls, and retain cold-cache and replication
requirements. Both present structured methods expose their full current state
in ingestion prompts, so larger-state tests must measure the shared prompt
budget limit rather than imply that durable storage alone removes it.
