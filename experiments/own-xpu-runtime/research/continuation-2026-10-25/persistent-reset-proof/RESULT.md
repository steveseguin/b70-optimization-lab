# Persistent cold reset proof: PASSED

Two identical 87-token prompts ran in the same four native processes, with a
quiescent cold reset before each. Each request emitted the 32 baseline tokens,
and its 2,065 target buffers and 73 draft allocations were compared to the
accepted live PP4 run and to the other request. Full raw hidden pair identity,
all 117 provider steps and all 32 legacy draft proposals were checked separately.

All gates passed: True. Every stage's global wire sequence, native command
trace, cold reset receipt, preserved allocation layout and all 87 executed
prompt rows were checked. This proves request-state reuse was disabled for
these requests; process/model/page caches remained warm. No speed claim.

[Summary](summary.json), [target cross-comparison](request-target-comparison.json.gz),
[draft cross-comparison](request-draft-comparison.json.gz). Per-request packets
retain full comparisons and reset-audit details. Derived input adapters are
explicitly hash-bound to the original shared run and request records.
Original raw state remains external and in the verified durable archive.

The verified [content-addressed archive receipt](../persistent-reset-archive-verification.json)
retains all 16 raw bundles through five unique SHA256-addressed blobs: no bytes
were dropped. Its compressed size is 180,966,844 bytes. The archive includes
every original path and seal plus `restore_state_bundles.py`, which restores
independent copies after extraction. The [durable copy receipt](../persistent-reset-durable-archive.json)
records the independently rehashed USB copy; originals are untouched.
