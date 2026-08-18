# Qwen3.8 Q8 attention-only crossed-DP4A experiment

Date: 2026-08-18

Status: closed performance-nonrepeatable; exact schedule experiment, not promoted

The exact global crossed DP4A schedule had improved a deep direct gate by
`0.758%`. Dense FFN and recurrent GDN isolation did not reproduce that gain,
so this arm applied the same integer-exact schedule change only to the fused
attention Q/V/K triple (`K=5120`, local `N=6144+512+512`). All other kernel
families, SG24 recurrent geometry, weights, equal TP2 split, F16 KV, and
FlashAttention remained unchanged. The default-off same-binary door was
`GGML_SYCL_MMVQ_Q8_ATTENTION_CROSS_DP4A=1`.

The strict shared-Q8 verifier completed `990/990` comparisons with
`VERIFY_MISMATCH=0`, but verifier level 2 disables the meta-backend fused
triple. Separately, a production-level TP2 `p0/n2` mechanism smoke announced
the exact treatment on both GPUs and counted 64 fused attention triples. This
keeps verifier correctness and live-treatment reachability separate rather
than overstating either. The integer reassociation preserves every packed
weight/activation pairing and the exact pre-scale sum.

Two complementary same-binary `p64/n512/r3` brackets produced:

| Order | Position | Arm | Decode tok/s |
| --- | ---: | --- | ---: |
| A-B-B-A | 1 | control | `36.676053` |
| A-B-B-A | 2 | treatment | `36.724722` |
| A-B-B-A | 3 | treatment | `36.848081` |
| A-B-B-A | 4 | control | `36.854342` |
| B-A-A-B | 1 | treatment | `36.866507` |
| B-A-A-B | 2 | control | `36.866627` |
| B-A-A-B | 3 | control | `36.705326` |
| B-A-A-B | 4 | treatment | `35.763641` |

The first block was only `+0.057674%`; the opposite block was `-1.280114%`.
Pooled means were `36.775587` control and `36.55073775 tok/s` treatment
(`-0.611409%`). Even excluding the final slow treatment process, the treatment
mean was only about `+0.10%`, still ordinary run noise. No endpoint or semantic
promotion gate was warranted.

Candidate identities: SYCL library
`fce0da8c9061293f4ea8c5b56cdcd880a9b7988c2b34a5ae5d344deee2813399`,
MMVQ object `2d5e9d7ae42663df581e95fcfa3ff20cf94106c217b31a72de76c879551c7f3b`,
and host llama-bench
`74e7d48905196285f6e7cd8c8d0b20a8e25cf3f4731b1e2f0f5f6c49ad8d8865`.
The exact patch is
[`q8-attention-cross-dp4a-nonrepeatable-20260818.diff`](../patches/q8-attention-cross-dp4a-nonrepeatable-20260818.diff),
and structured data is
[`2026-08-18-q8-attention-cross-dp4a-nonrepeatable.json`](../data/2026-08-18-q8-attention-cross-dp4a-nonrepeatable.json).
Raw logs remain in
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260818-attention-cross-dp4a/`.

Both GPUs passed the post-run health gate. No speculation, DFlash/MTP, peer
writes, profiler, PCI/power policy, driver, firmware, or kernel changes were
used.
