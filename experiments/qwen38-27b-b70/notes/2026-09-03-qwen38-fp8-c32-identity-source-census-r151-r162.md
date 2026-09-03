# Qwen3.8 FP8 TP2: what flips near-tie tokens above 16 concurrent requests (R151-R162)

Date: 2026-09-02 evening to 2026-09-03 early morning, boot `2c230b44`

Status: **MTP0 source found and fixed (R156: output-identical c1-c64, 64/64, twice
reproduced). MTP1 residual not yet explained; every kernel-level candidate is
cleared. No public text changed by this note; the R156 promotion campaign
decides that.**

## Method

Operator censuses in the R139 image on one card, each comparing every
sequence's or row's result in a batched call against its single-sequence
call, bitwise, with repeat and permutation checks; then one preregistered
endpoint ladder per surviving hypothesis, ladders only (R63 configuration,
512-token budget, 64 sequential oracles, c1 to c64).

## Cleared at the operator level (bitwise invariant through 64 sequences)

| kernel or op | census | note |
| --- | --- | --- |
| GDN decode (states included), GDN prefill | R151a, R151c | |
| paged attention decode (both split plans) and prefill | R151a, R151e | |
| greedy argmax on planted exact ties | R151b | |
| two-rank all-reduce, 1 to 2048 rows | R151d | exact, repeat, prefix-invariant |
| gated RMSNorm (Triton) | R151e | |
| GDN spec path, uniform and mixed accepted counts, arbitrary slots | R158, R162 | |
| state-slot reuse (stale conv/SSM bytes) | R157 | ignored correctly |
| attention with prefill and decode rows in one call | R155 | exact |

## Found

| finding | census | effect at the endpoint |
| --- | --- | --- |
| vLLM ir `rms_norm`/`fused_add_rms_norm` (the Gemma layer norms, q/k norms): a row's bits depend on its slot in the batch | R151f | Triton route (R152/R153a2/R161) does not change the ladders; MTP0 is exact without it. Real, but not what flips tokens here. Costs 31% at c1 as an opaque op |
| **GDN kernel: decode rows computed on a different path when prefill rows share the call** (1 fp16 ULP in SSM state and output, every mix) | R155 | **splitting mixed steps into pure calls (R156) makes MTP0 exact through c64**; MTP1 unchanged |
| draft INT4 head row-invariant only to 8 rows | R159 | 8-row chunk (R160) does not change the MTP1 ladder |
| FP16 target head row classes at 33+ rows | R151/R149 | 32-row chunk does not change the ladders; MTP0 c64 exact with 64 rows |

Also negative: `max_num_batched_tokens` 2048 (R148), no static compile size
(R154).

## MTP1 residual

With the split, the draft-head chunk, and the Triton norm all active (R161),
MTP1 still misses 2/32 and 6/64 on near-tie prompts (`rollback-c010` token
97, `evidence-c015` token 77, and so on), while MTP0 on the same fixes is
64/64. The residual is therefore specific to speculative serving and not in
any censused kernel. Candidates not yet tested: the target's one-row versus
two-row verify grouping when acceptance differs between c1 and c32 for
reasons other than the draft head (the draft model's own forward at batch,
which shares every kernel above but runs its own FA/GDN cache), and the
rejection sampler's handling of bonus tokens at batch. Next census: run the
draft model forward alone (MTP module) at 1..64 rows and compare proposals
per request, before any further endpoint arm.

## Cost of the fix

R156 changes only how many kernel launches a mixed step issues; one-user
steps are never mixed, so c1 arithmetic and speed are unchanged by
construction. The R156 promotion campaign (`r156f`) measures it.

Evidence: `data/2026-09-0{2,3}-qwen38-fp8-*r15[1-9]*`, `*r16[0-2]*`; artifact
roots `/mnt/fast-ai/bench-results/qwen38-fp8-*-2026090{2,3}-r15*`.
