# Qwen3.8 Q8 TP2 R1A: invalid transport attempt

R1A completed the fixed twelve-prompt suite at a diagnostic class-balanced
median of 36.769596 tok/s with `cached_tokens=0` on all rows. It is **not a
benchmark claim**.

The accepted llama.cpp build did not expose generated token IDs through its
OpenAI-compatible `/v1/completions` stream. All twelve rows therefore recorded
zero streamed token IDs, freshness validation failed, and the promotion gate
rejected the run before canaries. R1B was deliberately not run.

The preserved raw evidence is under
`../data/qwen38-q8-tp2-strict-reasoningoff-20260827-r1a/`. The R2 transport
amendment uses llama.cpp's native `/completion` endpoint with the exact same
raw suite prompts and `return_tokens=true`; it does not add a chat template or
change the model, runtime, cache policy, sampling, or metric.
