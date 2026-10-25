# Four-card persistent rolling suite: correct outputs, no speed gain

The complete cold suite passed all twelve answers: **5,965 output IDs match**
the retained GPU baseline. All **2,065 target-state buffers** also match at the
end of the final decision-memo request (input position 571). The ordinary median
full-response decode observation is **41.57 tokens/s**, below the earlier
four-card observation of **42.31**. The retained two-card service observation is
**47.97**; its service timing layer differs from this controller's timestamps.
This is a negative speed result, not a promoted record.

The fixed six-class first-99-interval metric is **42.68 tokens/s**. It is computed
from generated-token timestamps 1 through 100, then medians within classes and
across classes. It must not be compared with the older 47.97 full-response
aggregate. [Timing definitions and rows](TIMING.md).

## What was checked

- One loaded four-worker set served twelve fresh prompts with native resets,
  zero cached tokens and no prompt/KV/response reuse. Eleven responses reached
  the 512-token cap; customer-email ended naturally at 333 tokens.
- Raw command, epoch, proposal, native execution and reset witnesses passed the
  frozen auditor and a separate review. Actual two-step proposals used the
  existing MTP weights; no draft training or scripted guesses were used.
- The final target state matches the retained four-card suite. The final
  canonical draft's 73 allocations are authenticated, but there is no matching
  independent long-cohort draft-state parity claim. Intermediate requests have
  output/reset/provenance checks, not full-state comparisons.
- Earlier two-request gates established target/draft parity with both diagnostic
  policies. The measured policy omits expensive byte/survival readbacks and
  reports them as disabled; mandatory copies and error checks remain enabled.
  Reset operations were audited, without claiming full cold-allocation readback.
- All four workers exited zero. Passive observations retained the same fourteen
  historical fault signatures; no new fault occurred. GPUs are idle after the run.

The six independent CPU-reference disagreements remain unresolved. This result
establishes equality with the retained GPU engine, not full CPU-reference equality.
LocalMaxxing submission is **withheld**: no new matched promoted record and no
complete promotion/determinism/oracle attestation. The exact disposition is in
[window metrics](../persistent-rolling-suite-window-metrics.json).

## Identity and reproduction

Binary SHA256: `02a47c059444af0e9179612461a8078e4308f3357fb54e370421a2ba1b7788aa`.
Layer cuts: `0,13,25,37,48`; BDF order: `23,27,43,47`; context 4096;
unchanged SC117 target/quantization, f32 activation/state mode; existing MTP.
Source at launch: `de9b4356f8304ed8d60c319b821f30ab94ef9452`.
The [plan](plan.json), [prompt-only runtime inputs](runtime-inputs.json),
[run command](../ring-persistent-suite-run-command.json),
[prerequisite closure](../ring-persistent-suite-prerequisite-preflight.json) and
[summary](summary.json) bind the exact model, binary, environment and source.
The [auditor](../finalize_persistent_rolling_suite.py) is separate from inference.
This is a lab reproduction record; it does not claim a clean-host portable
rolling service or a standalone public raw-state replay kit.

## Evidence preservation

This directory is an exact metadata selection, not the complete proof directory.
[The selection manifest](metadata-selection.json) lists every original member,
size and hash. Bulk journals remain in the complete archive.
[Full archive](../persistent-rolling-suite-full-archive.json),
[lossless reuse/restore check](../persistent-rolling-suite-reuse-archive.json),
[exact-tar recompression](../persistent-rolling-suite-recompressed-archive.json)
and [durable copy](../persistent-rolling-suite-durable-archive.json) retain the
entire run. Six sealed bundles restored successfully; four carry final target
parity, the canonical draft is authenticated, and the extra FINISH draft is
preserved without upgrading its evidence scope. Original files remain intact.
The compact packet depends on the hash-pinned earlier suite archive named in
its manifest; both are durable local artifacts, not public download promises.

Next: use the measured work imbalance to test a lighter first target stage,
which also owns the draft head. Preserve this result and unchanged arithmetic.
