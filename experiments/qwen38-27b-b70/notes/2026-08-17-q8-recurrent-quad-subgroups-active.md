# Qwen3.8 27B Q8 TP2 recurrent-quad workgroup population

Date: 2026-08-17

Status: active; SG16 candidate claimed on the reference ASRock host

## Hypothesis

The accepted hardware-derived policy groups eight SG16 subgroups (128 work
items) per fused recurrent GDN-quad workgroup. This quad is launched 192 times
in the diagnostic decode trace and accounts for `19.456 ms` of device time.
The prior shape-scoped subgroup experiment changed only the dominant FFN
pair/down families and tested SG4; it did not touch this recurrent quad.

This trial changes only the recurrent-quad workgroup population from the B70
default SG8 to SG16 (256 work items). Each output row still belongs to one
SG16 subgroup, uses the same Q8 DP4A body, accumulates the same blocks in the
same FP32 order, and uses the same subgroup reduction. The candidate changes
only how independent row subgroups are packed into workgroups.

## Contract

- retain target-only equal TP2, F16 KV, FlashAttention and `b1024/ub256`;
- keep the fixed-shape door off; this isolates launch geometry from the closed
  compiler specialization;
- admit only the observed recurrent local shape
  `K5120/N5120+3072+24+24`;
- retain SG8 in the same binary as the default control;
- announce the SG16 branch on both devices and require
  `VERIFY_MISMATCH=0` before timing;
- use fresh-process, position-balanced direct-decode screens;
- proceed to the full cache-zero endpoint and quality oracle only if the
  performance gain repeats;
- any output-hash or semantic mismatch is a hard reject.

Other hosts should not duplicate this exact SG16 recurrent-quad arm while the
note remains active.
