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
