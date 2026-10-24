# IQ3_XXS block-loop CPU delta proof

The first GNU CPU proof passes7,878,100 exact checks. It compares the unchanged
original decoder and lane implementation against the candidate, retaining exact
FP32 bits and complete BF16 outputs/statuses. Tests cover15 representative half
classes (including signed zeros, subnormals, infinities and NaNs), all16 group scales,
128 sign/parity codes, grid bytes, full640-row/top10 per-slot operation, nonzero row
starts, duplicates, invalid and zero routes, tails, and changed live inputs/weights.

This proves the synthetic CPU loop/decoder delta, not native compiler behavior or
public Device admission. No model bytes or GPU were used. The old complete Device
ABI proofs remain separate; a new native control/candidate comparison is required.

[CPU receipt](evidence/cpu-proof.json) binds the exact commands,37 dependencies,
23 reused GNU objects and retained binary. [Root review](evidence/cpu-root-review.json)
rechecks254 source hashes, dependencies, object hashes and binary, without rerunning
the same tests. Retained proof data totals4,898,103bytes. No tolerance or waiver was
used. The unchanged kernel source hash is
`99c32706cefe5a3cd850ed3ef74eb577e439335fd99fc1d9bb595c48ed718cff`;
CPU receipt SHA256 is
`210c2f3dd6bff2eceb81a968b50fac81e837a38f65d6bb9cf2e1c9ad75f7a68f`.

Next authenticate the fixed real slices and saved inputs, compile the bounded native
micro, and compare all output/status bytes with the control and saved original
baseline. Timing remains an isolated repeated-kernel diagnostic until full-engine
correctness and throughput are measured.
