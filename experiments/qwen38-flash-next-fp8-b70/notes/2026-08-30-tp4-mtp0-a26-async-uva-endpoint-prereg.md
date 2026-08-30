# Qwen3.8 Flash-Next FP8 TP4 MTP0 A26 async-UVA endpoint preregistration

Date: 2026-08-30
Status: frozen; requires the next fresh boot

## Question

Does the component-exact XPU async-UVA PLE candidate improve the trace-off TP4
target-only lane while retaining the complete short and exact-4K quality and
repeatability contract?

## Frozen identity

- checkpoint: `Qwen/Qwen3.8-Flash-Next-FP8` revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`, local NVMe artifact;
- vLLM: `d14396e27247c1b251da0ce24a0942772c4b002f`;
- kernels: `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`;
- staged runtime build: `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, eager, MTP0, text-only, one request stream, max length `4352`;
- selective rank-local UVA only for
  `ple_embedding.ngram_embedding.weight`, `12.0 GiB` budget;
- `VLLM_XPU_PLE_UVA_PREFETCH=1`, verified from the live server environment;
- trace disabled, prefix caching disabled, KV cache fixed at `134217728` bytes;
- all other target/runtime selectors inherited from A25.

The launcher injects the async selector after the base launcher's environment
scrub. The client rejects a server whose live `/proc/<pid>/environ` does not
contain the exact selector and staged-runtime-first `PYTHONPATH`, or contains
either trace-file selector. The launcher repeats the clean vLLM-head check
immediately before `setsid`; the client checks it again after health. The
candidate source rejects graphs, process-worker PLE, non-XPU execution,
disabled/non-UVA offload, missing selective placement, and multi-PLE layouts.

Frozen tools:

- launcher SHA256:
  `30228163b05a5150db1bc3326fab079c7a31241d05d7143ce04159702989e1be`;
- client SHA256:
  `3c5ebbf7182fe6bfb8c516f2f75e83d749dc98d18b9c3885330b4e9024e5e7d0`;
- supervisor SHA256:
  `082c41949dd050fd6c1d95a0e3f8374df03f4f6b98ebbab432c80153b55ebcd8`;
- attempt `26`, port `19698`, isolated cache/RPC/evidence paths.

## Gates and interpretation

The inherited recovery canary, 7-case semantic battery, 16-repeat check, exact
4K needle, three short timing rows, and two byte-identical exact-4K rows all
run. Short and exact-4K authority hashes are unchanged. The supervisor passes
only if the client summary records the async selector, the inherited semantic
boundary is accepted (7/7, or 6/7 with only the established
`code_execution=30` miss), both exact-4K rows agree with each other and the
retained authority, cached tokens remain zero, and teardown is clean.

- A full pass makes this a candidate reliability/speed positive; a separately
  started matched control is still required before attributing a speed delta.
- Any output/hash/quality difference is a bounded negative and changes no
  protected result.
- A clean quality pass with no meaningful speed gain preserves the component
  result but does not promote the endpoint selector.
- Infrastructure failure before inference is not a model result.

The current boot already contains A25's full model load. The one-load-per-boot
guard correctly rejects A26 here; A26 is the first and only Flash-Next full
load after the next reboot. Protected `5.515783 tok/s` target-only and
approximately `20.727 tok/s` MTP4 results remain unchanged.
