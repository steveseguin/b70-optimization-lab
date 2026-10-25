# Independent rolling provenance review

The isolated typed-event model passed 14 additional rejection cases in
`review_provenance.py`; its source-bound receipt is
`provenance-audit-review.json`. Malformed provider serial, restored position,
target cursors, pending IDs, token type/range/depth and malformed final-parent
ROW/ticket/commit refuse before provider retirement/publication or final target
commit. Failure remains sticky. All 15 existing arbiter/coordinator/socket tests
also passed independently.

The socket bridge uses the real final-record decoder and pending-provider codec
before invoking the typed-event coordinator. Original accepted ROW metadata,
including an originally tentative seed's ticket/flag, remains intact. The owned
final record and hidden bytes remain bound to the job until its validated reply.
Actual proposal tokens feed the existing immutable issued-row contract. No
blocker was found within this isolated CPU/socket scope.

The mock workers use synthetic arithmetic and modeled survival. Neither these
tests nor the event-level Parent hashes establish native numerical equality or
actual provider memory survival. Runtime qualification additionally needs the
versioned evidence contract in `V6_EVIDENCE_GATE.md`. At the review point, the
bridge retains raw final-record witnesses but only decoded provider proposals;
retaining raw provider publication/reply witnesses is a follow-up requirement
for independently rerunning that codec offline. Existing native/controller v5
proof files were not modified.
