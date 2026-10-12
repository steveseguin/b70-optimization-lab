# Packet40 CPU qualification in progress

This supersedes the copied packet38 summary. No device ran and no speed is
claimed. The build receipt remains incomplete until current-source qualification
is sealed. Copied parent receipts are historical inputs only.

Current completed coverage includes:

- 202 miniature cancellation/retention cases across native and Python controllers:
  all 100 launch boundaries per controller and 1,400 forced-miss/redo comparisons.
- Four seeded real-model cancellation boundaries out of 909 actual launches,
  with the original 87-token input and two exact outputs; full plan and spare-bank
  state hashes agree. Real-model retention on/off also agrees.
- Independent archived-inventory validation of all 204 forced-boundary cases
  (100 miniature per controller plus four real), excluding only the separately
  recorded operation counter.
- Eight retention comparisons over twelve requests, both controllers and both
  64/128-token caps; none, early fixtures and early/tail fixtures produce identical
  tokens and complete model-state inventories.
- 1,109 actual miniature native/Python paired cases, including all 1,093 ternary
  guess patterns through length six and twelve randomized 64-token cases. The
  terminal case uses the explicitly limited committed-state comparison below.
- 28 draft publication/failure cases, both controllers and retention modes;
  target token authority and all 210 target-state entries agree.
- Normal, ASAN and TSan standalone controller checks: 1,123 cases per build;
  five mailbox cases per build.
- 1,056 exact-array QSA capacity comparisons across two compilers and 132 capacities.
- Every wrapper rehearsed on CPU: 22 success and 22 ordinary-failure outcomes,
  with summaries, source/archive bindings and no ordinary-error boot latch.
- 27 metric unit tests, including the hand-computed interval formulas.

These are separate gate counts, not a combined benchmark sample size. Consult
individual receipts and the final execution audit for current hash bindings.
Inherited real-model qualification, selected-kernel draft references, actual
128-token tail fixtures and final admission checks remain in progress.

The strict terminal-EOS image restoration is now implemented; see
EOS-STATE-SCOPE.md. The coverage listed above records earlier completed work and
must not substitute for current-source qualification of the rebuilt snapshot
implementation. No reduced-state exception is assumed. The final seal must
authenticate fresh full-state terminal, retention and cancellation evidence.
