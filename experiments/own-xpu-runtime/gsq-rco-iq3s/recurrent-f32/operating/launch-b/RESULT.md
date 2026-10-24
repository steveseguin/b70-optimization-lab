# Corrected native recurrent state: bounded pair passes

One persistent two-rank engine ran the original 87-token prompt for 32 outputs
in target-only mode, reset completely, then ran MTP. Independent readback
confirms identical complete tokens and target state. All 32 output tokens also
match the independent CPU reference using the same SC117 weights. MTP recorded
31 proposals: 26 accepted and five rejected. Every emitted token remained
target-verified. No speed claim follows from this correctness test.

All six captured bundles pass range and whole-file verification. The auditor
checked 330 FP32 recurrent/history ranges and counted 84,920,510 stored words
with nonzero low 16 bits, confirming actual full-width storage. Actual device
allocations match the new census: 31,083,481,994 and 29,995,470,740 bytes.
All five capture acknowledgements closed, both physical GPU contacts were seen,
both owners exited cleanly, target descriptors drained, protected vision and
the kernel-fault baseline remained unchanged. The unit ran for 111.21 seconds.

The preceding A attempt remains failed after the target DUMP when the root
cache reserve was crossed; it produced no complete pair qualification. Verified
archival of older closed driver caches recovered 271,221,744 root bytes. B adds
an initial-only 128 MiB allowance above the unchanged ongoing reserve. It uses
the same native binary and request identity, with fresh control/evidence paths.

[Independent actual review](evidence/device-b/review.json),
[closed artifact index](evidence/device-b/artifact-index.jsonl.gz), and
[source review](evidence/independent-review.json) preserve the result. The index
covers 166 artifacts and 983,965,212 bytes. Broad quality remains unqualified:
a short token match does not establish recurrent fidelity on long sequences or
resolve remaining reference activation/rounding differences. Next is a retained
same-prefix logit comparison and a few longer controlled comparisons.
