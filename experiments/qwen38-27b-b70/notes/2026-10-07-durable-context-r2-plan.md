# Durable context revision 2: repair and qualification plan

The first pilot retained its source correctly but failed to use that source to
answer reliably. Mixed answer/retrieval responses were prematurely finalized;
substring retrieval confused batch 2 with batches 20–29; repeated searches
exhausted the budget. Preserve that failed pilot and its harness unchanged.

1. Implement a separate `durable_v2` protocol (`durable-context-r2`). Persist
   partial answers, request budgets and retrieved evidence. Require explicit
   submission covering every question, with null allowed as an admitted unknown.
   Invalid or ambiguous actions return format feedback without correctness hints.
2. Offer exact batch retrieval and numeric-boundary search. Repeated requests
   return cached evidence, consume an action, and do not consume another retrieval
   slot. Keep questions, saved answers and remaining budgets visible.
3. Reproduce the observed failures in CPU tests, including interrupted answer
   sessions. Reserve each of 32 answer calls before dispatch; allow at most 24
   distinct retrieval operations. All three arms use this same protocol.
4. Run the existing two extraction diagnostics, then full development tasks:
   seed 7, both authored styles, 48 batches and 320 filler words, all three arms.
   All six native model trials must complete cleanly and answer all 24 questions
   correctly before any new held-out run. Regrade saved native answers against
   regenerated tasks; bind source, runtime, budgets and execution history.
5. Only after that gate passes, run fresh held-out seeds 401, 502 and 603 in both
   styles: 18 trials. The previously inspected seeds 101, 202 and 303 are spent.
   Freeze tasks and source plans before model requests. Keep all failures.
6. Use one explicitly prepared, strictly qualified server for the campaign and
   stop it on completion or failure. No automatic server retries. Publish no
   speed conclusion unless quality, completeness and timing requirements pass.

The working context remains **32,768 UTF-8 bytes**, not 32K model tokens.
This remains a synthetic pilot with two authored styles. Quote validation proves
applied arithmetic provenance, not complete extraction or general understanding.

Implementation is separate in `scripts/context/durable_v2/`, with a separate
`durable_v2_host_runner.py`. Independent review checked answer persistence,
submission, evidence eviction, restart budget reservation and lifecycle ownership.
CPU validation passed 77 harness tests and 24 host-runner tests. The six-trial
scripted control passed as wiring evidence only. Documentation and manifest path
checks found no missing links. The global historical pin check remains at its
known baseline: 87 matches, 231 drifted pins, zero absent targets.

Tasks and both plans are frozen in `data/2026-10-07-durable-context-r2/`.
Live output is designated `/mnt/fast-ai/bench-results/context-durable-r2-20261007`.
The owned unit is `ctx-durable-r2.service`, with no restart policy. Its live
status and final receipts determine execution outcome; this plan is not a claim
that qualification or any model trial passed.
