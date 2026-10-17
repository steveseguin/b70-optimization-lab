# Initial CPU proof refusal

The first GNU CPU proof exited after six checks with `V1 adjacent tree`.
Original log: `../host-1792227901285011959-0/native.log`.

This was a test-harness defect. `iq3::tree32(float*)` reduces its argument in
place. The initial test passed its original logical-lane array to that helper,
then passed the already-reduced array to the virtualization model. Its first
all-zero case happened to survive; the next cancellation case exposed the
destructive call. A second call site in the routed-row tests had the same
defect, with an additional unspecified function-argument evaluation order.

The corrected test calls production reduction on a by-value array copy.
Neither expert kernels nor production arithmetic changed. This directory
retains the rejected source, both initial compiler build receipts, and the
failure log before those live receipts are replaced by corrected builds.

Rejected source SHA-256:
`e9a10386e62564306d9577a29dc479d6a76168c1084910b7651c29fe80893c39`

This is rejected preparation evidence, not an arithmetic or device result.
