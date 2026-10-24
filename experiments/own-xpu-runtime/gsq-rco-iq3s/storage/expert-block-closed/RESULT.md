# Closed expert-block state archival — October 24

All54 audited target-state bundles are preserved in verified archives. The raw
5,987,065,536 bytes occupy2,320,696,389 compressed bytes. Every batch completed
archive/member readback, verified original removal, USB offload/readback and local
archive release. All216 phase receipts pass. No retry, model file removal, device
operation or setting change occurred. USBfree6,260,334,592/rootfree27,245,862,912
bytes at completion. Quotas and reserves were unchanged.

[Completion map](evidence/complete.json) records every original path, archive size,
SHA256 and phase-receipt hash; [final root check](evidence/root-final-review.json)
verifies receipt joins and the actual local archive filenames. The original
[full-engine result](../../expert-iq3xxs-block/engine/operating/RESULT.md) remains
bound to its independent all-byte readback. All JSON, logical indices, seals and
draft state remain at their original paths.

USB archives are `/mnt/usb-models/own-xpu-runtime-results/gsq-expert-block-state-bundle-NN.tar.gz`,
NN00–53. NVMe phase/restore receipts remain under
`/home/steve/own-xpu-runtime-results/gsq-expert-block-bundle-archive-a/chunk-NN`.
Each archive contains its one exact relative state.bundle path. Restore only a
missing bundle into the original run root and verify size/SHA against the bound
independent artifact index; retain its adjacent index/seal/state JSON.

The [bound helper](closed_expert_bundles.py) uses the unchanged filesystem Job,
128MiB quota and27GB+64MiB reserve. The unbound preparation and conditional review
are retained under lineage; only actual closed PASS hashes authorize these phases.
