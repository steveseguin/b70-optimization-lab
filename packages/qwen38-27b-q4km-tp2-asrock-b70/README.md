# Qwen3.8 27B Q4_K_M TP2 candidate packet

This is the package front door for the measured two-card target-only lane:
`49.717503 tok/s` conventional decode, `173.574 ms` TTFT, 12/12 exact output
hashes, and cache zero on every request.

> **Candidate, not a beginner install guide.** The immutable model, complete
> source patch stack, build recipe, preflight, launcher, benchmark, and oracle
> are present. Platform installation, an in-guide model downloader, and a
> clean-host replay remain open.

Use the [full reproduction guide](../../repro/qwen38-27b-q4km-tp2-asrock-b70/README.md).
Its speed setting is target-only TP2 with F16 KV, graph off, and no draft model.
The optional large-batch prefill mode is measured separately and must not be
confused with the decode headline.

The packet retains the complete lab TP2 patch plus the Q4_K dense gate/up
SwiGLU increment. Both are default-off source paths with explicit runtime
doors and exact output gates. The model is the same pinned Qwen3.8 Q4_K_M
artifact as the one-card packet; the two-card result remains its own topology
and metric identity.

Additional measured profiles now cover exact 2K→32K native HTTP decode/TTFT
and output-audited 1→96-user HTTP aggregate decode. At exactly 32K the package
measured `44.437281 tok/s`; at 64 simultaneous users it measured
`175.623794 tok/s` aggregate with the default-off exact F16
`ffn_down,ffn_gate` cache. The two candidate servers measured `175.798577`
and `175.449010 tok/s`, each
matching the preregistered fixed-cohort token oracle 64/64 with prompt caching
disabled. Same-binary cache-off controls centered at `160.981046 tok/s`
(`+9.10%`); the result is `+4.45%` above the prior one-family cache record.

The later near-capacity c96 profile measured `192.350949` and `192.332958
tok/s`, for a qualified **`192.341954 tok/s`** center. Both fresh servers
matched a frozen same-shape c96 control-batch oracle 96/96. The requested 32K
pool was rounded by llama.cpp to 49,152 tokens (96x512), and peak used VRAM was
about 30.48/30.35 GiB per card. The separate sequential comparison was 50/96,
so this is candidate-vs-control identity and aggregate-capacity evidence—not a
batch-invariant-text claim.

The aggregate optimization retains the incumbent dequantized F16 bytes on each
device; the pair adds approximately 13 GiB of device memory per card and did not improve the
single-user MMVQ route. The `49.717503 tok/s` one-user headline therefore stays
unchanged. See the [qualified c64 result](../../experiments/qwen38-27b-b70/notes/2026-08-30-qwen38-q4km-tp2-exact-f16-cache-pair-c64-result.md) and the
[qualified c96 result](../../experiments/qwen38-27b-b70/notes/2026-08-30-qwen38-q4km-tp2-exact-f16-cache-c96-result.md), including patches,
preregistrations, hashes, memory samples, and strict runner.
