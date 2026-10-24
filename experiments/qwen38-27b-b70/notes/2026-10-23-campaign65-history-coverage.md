# Campaign 65: exhaustive history requires original evidence

Registered after campaign 64's full-task failure and before any campaign-65 model call.
The existing keeper repairs all 40 bugs and keeps all rules, but pi writes only three of seven
historical audit entries. Its own reasoning considers that other early repairs may exist, then
treats the surviving NOTES list as exhaustive. No audit-time recall occurs.

## One intervention

Add one generic history-use contract to the main agent's existing memory instruction. NOTES are
selective, absence is not evidence that an event never occurred, and an exhaustive historical
request requires original archive evidence covering the requested scope. A short search result
is not proof of complete coverage. Genuine later corrections still take precedence where applicable.
The exact suffix is frozen in the probe before launch; no task names, ticket numbers, expected
answers or fixture-specific retrieval hints enter it. No notes parser, reviewer, cap or recipe change.

This addresses an unavoidable distinction even with better notes: a summary is not a complete event
log. Campaign 64 also exposes repeated generic STATE keys overwriting earlier completed events
under intended last-value semantics, and a failed rewrite advancing the archive cut without new
notes. Those are separately recorded failure paths, not silently changed in this experiment.

## Frozen reconstruction and gate

Select campaign 64's actual client request 289: 601 original messages ending in the real audit
instruction. Freeze its original body, the saved notes through archive message 585, and the archive
prefix through that same boundary. Production `Keeper.complete` against a fake upstream captures
the prepared request. It must make exactly one main call, no notes call, no cut/restart/recall,
and produce 19 upstream messages. The historical call used 6,026 prompt tokens; check the control's
measured prompt count against that receipt.

This is a reconstructed state, not a claim that historical wire bytes were saved. The final counters
and token-ratio estimate are later than the audit request; CPU checks must establish that they do
not change the cut or the prepared path. No future messages, final answer or expected audit entries
enter model-visible input. The unchanged production proxy already transforms streaming client input
to a nonstreaming upstream request; no extra transport change is introduced.

Run the unchanged reconstructed control first. It must reproduce the original first external action:
writing exactly `6 | time_limited`, `7 | numeric_range`, `8 | classify_unique` to `/app/AUDIT.md`,
with no recall. Otherwise stop: the reconstruction is inconclusive and the candidate does not run.
If qualified, run one fresh cloned candidate state with only the generic memory suffix changed.

Production archive recall executes against the frozen prefix, with the original 16-round recall bound.
Stop at the first external task-tool action; never execute model shell, read, edit or write tools.
A candidate passes only if it retrieves original evidence and proposes the exact seven-line audit
with no extra entries. A read/bash/other first action is recorded as needing full-task continuation,
not scored as a completed artifact. No adaptive fixture extension, prompt sweep, closing retry or
selective rerun. Original model output cap and sampling fields stay unchanged.

## Predictions and next decision

Prediction: control remains 3/7 with no recall; candidate recalls original early receipts and writes
7/7. This one decisive-turn diagnostic cannot qualify the whole agent or a production default.
If it passes, the next measurement is a fresh full pi task with that one contract change. If it
fails or the control does not reproduce, record the reason and close this particular diagnostic
without enlarging it into a replay matrix. Historical source correctness and valid user corrections
remain separate transfer gates before any promotion.

## Lifecycle

One fresh c59-identity two-card Qwen3.8-27B FP8 server, full-precision KV, MTP5, two sequences,
medium effort and piece 832. No resident restore or automatic retry. CPU capture tests and independent
source review precede launch; no agents/tests/builds beside the model and no push until shutdown.
The check-client cap is 1,800 seconds for the two gated arms; no external task tool executes.
Parent remains active through completion, source audit and the next practical decision.

## Frozen implementation and checks

The exact candidate suffix is:

```text
- NOTES are selective memory, not an exhaustive event log. Absence from NOTES does not establish that an event never happened.
- Before producing an exhaustive historical list, use recall to inspect the original evidence for the requested range and verify coverage. Search snippets can omit matches or truncate messages; inspect original messages as needed.
- Historical evidence does not cancel later authorized corrections or changes of instruction.
```

[Probe](../scripts/context/main_history_contract_probe.py), [runner](../scripts/context/run_campaign65.py),
[seven CPU tests](../scripts/context/test_main_history_contract_probe.py),
[actual frozen capture check](../data/2026-10-23-campaign65-preflight/cpu-check.json),
[independent review](../data/2026-10-23-campaign65-preflight/review.json).
[Compressed fixture and restore map](../data/2026-10-23-campaign65-fixture/retention.json) preserve every
input byte and both production captures; grading expectations stay outside model-visible requests.
The first device control must also match the historical 6,026 prompt-token count. Correct proposed
content is only a screen: manual source review must establish original-evidence coverage before a
full-task follow-up. Per-call HTTP timeout is 600 seconds without retries; the unchanged output cap
and production recall bound are preserved.
