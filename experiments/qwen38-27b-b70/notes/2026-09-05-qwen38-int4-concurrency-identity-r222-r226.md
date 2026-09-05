# INT4 concurrency identity on the fixed-K kernel: R222-R226 (2026-09-05)

Directive: lossless for concurrent users on TP1 and TP2 at MTP depths 0-3. Method: the r152 c1-c64 identity ladder
(each concurrency level's complete token streams vs a sequential oracle), TP2, 128 output tokens, short prompts.

| run | image / switches | MTP0 ladder | MTP4 ladder |
|---|---|---|---|
| R216 (old kernel, r213b) | plain-GPTQ oneDNN W4A16, Python pad | c2 exact, c4 3/4 ... c64 59/64 | same pattern |
| R222 (R221 fixed-K, pad off) | two-tier fixed-K W4A16 | exact through c32, c64 63/64 | c2 exact, c4 3/4, c8-c32 exact, c64 59/64 |
| R225 (R224) | + FP16 linears in <=32-row pieces, FA serial env | exact c1-c16, c32 31/32, c64 64/64 | c4 exact, c8 7/8, c16 exact, c32 31/32, c64 60/64 |
| R226 (R224) | + `VLLM_BATCH_INVARIANT=1` (single-split flash-decoding) | **exact c1-c64** (998 tok/s at c64) | **exact through c16**, c32 30/32, c64 59/64 |

Strict gates on R221/R224 at TP2: G1/G2/G3 12/12 at depth 4; MTP0 35.5/36.2, MTP4 68.6/68.2 tok/s.

## What each step fixed

1. The fixed-K W4A16 kernel (R221) removed the GEMM's row-class dependence: identity went from c2 to c32.
2. The FP16 oneDNN GEMM behind `lm_head` and `mtp.fc` keeps the single-row class only to 32 rows (census
   2026-09-05: `in_proj_a/b` invariant at every M, `mtp.fc`/`lm_head` change class at 33+). R224 runs every
   unquantized XPU linear in <=32-row pieces inside an opaque custom op: MTP0 c64 63/64 -> 64/64.
3. Flash-decoding picks `num_splits` from a batch-size heuristic; `VLLM_BATCH_INVARIANT=1` forces one split:
   depth 4 c8 7/8 -> 8/8, exact through c16.
4. `VLLM_XPU_FA_SERIAL_SPEC_DECODE=1` never engaged (no "reached" marker); inert here.

## The residual

The same near-tie prompts flip whenever batch composition changes at c32+ (benchmark-c003 at token 60, cache-c016 at
75, capacity-c006 at 11, capacity-c046 at 18, rollback-c018, testing-c061), for MTP0 (c32 31/32 on R225) and MTP4
(c32 30/32, c64 59/64). Every INT4 GEMM, every FP16 linear and the attention decode are now batch-invariant, so the
remaining batch-dependent kernel is in the GDN path (`gdn_attention_core_xpu`: one launch for all sequences of a step;
the FP8 lane traced its own c32/c64 residual to the same place and published MTP1+ "exact through c16"). This lane now
matches that bar for depth 4 and exceeds it for MTP0 (**exact at every concurrency c1-c64**, R226). Next: a kernel-level census of `_xpu_C.gdn_attention`
per-sequence output vs number of sequences (needs the real metadata layout), during the R227 TP1 phase on GPU 1.
