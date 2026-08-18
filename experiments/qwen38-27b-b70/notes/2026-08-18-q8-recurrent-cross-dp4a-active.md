# Qwen3.8 Q8 recurrent-only crossed-DP4A experiment

Date: 2026-08-18

Status: active and claimed on the reference two-ASRock-B70 host; not promoted

## Why this arm

The exact global crossed two-chain DP4A schedule improved the complementary
deep direct gate by `0.758%`. A new shape-selective experiment then showed that
crossing only the dense FFN gate/up and down projections was slightly negative
at `-0.1046%`. The global gain therefore originated outside dense FFN, or from
an interaction outside it.

The promoted recurrent GDN quad is the highest-frequency remaining fused Q8
MMVQ family: the completed `p64/n512/r3` processes counted 147,552 quad launches
versus 49,184 attention triples. This experiment isolates the exact crossed
schedule to that recurrent quad and leaves all other families striped.

## Treatment

The runtime door `GGML_SYCL_MMVQ_Q8_RECURRENT_CROSS_DP4A=1` changes only the
exact promoted local recurrent shape:

- `K=5120`;
- `N=5120+3072+24+24`;
- processed GDN quad;
- promoted 24 x SG16 workgroup geometry retained.

Every packed weight word remains paired with its original activation word.
Only the two independent exact integer chains change from `0->2 / 1->3` to
`0->3 / 1->2`; the unchanged integer sum still precedes FP32 scaling and
subgroup reduction. The model, weights, tensor split, F16 KV, graph,
collectives, and floating-point operation order do not change.

No speculation, MTP, DFlash, cache reuse, peer write, profiler, PCI policy,
power-management setting, firmware, driver, or kernel setting is involved.

## Gates

1. Reflink the checksum-verified accepted source/build into an isolated path.
2. Recompile only the changed `mmvq.cpp` object and run the BMG device link
   inside the 6/8 GiB build limit.
3. Require a TP2 `p0/n1` verifier smoke to announce the exact recurrent shape
   on both devices and end at `VERIFY_MISMATCH=0`.
4. Run a same-binary, position-balanced `p64/n512/r3` bracket with production
   verifier settings.
5. Run the fixed cache-zero endpoint oracle only if the direct result clears
   ordinary noise, then record, close, commit, and push the result.

Any Xe fault, reset, hang, timeout, device-lost event, host-memory pressure, or
quality mismatch stops the arm without promotion.
