# Independent v6 evidence review

Review passed after one concrete evidence gap was fixed. The runtime controller
and native binary were not changed. All 51 state-comparison tests and nine
trace/finalizer tests passed independently; source hashes are retained in
`independent-review.json`.

The initial trace auditor accepted a final-stage ROW issued before its matching
provider operation. On a two-stage mock with six outputs, moving final ROW issue
14 ahead of provider issue 12 preserved raw bytes and per-owner order but would
invalidate the native parent marker. The auditor checked only an already-active
provider command and missed the pre-reservation lease. The fixed auditor holds
the lease from final ACCEPT through provider completion and checks final-owner
quiescence at provider admission. The exact reorder regression now refuses it.
`reproduce-parent-lease-order.py` preserves the small reproducer; run with the
engine tools/planning and research continuation directories on PYTHONPATH.

V5 survival validation and its finalizer are byte-identical to the committed
implementations. The comparator dispatches only explicit v6 manifests to the
new survival rules. Full before/after canonical, pinned, private, host, Sequence
and prepared-binding identities remain required. V6 can report an authenticated
empty survival trace or a preserved provider state that did not advance after
a target snapshot; advancement is derived from recorded positions/serials,
never manufactured from a successful comparison. Downstream target aborts do
not claim independent provider ownership.

The independent replay binds issued/completed raw wire messages, native target
commands, actual proposal origins and prefixes, final records, target truth,
provider canonical pairs, recursive guesses and every stage-zero survival
receipt. New ROW tentative flags follow current target truth, while ACCEPT,
ABORT and provider metadata retain the original local ROW flag. The native trace
must match those exact per-owner original flags.

This first finalizer deliberately qualifies the complete matched full-cap
reference cohort. It does not claim early-EOS or cancelled-prefix proof; those
paths need separate evidence scopes if added later. Actual model replay,
complete sealed target/draft comparison and durable archive remain parent-owned
steps after this CPU evidence review. No performance claim follows from these
diagnostic checks.
