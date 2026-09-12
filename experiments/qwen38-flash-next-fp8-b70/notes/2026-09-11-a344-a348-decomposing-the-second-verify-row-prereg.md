# Preregistration: A344-A348 - which block pays for the second verify row?

## Question

A343: the promoted MTP1 line's two-row verify forward is 42.7 ms against 27.2 ms for one row
(A340), +15.5 ms. Which block scales super-linearly at M=2 today? On the 09-03 line (A124/A125,
eager) the excess was MoE (2.6x) and the serial verifier-row GDN path (2.5x), with HC and QSA at
1.25x; the line has since gained headroom placement, Triton HC glue, the fused QSA pre-indexer
and the W13 maps.

## Arms (graph MTP1, promoted packet A338, three exact-2K rows each, step timing on)

All on the MTP1 diagnostic head with the skip switches ported (`q38-mtp1-promoted-diag-20260911`).
Each skip is a timing-only no-op (outputs are garbage by construction and are not compared):

- **A344 control**: no skip. Must reproduce A343 (42.7 ms, `afffd211…`); it is the reference for
  the arms below because they share its head.
- **A345** `Q38_DIAG_SKIP=moe_gemm`: the two Triton grouped GEMMs are not launched.
- **A346** `Q38_DIAG_SKIP=gdn_attn`: linear-attention modules replaced by zeros.
- **A347** `Q38_DIAG_SKIP=qsa_attn`: full-attention (QSA) modules replaced by zeros.
- **A348** `Q38_DIAG_SKIP=hc_mix`: hyper-connection combine/mix removed.

## What is read

The M=2 forward median per arm; block cost at M=2 = control - skipped. Where the same skips were
measured at M=1 on the old line (A145/A148: MoE ~50 ms of 72.7), the M=2/M=1 ratio per block is
the verdict; the block whose removal shrinks the +15.5 ms most is the kernel target.

## Predictions

- MoE: on the M=1 promoted line the MoE GEMMs are the bulk of 27 ms; if they still run per-row at
  M=2 the moe_gemm arm shrinks the step by ~2x the M=1 saving.
- GDN: the serial verifier-row path (VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1) runs the decode kernel
  once per row; expected ~2x its M=1 cost.

## Stop rules

- A344's outputs != `afffd211…`: the ported skip code changed the default path; stop.
- Any arm fails to become healthy: stop and follow the post-fault rule.
