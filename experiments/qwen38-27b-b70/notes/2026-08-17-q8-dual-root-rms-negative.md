# Qwen3.8 Q8 dual-RMS collective root

Date: 2026-08-17

Status: closed negative; do not repeat unchanged

This candidate tried to shorten both per-device handoff tails without repeating
the rejected mode-4 design that put rank 0's full multiply/quantize tail on the
root critical path. The existing device-0 reduction workgroup computed both
ranks' RMS sums in the accepted SIMD16/tid-strided order. Each rank then kept
its own multiply, graph-visible stores, and Q8 quantization kernel. The root
added one peer read of rank 1's residual but no new peer output write.

The final allocator-free revision used two dead-after-reduction rank-0 partial
slots for the scalar sums. Its `p64/n1/r1` safety gate completed normally with
1,980 verified Q8 buffers, zero mismatches, and no device or kernel fault.

The mirrored `p64/n128/r3` performance gate was decisively negative:

| Arm | Mean decode |
| --- | ---: |
| accepted control | `36.452554 tok/s` |
| dual-RMS root | `35.490563 tok/s` |
| delta | **`-2.639022%`** |

Both treatment positions lost. The extra root reductions lengthened rank 1's
dependency more than the shorter parallel tails recovered, confirming the
critical-path lesson from the broader mode-4 rejection. No endpoint or
semantic run was warranted. Accepted source/library were restored exactly and
both B70s remained normal.

An earlier prototype allocated a persistent two-float VMM-pool buffer. Compute
completed, but teardown asserted because the pool is stack ordered. That
allocation was removed before the measured revision; it was a host allocator
lifetime error, not a GPU fault.

- candidate source SHA-256:
  `206d2d68025bd78125429f45e1dbc5fa68d940363d4f9740c011efa96a045bec`;
- candidate library SHA-256:
  `8ce6464af767f944509e445eb125edd362d44a7b937d0c4fe26ce1da97ac24fb`;
- exact compressed increment:
  [`../patches/q8-dual-root-rms-negative-20260817.diff.gz.b64`](../patches/q8-dual-root-rms-negative-20260817.diff.gz.b64).
