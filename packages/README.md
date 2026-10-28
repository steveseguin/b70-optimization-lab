# B70 Model Packages

This directory is the user-facing packaging layer over verified material in
`repro/`, `results/`, and `patches/`. A package is a small, machine-readable
front door: it names exact hardware, model, runtime, patches, commands,
evidence, and any remaining gates without duplicating their source of truth.
The `library` block supplies normalized discovery fields for the public guide
browser (family, quant, card count, OS, native/container delivery, use cases,
and either a promotion-grade measured metric or an explicit strict-benchmark
pending state). A candidate may use `featured_metric: null` plus a non-empty
`benchmark_status`; generators show the pending state and never fill it with a
diagnostic number. The `contributors` block records the exact work and
evidence carried into that package; upstream dependencies are not treated as
contributors unless a concrete contribution was adopted.

External submission additionally requires the
[hash-bound promotion attestation](../docs/promotion-attestation.md); a
performance-suite `passed` flag alone never authorizes publication.

An optional `performance_profiles` list carries measured curves. Each curve
names one metric (`decode`, `prefill`, `ttft`, or `aggregate_decode`), uses an
explicit measured x-axis (`context_tokens` by default, or
`concurrent_sequences`), links in-repository evidence, and contains at least
two ordered measured points. Aggregate curves may include `per_user_value` in
addition to their aggregate `value`. A package with only a headline omits the
list; the guide library then displays “sweep pending” instead of inventing a
curve.

A package status matters:

- `candidate`: useful on a matching expert-managed host, but one or more
  portability or clean-host gates remain;
- `starter`: clean-host replayed and eligible for an “Install guide” label;
- `preview`: intentionally unverified on the named platform, such as future
  Windows work.

Current packages (all are candidates; the linked manifest owns the exact
evidence and remaining gates):

| Family | Deployment packet |
| --- | --- |
| SC117 Flash-Next IQ3_S (separate mixed quantized model) | [Three/four-B70 dedicated-draft research recipe](sc117-iq3s-b70-research-draft-20261028/); expert candidate, portable dedicated launcher and certification pending |
| Flash-Next UD-IQ3_XXS (separate quantized model) | [Own Xe runtime, one B70](qwen38-flash-next-iq3xxs-ownrt-tp1-b70/) and [two B70 cards](qwen38-flash-next-iq3xxs-ownrt-tp2-b70/); full-512/prefill lab observations, quality promotion pending |
| Flash-Next FP8 | [Exact-GDN MTP1 four-B70 record replay](qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/) |
| Flash-Next FP8 | [MTP0 W13/N64 four-B70 retained recipe](qwen38-flash-next-fp8-tp4-mtp0-w13n64-b70-34tps-20260908/) |
| Flash-Next FP8 | [MTP1 four-B70 retained recipe](qwen38-flash-next-fp8-tp4-mtp1-lossless-b70-27tps-20260905/) |
| Flash-Next FP8 | [MTP1 host-placement four-B70 retained recipe](qwen38-flash-next-fp8-tp4-mtp1-placement-b70-32tps-20260906/) |
| Flash-Next FP8 | [MTP1 Triton hyper-connection four-B70 retained recipe](qwen38-flash-next-fp8-tp4-mtp1-hctriton-b70-37tps-20260907/) |
| Flash-Next FP8 | [MTP1 reference Triton kernels four-B70 retained recipe](qwen38-flash-next-fp8-tp4-mtp1-qsafused-b70-38tps-20260907/) |
| MiniMax-H3 | [Owner-approved Comfy-Org pruned BF16 video, two-B70 measured batch; rebuild incomplete](minimax-h3-pruned-bf16-tp2-b70-20261004/) |
| LTX 2.5 | [145-frame continuation video, four-B70 lab replay](ltx25-continuation-stream-b70-145f-20261010/) |
| Gemma 4 26B A4B | [Q8 one-B70 reconstruction](gemma4-26b-a4b-q8-b70/) |
| Laguna S 2.1 | [INT4 four-B70 record replay](laguna-s-2.1-int4-b70-125tps/) |
| LFM2.5 24B A2B | [Q8_0 one-B70, exact fast path](lfm25-24b-a2b-q8-b70/) |
| LFM2.5 2.6B | [Q8_0 one-B70](lfm25-26b-q8-b70/) |
| MiniMax M2.7 | [AutoRound INT4 four-B70](minimax-m27-int4-autoround-b70/) |
| Muse-Glimmer 30B | [Q8/WOQ four-B70](muse-glimmer-30b-q8-woq-b70/) |
| Nemotron 3.5 Lightning 30B-A3B | [UD-Q4_K_M one-B70](nemotron-35-lightning-30b-a3b-b70/) |
| Ornith 1.5 35B-A3B | [Q4_K_M one-B70](ornith-15-35b-a3b-q4km-b70/) |
| Ornith 1.5 9B | [Q8_0 one-B70](ornith-15-9b-q8-b70/) |
| Qwen3.5 4B | [W4A16 + native MTP one- or two-B70](qwen35-4b-w4a16-b70/) |
| Qwen3.5 9B | [FP8-dynamic + native MTP one-B70](qwen35-9b-fp8-b70/) |
| Qwen3.5 9B | [W4A16 + native MTP one- or two-B70](qwen35-9b-w4a16-b70/) |
| Qwen3.8 27B | [Q5_K_S 256K + vision + MTP one-B70](qwen38-27b-256k-vision-mtp-b70/) |
| Qwen3.8 27B | [official FP8 vLLM one-B70](qwen38-27b-fp8-tp1-b70/) |
| Qwen3.8 27B | [official FP8 vLLM two-B70](qwen38-27b-fp8-tp2-b70/) |
| Qwen3.8 27B | [AutoRound INT4 fixed-K two-B70](qwen38-27b-int4-fixed-k-tp2-b70/) |
| Qwen3.8 27B | [Q4_K_M one-B70](qwen38-27b-q4km-tp1-b70/) |
| Qwen3.8 27B | [Q4_K_M + Q4_0 MTP2 one-B70](qwen38-27b-q4km-mtp2-tp1-b70/) |
| Qwen3.8 27B | [Q4_K_M + Q4_0 MTP2 two-B70](qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/) |
| Qwen3.8 27B | [Q8_0 one-B70](qwen38-27b-q8-tp1-b70/) |
| Qwen3.8 27B | [Q8_0 + Q4_0 MTP2 one-B70](qwen38-27b-q8-q4mtp-mtp2-tp1-b70/) |
| Qwen3.8 27B | [Q4_K_M two-B70](qwen38-27b-q4km-tp2-asrock-b70/) |
| Qwen3.8 27B | [Q8_0 two-B70](qwen38-27b-q8-tp2-b70/) |

None is a starter package yet because its host platform path has not been
rebuilt and tested from a clean OS. Gemma additionally lacks the retained
historical server and local Q4_0 draft hashes, so it is explicitly a source
reconstruction candidate.

Package manifests are checked by `python3 tools/validate-repro-guides.py`.
The browser reads the generated [`catalog.json`](catalog.json), which must not
be edited by hand. After adding or changing a package, rebuild and validate it:

```bash
python3 tools/validate-repro-guides.py --write-package-catalog
```

The linked reproduction guide remains authoritative for technical details and
evidence; package files must point inward to it rather than becoming a second,
drifting recipe.
