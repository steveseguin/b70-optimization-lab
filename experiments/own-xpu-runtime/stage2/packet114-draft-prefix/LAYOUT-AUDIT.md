# Prefix layout and arithmetic

The only arithmetic-facing changes are the new name `p114-80128` in the draft
selection parser and row-count lookup. `p56::restrict_matrix` changes rows/span;
`restrict_argmax` changes only its input extent. The Q6 row stride remains 3,380
bytes (3,200 addressed code/scale bytes), and each row uses the unchanged p33
reduction. The inherited round2 argmax keeps its lower-token-ID tie rule and
never reads the excluded suffix. No target kernel changes.

Full-size allocation is 27,986,860,116 bytes on rank0 and 31,581,735,626 on rank1
for either view. The unchanged arena admission passes, with at least 1.5 GB
reserved. Real driver residency remains unmeasured. Every switch preserves
allocation IDs, addresses, extents and weight descriptors. CPU captures prove
that the target command bytes do not change and the draft restores exactly to
fresh control/candidate captures. Poisoned miniature state resets byte-for-byte.

The CPU capture audit additionally registers `capacity` and `shapes` members
already present in inherited operations. This fixes an audit refusal, not a
model arithmetic change. The exact source delta is in `native-overlay.patch`.

KD's bounded draft-only host process allocates 4,571,734,986 numerical device
bytes in the payload/backend mock for either prefix, below the 8 GiB bound.
Its selected draft choices and row count match the corresponding resident path.
