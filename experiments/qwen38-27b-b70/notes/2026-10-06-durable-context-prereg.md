# Durable context: protocol frozen before model evaluation

Date: 2026-10-06. Status: implementation and CPU validation; model evaluation
has not started. The protected plan-E Harbor campaign keeps its original code
and owns the two-card endpoint. This work does not stop or compete with it.

## Question

Under the same bounded working memory and source-retrieval permissions, does
quoted extraction plus transactional arithmetic improve reliable task completion
against summaries and a model-maintained state table?

This is a synthetic system comparison, not an "unlimited context" claim or a
reproduction of the CLM paper. The purpose is to separate extraction, preservation
and retrieval before spending more GPU time on long streams.

## Fixed protocol

- Same Qwen3.8-27B FP8 model, 16-bit attention cache and qualified server identity
  for all arms. Record the actual launch artifact hash. Do not silently adopt a
  changed model, engine or compression mode.
- Arms: periodic summaries, model-written state/index plus source archive,
  and quoted events applied by the durable store. All have identical source
  search/fetch permissions and the same final questions.
- Prompt limit: 32,768 UTF-8 bytes including serialized system/user messages.
  This is not a token-window claim. Also record actual server-reported prompt
  tokens; missing usage stays unknown, never zero.
- Thinking off, greedy temperature zero, output allowance 4,096 tokens. At most
  three extraction attempts per batch and 24 final retrieval operations.
  No network retry or automatic server restart. Failures remain evidence.
- Six held-out cases: seeds 101, 202, 303 in report and dispatch writing styles,
  48 batches each, 320 filler words per batch plus actual content. Three arms per
  case, eighteen trials. Rotate arm order across cases to balance position.
- Exactly eight questions each for current state, historical details and a
  three-part cross-reference, regardless of how many counters survive. Numeric
  answers are type-strict; extra keys invalidate a response.
- Task files and code are hash-bound in the frozen plan. Any intervention after
  seeing held-out results creates a new development revision; it does not replace
  the failed result or become another attempt at the same claimed holdout.

## Gates and reporting

1. CPU tests must demonstrate canonical source preservation, conflicting/repeated
   event rejection, source ordering, transaction rollback after process loss,
   recovery after apply-before-checkpoint, torn-log recovery, task validation,
   and failure reporting. These tests establish software behavior, not model skill.
2. Development seed 7, both styles: one-step extraction with true prior state
   supplied independently. Require 100% exact event extraction in source order on fixed
   batches 1, 2, 3, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 47, 48
   (53 events per style), using the frozen 48-batch, 320-filler-word development
   task and the same 32,768-byte budget. Smaller diagnostics cannot unlock the
   holdout. Record all malformed responses. No holdout answers inform fixes.
3. Correctness gate: all 24 final answers correct and no invalid/unfinished trial
   in the frozen comparison. Report each category and seed separately regardless
   of passing. Per-batch table correctness is also reported for archive/quoted;
   the summary arm's unobserved intermediate state remains unavailable.
4. Speed is considered only for a complete model comparison with no resumed or
   failed attempts. Candidate threshold: at least 10% lower median paired elapsed
   ratio against the archive arm at the required correctness. All retries and
   retrieval are included. A failed trial is not replaced by its fastest retry.
5. One eighteen-trial campaign is a screening result. A speed headline requires
   confirmation on a second fresh qualified server under the lab's existing rule,
   plus another held-out task set. No broad document-memory claim from this corpus.

Source matching does not establish operation meaning or completeness. It is
possible to quote the right sentence and choose the wrong operation. The hidden
oracle grades that independently; it is never given to the production model
client. The stub receives it deliberately and is always labeled as a wiring test.

## Deliverables and launch boundary

- [Frozen development and held-out tasks](../data/2026-10-06-durable-context/README.md).
- [Durable harness and commands](../scripts/context/durable/README.md).
- [Canonical historical trial exporter](../scripts/context/evidence/README.md).
- [Historical manifest](../data/2026-10-05-context/canonical-2026-10-06/manifest.json)
  and [automatically generated table](../data/2026-10-05-context/canonical-2026-10-06/results.md).

Build and freeze the pilot while plan E runs. Do not inject calls into its endpoint
or change its queued imports. Once the protected work releases the machine,
perform the normal health/resource preflight, run the development diagnostic,
then the held-out comparison if it passes. No unattended server relaunch is
installed by this change.
