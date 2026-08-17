# Qwen3.8 27B Q8 TP2 register-direct collective tail workgroup

Date: 2026-08-17

Status: active; claimed before implementation.

## Hypothesis

At each of the 128 TP boundaries per generated token, the accepted path runs a
5,120-element register-direct residual/RMS/multiply/Q8 tail on each B70. The
tail currently uses the device maximum of 1,024 work-items: each thread visits
five RMS elements and 64 SG16 subgroups share 160 Q8 blocks. A smaller
workgroup may reduce scheduling and reduction overhead while retaining enough
parallel Q8 block ownership.

This is distinct from the closed `GGML_SYCL_COMM_REDUCE_WG` experiment, which
changed only the preceding elementwise cross-device root reduction and left
both RMS/Q8 tails unchanged. It is also distinct from the neutral five-element
loop-unroll experiment, which retained the 1,024-work-item geometry.

## Contract

- isolated same-binary runtime selector, defaulting to the accepted 1,024;
- admit only 256, 512, or 1,024 work-items for the exact 5,120-element
  register-direct path;
- retain tensor split, model, F16 KV, target-only execution and every promoted
  fusion;
- mechanism smoke with `VERIFY_MISMATCH=0` and post-run GPU health;
- position-balanced performance screen before endpoint work;
- because workgroup size changes the RMS reduction tree, any fixed-prompt or
  complete-suite output-hash difference is a hard rejection regardless of
  speed;
- retain 1,024 unless a candidate is repeatably faster and clears the full
  cache-zero output oracle plus semantic/long-context gates.
