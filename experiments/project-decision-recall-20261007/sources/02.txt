# Context campaign follow-up

The million-token quoted trial completed with **24/24**, nonvoid, in 47.9 minutes.
Its input stream and expected-answer hashes match the read-mode trial that scored
23/24 in 62.2 minutes. The observed elapsed reduction is 23.0% for this one pair;
it is not a repeat-confirmed speed result or evidence that every intermediate
state was correct. The legacy checker limitations in the
[review](2026-10-06-context-review.md) still apply.

The new [canonical snapshot](../data/2026-10-05-context/canonical-2026-10-07/manifest.json)
contains 31 attempts: 29 completed, one interrupted and one incomplete. It retains
all prior attempt IDs. The million-token attempt has progressed from incomplete
to completed; the 480K quoted seed-1 attempt is still incomplete at this snapshot.
That seed's generated task asks 21 questions, not 24. The earlier snapshot remains
unchanged as the record of what was known then.

## A queued cell did not run

The quoted retention seed-1 block (`ret120q2`) failed during planning because its
task file was absent. The existing 35/36 result in that directory is seed 0.
The wrapper continued to the next block. This is a setup failure, with no model
score, and is recorded in the [campaign audit](../data/2026-10-05-context/canonical-2026-10-07/campaign-audit.json)
and its copied log prefix. A final `plan complete` message from this wrapper
must not be presented as completion of every cell.

The durable campaign already verifies the complete planned task/arm matrix and
retains failures. Keep its tasks frozen and finish the planned extraction and
retrieval comparison before adding more legacy reruns. Review the remaining
legacy cells when the current campaign releases the machine.

## Next experiment

The [durable protocol](2026-10-06-durable-context-prereg.md) remains unchanged:
both fixed development diagnostics must pass before the eighteen held-out trials.
The new host coordinator is kept outside the frozen model-facing source directory.
It must wait for the protected supervisor to exit and for its server and clients
to release the machine; a gap between its retry attempts is not a handoff.
It uses a single owned server, preserves stop/failure receipts, and never uses
the legacy supervisor's automatic retries or process-pattern kills.
