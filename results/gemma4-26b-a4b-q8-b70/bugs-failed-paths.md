# Gemma 4 26B A4B Bugs And Failed Paths

No local Gemma 4 26B run has completed yet in this lane. Seed this file with
known risks so future agents do not start from a blank page.

## Known External Risks

- vLLM Gemma 4 MoE has a public issue for `--data-parallel-size > 1`; prefer
  four separate DP=1 servers for this lane.
- The 26B A4B MoE expert dimensions are reported by the vLLM Gemma 4 recipe as
  sensitive to 4-bit quantization. Treat W4A16 / INT4 AutoRound as a separate
  quality-risk lane, not the default.
- GGUF Q8 is large enough that KV headroom may be tight at 32K on a 32 GB B70.
  Establish small-context decode first, then walk context up.
- llama.cpp issue `#21893` reports B70/Gemma 4 nonsense output unless
  `GGML_SYCL_DISABLE_OPT=1` disables optimized SYCL reorder paths. This lane's
  launcher defaults to `=1`; any `=0` result needs repeat canaries before speed
  claims.

## Local Carryover Risks

- Qwen experiments showed that fast speculative and graph paths often pass a
  small smoke but fail at repeat depth. Do not promote Gemma results without
  repeated canaries.
- llama.cpp multi-GPU syntax uses slash-separated devices such as
  `-dev SYCL0/SYCL1`; comma-separated syntax can mean separate benchmark cases.
  This lane should avoid multi-GPU splitting until the single-GPU replica path
  is understood.
- Old llama.cpp/B70 notes include Level Zero device loss, allocation failures,
  and graph/DNN toggles that can change performance sharply. Preserve exact env
  vars for every run.
