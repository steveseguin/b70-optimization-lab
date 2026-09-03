# Qwen3.8 Flash-Next FP8 A65 in-server GDN inner-trace result

Date: 2026-09-02 20:22--20:40 EDT
Status: diagnostic positive; first differing operation localized; no
promotion claim; protected results unchanged

## Outcome

A65 (A64 identity at overlay head `c027fe2d...`, trace settings exported
under the `Q38_` aliases and verified in the server environment) loaded in
13 minutes, served, and reproduced the jitter: eight identical 8-token
prefills returned the same top token with a top-1 logprob spread of 0.2377
nats. All four ranks wrote three captures each (`gdn-trace-rank{r}.{0,1,2}.json`,
79 records per capture, positions 0-7). Comparison
(`tools/compare-q38-repeatability-trace-captures.py`, receipt
`gdn-trace-comparison.json`):

| rank | records identical across the 3 captures | first differing record | tensors |
| --- | --- | --- | --- |
| 0 | 5 of 79 | `layer_0_gdn_in_proj` | `hidden_states`, `qkvz`, `ba` |
| 1 | 8 of 79 | `layer_0_gdn_out_proj` | `out` |
| 2 | 8 of 79 | `layer_0_gdn_out_proj` | `out` |
| 3 | 8 of 79 | `layer_0_gdn_out_proj` | `out` |

Captures 0 and 2 are byte-identical on every rank and every record; capture
1 is the deviant. `model_positions` and `model_input` (embedding output,
replicated) match on all ranks and captures.

On ranks 1-3 the GDN input projection, the core kernel output (`core_attn_out`,
`z`), and the gated RMSNorm output are byte-identical across all three
captures; their first difference is the output projection, whose result is
the TP all-reduce of the four ranks' partial products.

On rank 0 the `hidden_states` entering layer 0's GDN already differ in
capture 1. That tensor is the output of the layer-0 attention
hyperconnection mix applied to the identical `model_input`: a BF16 oneDNN
GEMM with K = 10240 (hc_count 4 x hidden 2560) at M = 8. Its first six
elements are equal across captures, so the deviation is sparse. Rank 0's
differing GDN partial then changes the all-reduce sum, which is why ranks
1-3 first differ exactly at the reduced output projection (their own inputs
matched), e.g. element 4 of `out` is -0.00577 in captures 0 and 2 and
-0.00583 in capture 1 on every rank. Every later record differs on all ranks.

## Reading

Within one healthy server, the first non-repeatable operation on the 8-token
prefill path is a K=10240 BF16 dense GEMM in the hyperconnection mix, not
the GDN kernel, its norm, the PLE path, the MoE, QSA, or the collective
library (the all-reduce merely propagates one rank's differing partial).
This is the same family and mechanism the BF16 deterministic census
(A3/A4a) measured natively at M=1: `hc_down_inject` and `final_hc_down`,
the K=10240 down-projections, varied across sweeps, and
`torch.backends.mkldnn.deterministic=True` made all 14 dense families exact
within and across fresh processes at a multiplicity-weighted cost ratio of
0.986. It also matches the 2026-08-30 A24/A25 fresh-start pair (first
difference at the layer-1 attention output with the PLE path exact): the
mix GEMM before the attention block is where the two starts parted.

The flag was rejected on 2026-09-02 as a global replacement because its
stable result differed from every native sweep. For an operator that has no
single native result, a stable rounding is the only possible authority; the
endpoint test decides whether it is also lossless in the quality battery.

## Next

A66: the A65 server identity with overlay commit adding
`VLLM_XPU_MKLDNN_DETERMINISTIC=1` (sets `torch.backends.mkldnn.deterministic`
in every XPU worker's `init_device`), no trace, and the logprob probe at
depths 8/64/256/2048. Exact first steps and identical repeats at every depth
would make this the first logit-exact TP4 server and the base for a
promotable battery.
