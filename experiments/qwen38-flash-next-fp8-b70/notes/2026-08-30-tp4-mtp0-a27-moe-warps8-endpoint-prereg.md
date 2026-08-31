# Qwen3.8 Flash-Next FP8 A27 M4 MoE warps-8 preregistration

Date: 2026-08-30
Status: frozen; requires the next fresh boot

## Question

Does the exact real-weight M4 MoE `num_warps=8` component candidate improve
the TP4 target-only decode lane while retaining the complete short and
exact-4K quality, repeatability, and authority contract?

## Frozen identity and sole treatment

- checkpoint: `Qwen/Qwen3.8-Flash-Next-FP8` revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`, local NVMe artifact;
- vLLM: `d14396e27247c1b251da0ce24a0942772c4b002f`;
- kernels: `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`;
- staged runtime build: `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, eager, MTP0, synchronous selective PLE-only UVA, max length 4352;
- trace and async-PLE selectors absent; prefix caching absent; KV cache fixed at
  `134217728` bytes;
- sole treatment: `VLLM_TUNED_CONFIG_FOLDER` points to the tracked
  `configs/moe-warps8-m4` directory, whose one file has SHA-256
  `f93b5e1d5863e04268eb96877ab2ef6ba0990c42c62f1dff27bc36676c30bf7f`.

The map preserves the established entries for M1, M8, M16, M32, M64, and
M128. Only M4 changes `num_warps` from 4 to 8. Two real-weight component seeds
retained exact bytes for 100/100 repeats and reduced isolated latency by
20.20--21.14%. The projected 5.8--6.1 ms per 48-layer target step is an upper
bound, not an endpoint claim.

The launcher validates the exact config content before derivation and again
immediately before `setsid`. The client rejects any live async-PLE selector,
requires the exact tuned-folder environment, revalidates the config hash and
M4 entry, and requires the server's exact configuration-selection receipt.
The exact clean source head and staged-runtime-first `PYTHONPATH` gates remain.

Frozen tools:

- launcher SHA-256:
  `caf12747ccd194ce784c7f64f3bbd327ed63fbfc3d2a7b92d702e5162ec58e0f`;
- client SHA-256:
  `d3cb538d71f11423b8cc5f13a2ca9873fb9ad1cf1a654eaaa6ddac7f480cf68a`;
- supervisor SHA-256:
  `0baede0a853c984df8994fd4f18fe08eb1d0d97c9bafa67d2f79d9953c436b44`;
- attempt 27, port 19699, isolated cache/RPC/evidence paths.

## Gates and frozen interpretation

The inherited recovery canary, accepted 7-case semantic boundary, 16-repeat
check, exact-4K needle, three protected-hash short rows, two cache-zero
exact-4K authority rows, journal window, and clean teardown all remain exact.
No token count, seed, timeout, warmup, output authority, or assertion is
lowered.

- Any output, repeat, semantic, authority, or lifecycle failure is a bounded
  negative and changes no protected result.
- A quality pass with no meaningful short-decode gain does not promote the
  config.
- A quality pass with a short median above the protected `5.515783 tok/s`
  result makes A27 a speed candidate only. Causal promotion still requires a
  separately booted d143 synchronous-UVA/config-unset control and a fresh
  candidate repeat or control-candidate-control bracket.
- Exact-4K failure cannot by itself causally implicate M4 because the retained
  fresh-start variability is already localized first to zero-based layer-1
  GatedDeltaNet. It still prevents reliable/lossless promotion.

A26 consumed the current boot. The inherited one-load guard makes A27 the
first and only full Flash-Next load after the next reboot. Protected
`5.515783 tok/s` target-only and approximately `20.727 tok/s` MTP4 results
remain unchanged.
