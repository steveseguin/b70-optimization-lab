# Qwen3.8 Q8 attention-only crossed-DP4A experiment

Date: 2026-08-18

Status: active and claimed on the reference two-ASRock-B70 host; not promoted

## Why this arm

The exact global crossed two-chain DP4A schedule improved the complementary
deep direct gate by `0.758%`. Shape isolation has since ruled out dense FFN
(`-0.1046%`) and recurrent GDN (`+0.0993%`, inconsistent bracket signs) as the
source of a repeatable gain. The fused attention Q/V/K triple is the remaining
high-frequency family: 49,184 launches in a completed `p64/n512/r3` census.

This experiment applies the same exact crossed schedule only to the full
attention triple (`K=5120`, local `N=6144+512+512`). Dense FFN, recurrent GDN,
output head, collectives, model weights, equal TP2 split, F16 KV,
FlashAttention, and launch geometry stay unchanged.

## Contract and gates

The treatment will be selected by a default-off same-binary runtime door.
Every packed weight word remains paired with its original activation word;
only the two exact `int32` DP4A chains change from `0->2 / 1->3` to
`0->3 / 1->2` before their unchanged exact sum and FP32 scale.

1. Reflink the checksum-verified accepted DP4A2/SG24 source and build into an
   isolated path.
2. Compile only the affected MMVQ object/device image under the 6/8 GiB cap.
3. Require a TP2 mechanism smoke to announce the exact attention shape on both
   devices, with no verifier mismatch where the verifier can retain the fused
   path.
4. Run complementary same-binary position-balanced `p64/n512/r3` brackets.
5. Run the fixed cache-zero endpoint oracle only for a repeatable direct gain
   outside ordinary run noise.

No speculation, MTP, DFlash, peer writes, profiler, PCI/power policy, firmware,
driver, or kernel setting is in scope. Any device fault, timeout, host-memory
pressure, or quality mismatch stops the arm without promotion.
