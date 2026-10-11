# Independent review

Two read-only subagents reviewed packet18; neither executed or discovered a
device. The first audited platform math and contraction-sensitive expressions.
The second audited event order and buffer lifetimes, including the removal of
per-site control-copy submissions.

Arithmetic review: v2 exp/log and deliberate FMA expressions match packet17.
GEMV reductions and explicit parenthesization are unchanged. Norm uses the
single selected rsqrt switch; GDN/QSA divisions still use IEEE sqrt and division,
not reciprocal multiplication. RoPE rounds normalized rows before rotation.
Fixed findings: standalone rope header includes cstddef; tiny rotary dimensions
are validated and mapped into the table; tiny second-half rotation spells
b*c+a*s like Core; the broad legacy mock header was replaced by its exact
synthetic weight helper so the recursive math grep is unambiguous.

Chain review: a single owner chains all compute/copy events across both queues.
Direct controls are owner-local allocations; sticky error is accessed atomically
inside ng work-groups and only after ordered completion by other kernels.
The extra table binding is runtime tail+4 / ng slot16. The table is process
lifetime and outside the streamed weight map. Snapshots precede buffer reuse;
attention score/probability scratch survives all three submissions; streamed
releases and event retirement follow completed work. No blocking issue found.

The removed bridge modes remain dead compatibility code, not launches; the
calculated census follows the actual dispatch. Native queue/peer behavior and
barrier correctness remain device gates. A timed-out device drain deliberately
retains the owner for coordinator recovery rather than hard-killing it.

Final build review independently checked all 15 actual device translation units
against the grep gate's 51-file include closure and every generated compile/link
precision flag. All provenance hashes match. The builder additionally rejects
any future device translation unit absent from the checked closure. Loader-only
RPATH verification is retained in the final build receipt.

Both core and parallel reject a deliberately changed layer 0 oracle byte with
`passed=false`, `oracle_exact=false`, the first-layer message and safe owner
teardown. The two CPU checks are reproducible through test_mismatch.py and
retained in cpu-mismatch-rejection.json.
