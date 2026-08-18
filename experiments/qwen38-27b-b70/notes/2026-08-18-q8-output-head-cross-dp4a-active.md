# Qwen3.8 Q8 output-head-only crossed-DP4A experiment

Date: 2026-08-18

Status: active and claimed on the reference two-ASRock-B70 host; not promoted

The exact global crossed two-chain DP4A schedule improved a deep direct gate by
`0.758%`, but isolated dense FFN, recurrent GDN, and fused attention arms were
negative, neutral, or non-repeatable. The last large reordered-Q8 consumer is
the standalone output head: `K=5120`, local `N=124160`, once per token on each
TP2 rank.

This arm changes only that exact output-head shape from the accepted striped
`0->2 / 1->3` DP4A chains to crossed `0->3 / 1->2` chains under a default-off
same-binary runtime door. Every packed weight word remains paired with its
original activation word and the same exact integer sum precedes the unchanged
FP32 scale/reduction. FFN, recurrent, attention, collectives, launch geometry,
weights, equal TP2 split, F16 KV, and FlashAttention remain unchanged.

The build stays under 6/8 GiB; model runs stay under 8/10 GiB and never overlap.
A production mechanism smoke must announce the output-head treatment on both
devices. The strict shared-Q8 verifier and live-treatment evidence will be
reported separately if verifier mode bypasses the target shape. Complementary
same-binary `p64/n512/r3` brackets precede any cache-zero endpoint gate.

No speculation, MTP/DFlash, peer write, profiler, PCI/power policy, firmware,
driver, or kernel changes are in scope. Any fault, mismatch, timeout, or memory
pressure stops the arm without promotion.
