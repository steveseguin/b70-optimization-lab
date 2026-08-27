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
| Gemma 4 26B A4B | [Q8 one-B70 reconstruction](gemma4-26b-a4b-q8-b70/) |
| Laguna S 2.1 | [INT4 four-B70 record replay](laguna-s-2.1-int4-b70-125tps/) |
| LFM2.5 2.6B | [Q8_0 one-B70](lfm25-26b-q8-b70/) |
| MiniMax M2.7 | [AutoRound INT4 four-B70](minimax-m27-int4-autoround-b70/) |
| Muse-Glimmer 30B | [Q8/WOQ four-B70](muse-glimmer-30b-q8-woq-b70/) |
| Nemotron 3.5 Lightning 30B-A3B | [UD-Q4_K_M one-B70](nemotron-35-lightning-30b-a3b-b70/) |
| Ornith 1.5 35B-A3B | [Q4_K_M one-B70](ornith-15-35b-a3b-q4km-b70/) |
| Ornith 1.5 9B | [Q8_0 one-B70](ornith-15-9b-q8-b70/) |
| Qwen3.8 27B | [Q5_K_S 256K + vision + MTP one-B70](qwen38-27b-256k-vision-mtp-b70/) |
| Qwen3.8 27B | [official FP8 vLLM two-B70](qwen38-27b-fp8-tp2-b70/) |
| Qwen3.8 27B | [Q4_K_M one-B70](qwen38-27b-q4km-tp1-b70/) |
| Qwen3.8 27B | [Q8_0 one-B70](qwen38-27b-q8-tp1-b70/) |
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
