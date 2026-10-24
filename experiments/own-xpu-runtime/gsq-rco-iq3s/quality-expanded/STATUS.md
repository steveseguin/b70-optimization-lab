# Current expanded-quality status

The subsequent [dtype audit](../reference-cpu/RECURRENT-DTYPE.md) identifies
BF16 recurrent matrix storage where the reference usesF32. This run verifies
internal parity and task readback, not no-added-loss reference qualification.
State precision correction and an independent same-weight probe now take priority.

The [actual result](RESULT.md) independently passes all24 original prefixes,
12 full target/MTP pairs and54 state bundles on binary5aef. All twelve complete
retained texts were read and hash-joined to the closed index. Eleven answers
are capped and incomplete; one reaches EOS. Technical and unsupported-claim
cautions remain visible, and overall quality_qualified stays false.

Frozen historical preparation files retain their original no-inference wording
because the actual admission binds their exact hashes. They are preparation
evidence; this status and the actual result describe completed execution.
No broad-quality or public-speed claim is made.
