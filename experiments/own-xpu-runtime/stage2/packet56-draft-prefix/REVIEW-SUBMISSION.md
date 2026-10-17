# Packet56 independent submission review

Reviewed on 2026-10-17 by the CPU-gates agent, independently of the submission
and overlay authors. This was a source/evidence review; no GPU, model payload,
network submission, or protected packet edit was performed.

The packet-local submission extension retains the packet49 oracle binding,
exact output-token checks, timestamp-derived speed, complete varied suite,
zero cached tokens, fresh owner identities, native binary hashes, teardown,
and kernel-log checks. The packet56 seal and every required model window bind
the prefix calibration and generated configuration hashes. The strict
512-token gate remains false under the inherited explicit 128-token scope.

One blocking submission issue was found and fixed: a prepared queue initially
replayed only its bundled record floor. A later packet49d record could therefore
make its eligibility stale. `scope_problems()` now rereads the current pinned
record file immediately during packet56 posting preflight and requires the
measured rate to exceed it. The author's focused regression test prepares a
synthetic 51.25 tok/s queue, advances the synthetic floor to 52, and verifies
that both local validation and the unchanged shared CLI refuse the queue.
Historical evidence replay remains possible. The reviewer inspected the fix
and test; the author reported all eight submission tests passing.

The KD review also found that the new resident-head requirement rejected the
existing isolated draft capture, which defaults to layer streaming. The final
overlay exempts only that existing diagnostic capture allocation; production
still requires the shared resident head. KD now dumps only the computed prefix
logits and checks their exact extent and calibration identity before comparing
host/device bytes. The historical `compare_draft.py` helper is not part of the
authorized KD chain; it must not supply full-vocabulary draft equality claims.

The inspected Git diff showed no tracked changes to packet49d or the shared
submission helper, pins, and record-floor files. No blocking finding remained
in the reviewed submission changes. Device K windows and the complete model
chain remain required; synthetic CPU tests are not model certification.
