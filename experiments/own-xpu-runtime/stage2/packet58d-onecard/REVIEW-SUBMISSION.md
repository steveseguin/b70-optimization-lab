# Packet58 independent evidence and submission review

CPU-only review of `window.py`, `suite_driver.py`, `packet58_submission.py`
and the request-reset/timing path in `main.cpp`, by the cache/gates subagent.
No device, model read, external submission or credential access occurred.

## Findings corrected

1. Submission derivation checked chronological named windows but did not
   check their `previous` links. A sibling receipt with identical bytes could
   stand in for the actual chain predecessor. Derivation now requires the
   hash-bound `previous` path to equal the immediately preceding window in
   this chain. KD must follow this chain's K1b.
2. K1 references could point to another compatible chain, and their extra
   native-K1 hash field was unused. Derivation now requires the exact ordered
   K1a/K1b pair in the supplied chain and verifies each native K1 hash.
   Every model stage must start after both K1 windows; K1a must finish before
   K1b starts. Time fields must be positive integers, and starts must precede
   finishes. K1 and model owner identities cannot repeat.
3. Prerequisite admission originally accepted any nonempty native-file map,
   then read `run/k1.json` whether or not that file was bound. The window
   author fixed this after review: K1 now has an exact required closure;
   full-model prerequisites require all actual native run files and the
   expected driver/native receipts. Both closures include kernel logs and
   summaries. Missing, added or changed files, failure reasons and kernel
   faults refuse admission. Submission derivation invokes that same gate on
   every model window, so it does not rely on stored `passed` alone.
4. Suite summarization accepted a top-level safe-exit boolean without checking
   its underlying owner receipt. It now requires exactly one owner, a
   completed idle marker, zero exit code, zero in-flight events and zero live
   bytes. Boolean values cannot substitute for integer teardown counts.

Nine new mutation tests in `test_submission_provenance.py` cover exact valid
predecessors, sibling substitution, missing/tampered links, unrelated or
reordered K1 pairs, changed native K1 evidence, malformed/overlapping time,
unbound K1 JSON, and incomplete/live/native teardown. Together with the
existing suite and window tests, **34 tests passed** using:

```bash
cd experiments/own-xpu-runtime/stage2/packet58-onecard
nice -n 19 taskset -c 4-15,20-31 python3 -B -m unittest \
  test_suite_driver58 test_window test_submission_provenance -v
```

## Scope and fairness verified in source

- The one-card threshold is independently pinned to the submission ledger.
  The two-card record is not imported as the one-card threshold.
- Every request's generated token list is compared to its unchanged packet49
  CPU oracle. WS additionally compares all 48 layer fixtures for each of the
  first eight output positions on all 12 fixed prompts. The later positions
  are token-exact checks; they are not labeled full hidden-state comparisons.
- The complete fixed suite identity and varied prompt classes are inherited
  from the hash-bound oracle. WS128x and WS128 use separate fresh native
  processes without retained layer snapshots. All three full suites must
  produce the same token sequences. Metric windows require 100 generated
  events and use their 99 intervals, with the class-balanced aggregation.
- Request reset clears mutable scratch, KV, recurrent state, PLE history,
  control words and lookup staging in place. Process-lifetime immutable
  weights, cache and tables persist. The kernel author's CPU reset gate is
  additional evidence; source review alone is not a native reset measurement.
- Completed-token timestamps follow cache admission, so fill latency is
  included. The initial cache is empty and independent of benchmark content.
  No prompt/KV/answer reuse is introduced by weight caching.
- This packet's requested suite cap is 128. The draft payload and attestation
  explicitly keep the strict 512-token final gate false, state the absent
  512-token prefill/natural-completion measurements, and require scope review.
  The tool creates an offline draft and never posts or reads credentials.

## Remaining qualification

The code has no native results yet. CPU gates do not establish host-pointer
support, full-model equality, a one-card speed, actual host/GPU peaks or a
publishable result. K1 and all model windows must run through the coordinator.
A valid source/build seal must include the new review fixes and mutation test.
