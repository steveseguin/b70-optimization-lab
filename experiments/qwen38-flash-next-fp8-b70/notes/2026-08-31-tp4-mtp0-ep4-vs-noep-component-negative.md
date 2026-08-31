# Qwen3.8 Flash-Next FP8 EP4 versus no-EP TP4 component result

Date: 2026-08-31
Status: bounded component negative; no full-model launch

The A28 endpoint profile identified routed/shared MoE rank imbalance and
collective arrival skew as the largest remaining target-decode opportunity.
Native vLLM without `--enable-expert-parallel` is memory-plausible on this
model: EP4 stores 128 complete 640-wide experts per rank, while no-EP stores
all 512 experts with a TP4-sharded width of 160. Both layouts retain exactly
600 MiB of routed FP8 weights per layer and rank. The existing source performs
a lossless 128-to-32 block-scale refinement for the 160-wide TP shard.

The component gate loaded the exact layer-0 checkpoint weights on all four
B70s, used one frozen top-10 expert fixture, and included the real four-rank
XCCL BF16 all-reduce of the 2,560-element output. Every layout produced one
hash across all four ranks and five repeats. The current EP4 control's
critical-rank median was `529.431 us`. Native no-EP TP4 was `487.898 us`, a
`7.845%` improvement. A twelve-configuration screen found a better no-EP
kernel (`M16/N64/K32`, eight warps, four stages), but its real-weight plus XCCL
critical median was still `484.110 us`, only `8.560%` ahead of EP4.

The no-EP result was repeatable but not byte-identical to EP4. Their reduced
outputs differed in 2,436 of 2,560 BF16 elements, with maximum absolute
difference `0.008789` and mean absolute difference `0.001305`. The tuned
kernel retained the same no-EP hash, so tuning did not add another numerical
change. No-EP also allocated a net 2,301,952 additional bytes for one layer,
dominated by scale refinement but offset by removal of EP's 2,048-byte expert
map. That observed net projects to 105.375 MiB/card over all 48 layers; the
refined scales alone add 105.469 MiB/card. This remains narrow relative to
A30's 128-MiB KV allocation.

This does not clear the deliberately conservative 15% component screen and
fails the stronger internal byte-parity screen. The 15% threshold was chosen
during analysis rather than preregistered, so it is recorded as a screening
rule rather than a formal statistical gate. Even under the best measured
configuration, the upside is too small and the numerical/memory risks are too
large to justify another 173-GiB endpoint load. Keep EP4 and all protected
`5.515783 tok/s` MTP0 and approximately `20.727 tok/s` MTP4 results unchanged.

The extended component tool now supports exact EP/TP checkpoint slicing,
fixed expert fixtures, four-rank XCCL timing, output capture, and per-rank JSON
receipts. Structured results and external evidence manifests are in
[`20260831-tp4-mtp0-ep4-vs-noep-component-negative.json`](../data/20260831-tp4-mtp0-ep4-vs-noep-component-negative.json).
