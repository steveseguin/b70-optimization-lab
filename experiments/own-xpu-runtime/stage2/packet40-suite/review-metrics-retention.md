# Packet 40 independent definition and token-authority review

Reviewed the frozen reference table, packet 38 SUITE.md, docs/localmaxxing.md,
scripts/submit_localmaxxing_results.py, the existing 20260904 TP4 payload queue,
and scripts/qualify_realistic_window_metrics.py. No device was opened or run.

The requested fixed 64-event figure is 63/(t64-t1), with timestamps in seconds.
It is null if fewer than 64 generated events exist; EOS at event64 counts. The historical
reference table also includes early-EOS rows using (N-1)/(tN-t1), N at most 64,
and excludes the final EOS event. These are separate fields: `fixed64_tok_s`
and `decode_tok_s` (the historical table-compatible rate). A separate pooled
observed-row median preserves the reference table's repeat accounting. The
primary attempt and each optional repeat are also reported separately; repeats
are never silently pooled into a cold submission attempt.

The submission window is exactly 99/(t100-t1), not 100/(t100-t1), and not the
median of 99 reciprocal interval durations. Natural EOS at event 100 is counted;
fewer than 100 events cannot supply this metric. First take ordinary medians
within each of the six fixed prompt classes, then the median of those class
medians. The all-prompt median is retained as a secondary value. The class map
is checked against the repository's qualification helper. A cap of 128 does
not satisfy the fixed 512-token public final gate; the receipt leaves that gate
false and does not manufacture a promotion attestation.

Hand checks: t1=10, t64=25.75 gives 63/15.75=4 tok/s; t100=34.75 gives
99/24.75=4 tok/s. For times [0,1,2,6], the three-interval rate is 3/6=0.5,
whereas median([1,1,0.25])=1 and is the wrong calculation. Class rates
code=[1,2,3], prose=[20] give class medians [2,20], primary=11; all-prompt
median=2.5. The CPU unit gate checks these examples, late invalid timestamps,
missing timestamp rows, EOS, retention diagnostics, cap guards, subsets and
both complete oracle manifests. The packet parent independently found and
requested the explicit fixed64/historical split and full timestamp validation;
both findings were fixed and retested.

Retention source review: the generation-step number remains Request.fixture;
the selector only gates snapshot copy/readback/publication. It never gates
target layers, final head, argmax, or token acceptance. Captures copy the streams
into a separate snapshot allocation. Snapshots are zeroed at initialization
and after readback so retention on/off can agree in final mutable-state hashes.
The full-state gate also exposed inherited uninitialized standalone scratch
(control/compact-route buffers); initialization now zeroes every standalone
mutable allocation once outside request timing. The negative receipt is retained
in retention-initialization-finding.json; the rebuilt runtime must pass the full
state comparison before sealing.
Candidate publication refuses a cancelled candidate. Actual full-state CPU
comparisons are separately bound in the cancellation/retention gate receipt.

Draft source review: DraftRuntime asserts no mutable allocation aliases any
target buffer or weight. Its input is a copied, confirmed previous hidden
state; its embedding row is read without preparing target PLE/history. Target
HALF inputs are queued after the draft's final copy on the same in-order queue,
using private pinned staging. A guess is read only after publication-event
completion and release/acquire mailbox publication; native acceptance still
compares it to rank 1's target token. Provider failure publishes no guess.
Python retains the synchronous correctness fallback; only native controller
uses asynchronous publication in this packet.

One event-lifetime concern was raised to the draft author: publication might
finish during target drain after the last enqueue callback. The reviewed
Engine::wait polls progress_callback while waiting and once more after tail
completion, before drain retires completed events. That ordering closes the
stale-event path and preserves publication/profile-event lifetime. Device
completion and timing behavior remain coordinator gates, not CPU claims.
