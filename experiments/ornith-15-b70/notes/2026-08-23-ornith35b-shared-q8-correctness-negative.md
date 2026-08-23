# Ornith 1.5 35B-A3B: shared recurrent Q8 input

Date: 2026-08-23 EDT

Status: **CLOSED CORRECTNESS NEGATIVE — do not retain Q8 scratch across projections**

Ornith's 30 recurrent layers reuse the same contiguous FP32 `attn_norm`
activation in four quantized projections: QKV, gate, alpha, and beta. This is a
real Qwen-derived transfer opportunity. Stock SYCL MMVQ quantizes that input to
Q8_1 separately for each projection, so sharing one quantization could remove
three launches per recurrent layer, or 90 launches per decoded token.

The candidate matched only the exact one-token Ornith shapes, names, source
identity, quant types, layouts, one-device weights, and reordered MMVQ path. It
retained one graph-scoped 69 KiB allocation, split into 30 per-layer Q8 slices.
The final diagnostic routed the prequantized input through the complete stock
multi-device/MMVQ wrapper; only the quantization source changed.

The correctness gate failed before timing:

| Arm | Output SHA-256 |
| --- | --- |
| accepted six-optimization stack | `d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c` |
| shared Q8, QKV only | `29fc65b4e67ba6d584ba7fb3baf55af049a062ad213c1a41b829216ddf0a9acb` |

The QKV-only diagnostic fired 1,778 times before the changed generation ended;
there was no downstream reuse involved. Restoring stock weight-reorder order,
device-address resolution, stream selection, output stitching, and MMVQ
dispatch did not restore the canonical output. The earlier four-projection
form also diverged (`abff4a...`) and therefore provides no performance evidence.

The first implementation additionally retained one VMM-pool allocation per
layer and aborted at teardown because that pool requires reverse allocation
order. The graph-scoped allocation fixed the lifetime defect, but not the
numerical result.

Do not benchmark or publish this design. A future attempt needs a backend-level
proof that the exact stock Q8 bytes can be safely retained, rather than a
parallel quantization call into longer-lived scratch. The rejected complete
stack is preserved as
`../patches/llamacpp-ornith15-complete-shared-q8-correctness-negative-20260823.patch`;
the public package remains unchanged.
