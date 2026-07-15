# M=1 MHC post/pre plus RMSNorm fusion loss

## Outcome

The register-resident/on-chip M=1 MHC post/pre plus exact-geometry RMSNorm
candidate is closed before a four-GPU server run. It was both numerically
non-bitwise and slower than the existing two-command sequence.

The standalone probe is
`/home/steve/src/deepseek-v4-xpu-kernels-clean/tests/mhc/mhc_post_pre_m1_rms_probe.py`.
The preserved default-off experiment commits are vLLM `8bebe092f` and XPU
kernels `efebdae`.
It ran on one B70 with 40 changed input states, persistent output buffers, 100
warmups, 12 alternating A/B batches, and 200 calls per timed batch.

## Design tested

The existing fast MHC post/pre kernel uses 256 work-items with 16-wide
subgroups. Standalone H4096 BF16 RMSNorm uses 512 work-items with 32-wide
subgroups. The candidate used one 512-work-item kernel while preserving the
old 256 logical MHC lanes. It emulated each old 16-lane reduction inside one
half of a 32-lane subgroup, staged the rounded 4,096-element BF16 producer in
explicitly vector-aligned SLM, then used all 512 lanes for the RMS reduction.
This removed the global producer reread and the second launch without
quantizing unused data under the promoted selective-W8A16 configuration.

An independent source review caught and corrected two issues before the gate:
all 32 lanes now participate convergently in subgroup shuffles, and SLM uses a
16-byte-aligned BF16-vector accessor rather than reinterpreting a scalar BF16
accessor.

## Measured failure

- reference MHC post/pre plus standalone RMSNorm: `20.3255 us` median;
- fused candidate: `22.4271 us` median;
- regression: `2.1016 us` per boundary, or a projected `0.1786 ms/token`
  across 85 boundaries;
- speed ratio: `0.9063x`.

Across 40 changing cases, residual output was bitwise exact, but accumulated
mismatches were:

- post mix: 14 FP32 bits, maximum absolute error `2.3841858e-7`;
- comb mix: 309 FP32 bits, maximum absolute error `8.9406967e-8`;
- normalized BF16: 3 bits, maximum absolute error `7.6293945e-6`.

Fixed-address graph replay changed all four outputs after input mutation and
matched the reference for that graph case, so graph mechanics were not the
failure. SYCL does not promise an identical floating-point reduction tree
between the original subgroup-16 reduction and the emulated halves, and the
changed-state gate exposed that difference.

## Decision

Do not spend a TP4 load cycle on this implementation. A 256-lane approximate
variant might be faster, but cannot meet the exactness requirement and its
best plausible saving is below the major-win threshold. Preserve the guarded
operator and probe as negative evidence. Return to the 8-9 ms/token ordered
collective critical path, where eliminating producer operations or overlapping
the ring has a materially larger ceiling.
