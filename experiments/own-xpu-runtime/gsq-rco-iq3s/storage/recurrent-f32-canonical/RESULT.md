# Closed corrected-state bytes preserved through canonical copies

All16 mapped originals passed full-byte verification against their retained
canonical files, then a separate full rehash before release. Recovery totals
950,491,336 bytes. Nine canonical B files remain protected: four target bundles
(initial and target-only, both ranks) and five target-only draft files.

The originals were six duplicate target bundles (four from safely closed failed
A, two from B MTP) and ten initial draft files from A/B. No unique state bytes,
indexes, seals, result records or source artifacts were removed. Failed A remains
unqualified. B target-only logits and state remain directly readable.

[Closure binding](closure-binding.json), [review](evidence/independent-review.json),
and [complete release ledger](evidence/complete.json) preserve all mappings.
Per-batch restore.json records under evidence/batch-* describe exclusive copy
restoration and original metadata. Restore mapped originals before rerunning an
older auditor that expects the un-compacted physical file layout. No canonical
may be removed without first preserving these dependencies.
