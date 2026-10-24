# Duplicate archive consolidation complete

All41 fixed duplicate containers passed full compressed-file and every-member
verification against the retained canonical baseline archives. Separate verified
release phases recovered3,586,696,105 bytes. Every canonical archive remains.
No model, metadata from the original run, or historical receipt was removed.

The27 combined archives had exactly matching member inventories; the14 attention
prefix archives were exact target-state subsets. Each verified restore map retains
original member bytes by hash and original tar/PAX metadata. Original compressed
container bytes are not reconstructible and are not claimed identical.

[Complete mapping](evidence/complete.json) links every original path to its
canonical archive and tracked compressed restore map. Verify the canonical archive
and redirect hashes, restore only original_members with the saved metadata, and
check every member size/SHA. Historical consumers must consult these redirects;
old receipts continue to record the original archive identity. No symlink replaces
an original archive and no old hash is silently changed.

Root copied every restore map into repository evidence before releasing that
container. All82 explicit verify/release phases passed without retries. The new
Q6 full suite can now retain its complete state evidence with the2GiB reserve.
