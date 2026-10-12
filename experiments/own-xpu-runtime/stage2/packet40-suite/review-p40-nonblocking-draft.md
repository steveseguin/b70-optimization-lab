# Independent review: asynchronous draft publication

Reviewer: cancellation/retention subagent, independent of the draft implementation.
This is source review, not a device measurement or a claim of native qualification.

The native controller waits for the draft *submission* acknowledgement, then sends
rank 1 its confirmed half before waiting for the guess publication. The target
half and draft use one owner and one in-order queue. The draft copies the prior
confirmed target hidden state into its private bank before the next half uploads
its new inputs. Draft outputs are restricted to private mutable allocation IDs;
the shared target output-head weights are immutable. Thus the target can consume
neither a draft scratch value nor the guess as its own rank-1 input.

The draft's private eight-byte pinned publication is written by two ordered
copies. `poll_result` reads it only after the final copy event completes. That
poll neither retires events nor drains the subsequent target half. Per-launch
and wait-loop callbacks let rank 1 publish the guess while its half runs. The
publication captures its Request by value and release-publishes the matching
draft sequence; rank 0 acquires that exact sequence before reading bytes. The
next publication cannot overwrite those bytes until rank 0 consumes the current
one and finishes the confirmation/rollback cycle.

The pinned next-half staging block stays owned until teardown and cannot be
rewritten until the previous half drains. Target token and position are checked
against the confirmed values saved by the draft command before bypassing the
ordinary blocking input setup. Failure before submission disables the provider
and publishes no guess; a private sticky error or injected late failure also
publishes no guess. Target backend faults still fail the rank. A provider error
never supplies an emitted token: only the checked rank-1 target Reply can emit.

No unresolved source-level ordering or lifetime defect was found. Device event
completion, driver scheduling, real overlap and KD host/device parity remain
coordinator gates. Python's controller retains its synchronous draft path.
