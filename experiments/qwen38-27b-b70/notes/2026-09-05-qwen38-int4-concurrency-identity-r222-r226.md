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

## Afternoon screens R227-R237 and the final configuration (16:30)

| run | change | MTP4 ladder (c4 / c16 / c32 / c64) | MTP0 ladder |
|---|---|---|---|
| R227 | R224 + batch-invariant, depth 1 | exact / exact / 29/32 / 59/64 | - |
| R229 | R228: GDN spec rows grouped by 16 (marker confirmed) | exact / exact / 30/32 / 59/64 | - |
| R232 | + Inductor `split_reductions=false` | exact / exact / **31/32** / **63/64** | exact c1-c64 |
| R233 | spec grouping off | exact / exact / 31/32 / 57/64 | c64 63/64 |
| R234 | spec group 4 | exact / 15/16 / 32/32 / 60/64 | c32 31/32 |
| R235 | spec group 1 (per sequence) | 3/4 / exact / 31/32 / 61/64 (c64 aggregate 332 vs 432 tok/s) | exact c1-c64 |
| R237 | R236: GDN prefill launches per prompt | 3/4 / exact / 31/32 / 58/64 | c64 63/64 |

Reading: `split_reductions=false` is a real fix (four of the six flipping prompts cleared). GDN launch grouping is not
a lever: the gather/scatter split path is not arithmetic-equivalent to the plain launch (benchmark-c003@60 flips
whenever its batch goes through it), and per-sequence launches cost a quarter of the c64 throughput. The MTP0 ladder,
whose configuration never changed across R232-R237, is all-exact in three runs and one miss (c32 or c64) in three
others: arrival timing decides how the first prefill steps mix, and one composition-dependent kernel remains in the
mixed-prefill regime (GDN). Final configuration for the matrix (R239): R228 image + `VLLM_BATCH_INVARIANT=1` +
`split_reductions=false` + spec group 16 (`data/2026-09-05-qwen38-int4-final-config.env`). Package
`packages/qwen38-27b-int4-fixed-k-tp2-b70` registered (validator clean) with the R226 MTP0 c1-c64 and R232 depth-4 c1-c16
identity-qualified profiles; image on GHCR (`vllm-openai-xpu-qwen38-int4@sha256:aaf920b0...`, private until flipped).

## R239 matrix, first TP1 result (18:46)

TP1 (one card, no all-reduce), final configuration: MTP0 pair 32.960/32.945 tok/s G1 12/12; depth 1 49.640/49.468,
G2/G3 12/12, probe exact; depth-1 ladder exact through c8, c16 15/16 (benchmark-c003), c32 30/32, c64 60/64
(aggregate 393 tok/s at c16). The residual is identical in kind without any collective, so the oneCCL all-reduce is
excluded as a source; single-card decode is within 5% of TP2 (33.0 vs 34.2-35.6 MTP0; 49.6 vs 50.1-51.1 depth 1),
consistent with the launch-overhead-bound profile.

## R239 matrix complete (20:11): TP2 and TP1, depths 0-4, final configuration

Data `data/2026-09-05-qwen38-int4-r239-matrix-result.json`; tables in `repro/qwen38-27b-autoround-int4-b70/README.md`.

| | TP2 | TP1 |
|---|---|---|
| MTP0 pair | 34.21 / 35.64 (G1 12/12) | 32.96 / 32.95 (G1 12/12) |
| depth 1 | 51.10 / 50.09 | 49.64 / 49.47 |
| depth 2 | 61.14 / 61.54 | 56.51 / 56.45 |
| depth 3 | 67.61 / 67.83 | 58.47 / 58.47 |
| depth 4 | 68.55 / 67.79 (R240) | 56.29 / 56.25 |
| gates | every pair 12/12 vs each other and vs the MTP0 oracle; depth-1 probe exact | same |
| MTP0 ladder | exact c1-c64 in 3 of 4 (998.6 tok/s at c64); one run c32 31/32, c64 63/64 | exact c1-c64 in 3 of 4 (447.6 at c64); one run c64 63/64 |
| speculative ladders | exact through c16 at every depth (one run c8 7/8); c32 30/32; c64 58-60/64 | exact through c8; c16 15/16 (depth 3: 16/16); c32 29-31/32; c64 60-62/64 |

Turnover: depth 4 on two cards (68.2), depth 3 on one card (58.5). One card is within 5% of two at a single request.
The residual is the same without a collective, so the all-reduce is excluded; what remains is the GDN kernel's
composition dependence, most visible with speculative rows and at c32+.

## Residual mechanism from the kernel source (20:50)

`VLLM_XPU_GDN_NATIVE_SPEC_MULTI_REQUEST_SPLIT` is a launcher pass-through with no implementation in the library (R241
screen cancelled). The r35/r50 source says what the normal speculative GDN kernel does: all verifier rows of a launch
are carried in one work-group, and the state transaction can alias adjacent speculative cache columns physically; the
serial-exact lanes (`VLLM_XPU_GDN_NATIVE_SPEC_{CONV,RECURRENT,DELTA}_SERIAL_EXACT`) replay every verifier row through
the ordinary one-token kernels with an explicit source-row snapshot, but are gated to exactly one pure-spec request
(`num_spec_decodes == 1`). Every launcher sets them to 0, so c1 and c32 both used the batched kernel. Next: generalize
the serial-exact lanes to N requests (R242 kernel-library patch) and screen the ladders with them on.

## R242/R243 and the argmax census (21:45): what the residual is not

R242 (`patches/vllm-xpu-kernels-qwen38-gdn-serial-exact-n-requests-r242-20260905.patch`, image
`qwen38-int4-gdn-serial-n-r242` 9634a783, `_xpu_C` 06e3ae6c) generalizes both serial-exact GDN lanes from one pure-spec
request to N: every verifier row of every request is replayed through the ordinary one-token conv and recurrent
kernels with the source-row snapshot. R243 (lanes engaged on both ranks): depth-4 ladder exact through c16, c32 31/32
(rollback-c018@123), c64 60/64 (cache-c016@75, rollback-c018@77, monitoring-c036@41, capacity-c046@18) at a third of
the throughput (c16 174 vs 517 tok/s). A planted exact-tie argmax census on XPU returns the first index at every batch
size 1-320 in fp16 and fp32. So the residual is not the W4A16 GEMM, not the FP16 linears, not attention splits, not
Inductor reductions, not the GDN speculative arithmetic or state transaction, not the all-reduce (TP1 identical), and
not argmax tie-breaking. What is left: (a) position-in-buffer dependence inside a kernel (gathering rows into a
contiguous buffer changes results even for a single request, R235/R237 c4 flips), (b) the XE2 prefill chunk-scan
batched across prompts in the first mixed steps (would explain the MTP0 timing residual), (c) something outside the
censused kernels. The decisive next step is the lab's boundary-trace method: dump per-layer hidden states for a
flipping prompt at c1 and at c32 from the same server and find the first op whose bits differ. This image has no trace
hooks (the older lane's `VLLM_XPU_*_TRACE_FILE` switches are not in r156-derived images); adding one inside the GDN
custom op and after each decoder layer is a Python patch, but the compiled graph must be split at those points, which
changes the arithmetic it measures. That trade-off is the next design decision.
