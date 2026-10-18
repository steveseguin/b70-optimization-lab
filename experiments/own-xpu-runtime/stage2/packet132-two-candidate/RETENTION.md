# Packet132 evidence retention review

The five files `evidence/capture/doc-{0,1,2,3,4}/target/teardown.json` each
contain 2,342,225 bytes, so repository hygiene flags them for review. Keep
them intact. They are the original CPU oracle's complete ordered cleanup
receipts, including every release event and the final zero-in-flight,
zero-live-bytes status. A shortened status summary would lose the release
sequence needed to audit cleanup or compare a future harness change.
Their `MockDevice` backend records CPU harness cleanup, not GPU health.

All five have SHA-256
`adcd0d587b7c4fc2f31495a59fd364746370bb2b73cdd1943269fb66e6ce4057`.
The paths bind each receipt to its own target run. Identical bytes are not a
reason to discard a run's evidence; Git stores the shared blob once.
Consumers are [retain_capture.py](retain_capture.py), the
[retention manifest](evidence/capture/retention-manifest.json), and source/run
audits following the [analysis](ANALYSIS.md). The acceptance analyzer does not
need to parse these large cleanup sequences.

Restore any receipt by copying the tracked file to the identical relative
path under `build/capture`, then run the retention check from the analysis.
The manifest records each path's byte count and SHA-256. Original capture
files remain in the ignored build tree. Nothing was deleted or replaced by a
summary.

Target state streams and private generated source are stored in six
deterministic archives. Every archived member was compared byte-for-byte with
its original, and its original hash and restoration command are recorded in
the same manifest. No weights or generated caches are tracked.
