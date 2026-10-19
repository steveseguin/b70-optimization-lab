# Packet165 two-card result: warm 512-token prefill 75.9–76.0 tok/s; decode 58.56–58.63 tok/s with the full strict-512 gate (two fresh loads)

Two fresh loads on lane B (cards 2+3), using the bundle-8 identity (packet136 engine, unchanged arithmetic): `packet165-two-card-full512-B-a` (07:01–07:08 UTC) and `-B-b` (07:09–07:15 UTC). No GPU faults (count 2).

| Run | 512-token prefill (warm runtime, cold prompt) | TTFT | Decode (primary metric, full 512 cap) | Realistic final gate | Oracle-covered tokens |
| --- | ---: | ---: | ---: | --- | --- |
| a | **75.97 tok/s** | 6.739 s | 58.632 | passed | exact |
| b | **75.88 tok/s** | 6.747 s | 58.557 | passed | exact |

**Prefill definition:** 512 input tokens / request TTFT. The prompt is the first 512 tokenizer IDs of one unrepeated real-document excerpt, with no special tokens and `cached_tokens=0`. The request runs after one warm-up request on a **different** suite prompt and a full reset, with no prompt, KV or response reuse. TTFT excludes model load and the reset. It is not HTTP TTFT, and no isolated device prefill phase is exposed by this build.

This replaces packet163's cold-first 7.8 tok/s reading, which was dominated by the ≈ 60 s first-request cost.

**Context:** prefill currently processes one token at a time. packet165's `BATCHED-PREFILL.md` prices exact batching at roughly 120–180 tok/s for 2-token batches and up to ~720 tok/s for 8-token batches, depending on the batchable fraction. Packet166, a causal M=2 full-layer micro, measures the deciding ratio.

Evidence: `experiments/own-xpu-runtime/stage2/packet165-warm-prefill/two-card/evidence/device-warm512-B-{a,b}/bracket-summary.json`.
