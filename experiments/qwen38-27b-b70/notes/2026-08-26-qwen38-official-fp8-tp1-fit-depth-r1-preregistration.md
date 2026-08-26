# Official Qwen3.8 FP8 TP1 bounded fit/depth R1

This packet never starts or resumes the model download. The fixed target is
`/mnt/usb-models/llm-models/qwen3.8-27b-fp8-official-017b9c7`, exact revision
`017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`. At preregistration it contains
13 files and about 2.4 GB; the publisher manifest requires 66 weight files and
30,866,866,928 bytes. Default checks remain inert and report readiness only.

Explicit verification first requires every weight at its exact expected size.
It then hashes every complete file through strict O_DIRECT and repeats every
full-file SHA-256 through ordinary reads. Both views must match the publisher
manifest and each other. There is no direct-I/O fallback in this campaign.

After verification, the one-card target-only/eager lane attempts fresh service
lifetimes at 8K, then 4K, then 2K. The first successful lifetime measures its
exact depth and every smaller depth. An 8K fit therefore yields three Grade-C
cells; a 4K fit after 8K failure yields two; a 2K-only fit yields one. Explicit
fit failure at 2K closes this exact official-FP8 TP1 tuple as unsupported at
2K and above. Unclassified failure remains inconclusive, and correctness or
receipt failure after boot publishes no cells.

The runtime is the audited immutable XPU nightly image
`f01e24f6...eab1ba4f`, vLLM `0.27.2rc1.dev77+gac7509e2b`. This is a bounded
coverage lane, not permission to replace any historical speed or headline.
