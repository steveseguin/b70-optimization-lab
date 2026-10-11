# IQ3 line: the arithmetic authority is a frozen reduction order, not a BLAS call (2026-10-11)

**Finding.** The integrated program (stage 2 packet 4) reproduces the two-layer
synthetic mini-model bit-for-bit, but its real first-layer hidden-state hash
does not match the CPU oracle (packet2-cpu-oracle). The oracle computes its
matmuls with the pinned BLAS path; our runtime (and the packet 2 shared
header-only reference) uses a fixed, documented per-row reduction tree. Both
are "the exact arithmetic of the published weights" in the sense of using the
same bytes and FP32 accumulation, but floating-point summation order differs,
so the hidden states differ in low bits and the hashes cannot agree.

**Decision (coordinator, under the owner's rule "lossless relative to what it
is").** A BLAS library's blocked summation order is an implementation detail of
one CPU library build; it is not reproducible across machines and cannot be
implemented on the GPU. The model's arithmetic identity for this lane is
therefore defined as the documented reduction order of our runtime's shared
reference (packet 2 `kernels` header, mirrored by the device kernels), with the
rounding points stated in stage2/packet1b. The CPU oracle must compute with
that same order. Token ids from the BLAS-order oracle remain useful information
(argmax is robust to low-bit differences) but are not the gate; per-layer
hidden hashes are the gate only once the oracle uses the frozen order.

**Consequence.** After the running oracle job finishes its token-level pass,
re-base the oracle's matmul on the frozen reduction order (slower on CPU; use
the packet 2 reference implementation directly), regenerate the layer-1
fixtures, and only then run the packet 4 first-layer device gate. Any later
change to the reduction order (for example kernel optimization round 1's
subgroup tree) changes the identity and requires regenerating the oracle
fixtures; the receipts must pin the order version.
