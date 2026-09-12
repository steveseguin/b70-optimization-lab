# A344-A354: where the second verify row's 15.5 ms goes

Promoted Flash-Next TP4/EP4 lines, exact-2K rows, step timing (`Q38_STEP_TIMING_LOG=10`, median
target-forward ms over the logged decode steps of three rows). One block at a time replaced by
zeros via `Q38_DIAG_SKIP` (outputs change, so every skip arm's hash differs from the promoted
`afffd211…`; the same skip gives the same hash on both lines, e.g. hc_mix -> `6e84bd08…` on A353
and A354, which is the check that the switch engaged). Preregistration:
`2026-09-11-a344-a348-decomposing-the-second-verify-row-prereg.md`.

| block skipped | M=1 step (MTP0) | cost at M=1 | M=2 verify step (MTP1) | cost at M=2 | ratio |
|---|---|---|---|---|---|
| none (control) | 27.2 (A340) | | 42.7 (A343 42.73, A344 42.66) | | 1.57x |
| moe_gemm | 15.9 (A349) | 11.3 | 28.8 (A345) | 13.9 | 1.23x |
| gdn_attn | 24.8 (A350) | 2.4 | 31.5 (A346) | 11.2 | 4.7x |
| qsa_attn | 22.9 (A351) | 4.3 | 38.3 (A347) | 4.4 | 1.02x |
| hc_mix | 24.5 (A353) | 2.7 | 42.7 (A354) | 0.0 | - |
| sum of the four | | 20.7 | | 29.5 | |
| remainder (projections, norms, glue) | | 6.5 | | 13.2 | 2.0x |

A348 (hc_mix at M=2 on the unfixed head) and A352 (same at M=1) crashed on the injection-shape
assert and were superseded by the zero-injection fix (`0894c582`, MTP1 branch; `312d559f` on the
MTP0 branch).

## Reading

- The MoE grouped GEMMs are close to linear in rows (+2.6 ms for the second row): weight-bandwidth
  bound, as the roofline work already said. Not the lever.
- QSA is flat (4.3 -> 4.4): its cost is the KV read, and the second row reads the same KV.
- GDN is the super-linear block: +8.8 ms for the second row, 4.7x the single-row cost. The
  exactness selector `VLLM_XPU_GDN_SERIAL_SPEC_DECODE` runs the decode kernel once per verifier
  row and wraps each launch in index_select + contiguous copies of the inputs, index_copy of the
  outputs, per-call constant tensors, and the state copies between spec columns: about 14 extra
  device launches per layer per step on a card with a single compute queue.
- hc_mix reads as 2.7 ms at M=1 and nothing at M=2. Skipping it changes the accepted tokens, so
  the M=2 step population differs (n=156 vs 84 logged steps); the honest statement is that the
  hyper-connection mix is not where the second row's cost is.
- The remainder also doubles (6.5 -> 13.2). That is everything outside the four skipped regions:
  the dense projections around the attention blocks, norms, the sampler-side glue, and the
  all-reduces. The GDN skip zeroes the whole attention module including its projections and the
  serial path, so part of that remainder is the same launch-count story at M=2 elsewhere.

## Next

A355 (`2026-09-12-a355-serial-gdn-views-fast-path-prereg.md`): the single-request narrow-view fast
path for the serial rows, off by default (`VLLM_XPU_GDN_SERIAL_SPEC_DECODE_VIEWS=1`, overlay
`bbda09ae`). Prediction: M=2 step well below 42.7 with all rows at `afffd211…`. If a residual stays,
the follow-up is a two-row sequential decode kernel (one launch per layer that runs row 0 then row 1
with the state carried in registers) and a launch audit of the remainder at M=2.
