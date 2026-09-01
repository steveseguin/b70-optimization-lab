# Qwen3.8 Flash-Next FP8 GDN QKVZ dense graph screen

Date: 2026-09-01
Status: no exact component winner

The remaining prominent dense shape is the TP4-local fused GDN
`in_proj_qkvz`: BF16 `[1,2560] x [2560,4096]` in each of the model's 36
linear-attention layers. The screen used the real layer-0 rank-0 checkpoint
rows and the ordinary `F.linear` result as the per-input bit-exact authority.

Ordinary `mm`, `mv`, `matmul`, and `torch.compile` graph paths were all exact,
but remained at roughly `43 us` and offered no meaningful gain. Making the
transposed weight physically contiguous reduced replay to `22.486 us`, but
changed one BF16 result on the first sampled input. The existing Xe2 grouped
operator was only `2.978%` faster and also changed one result. A two-stream
split remained exact but slowed to `48.591 us`; the faster four- and
eight-stream forms changed one result.

oneDNN verbose output explains the split: the authority uses its transposed-B
catalog strategy while the packed weight selects a different N-layout
strategy, changing accumulation and rounding. No candidate advances under the
lossless rule. A credible future route is a purpose-built Xe2 skinny/T-layout
kernel for M1/N4096/K2560 that preserves the authority reduction order, not a
packed-layout substitution.

This component run emitted inline results rather than a separate evidence
folder. The pinned checkpoint/source/runtime identities, complete protocol,
and measurements are preserved in the
[structured result](../data/20260901-gdn-qkvz-dense-xpu-graph-screen.json).
