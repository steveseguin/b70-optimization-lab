# 2026-06-01 OpenAI Serve Quality Fix

Goal: make the REAP MiniMax M2.7 AutoRound W4A16 checkpoint usable through
`vllm serve` before doing more decode optimization.

## Problem

Offline `LLM.chat` quality could pass, but the OpenAI server path returned token
id `0` / NUL output. The failure reproduced with:

- preserved fast cache `f728d2c0cf`
- current cache root
- `--no-async-scheduling`
- `--enforce-eager`
- tool/reasoning parsers disabled
- `--generation-config vllm`

A logprobs request made the failure clearer: the server tried to serialize
`nan` logprobs, so the token id `0` output was a sampler symptom of NaN logits,
not a tokenizer or response-parser problem.

An attempted `SamplingParams.skip_clone` deep-copy probe did not fix the issue
and was reverted from the live vLLM source.

## Root Cause

`serve.sh` inherited several older MiniMax promoted-env settings that the
quality harness explicitly clears or overrides:

- `VLLM_MINIMAX_M2_ATTN_DELAY_ALLREDUCE=0`
- `VLLM_MINIMAX_QK_RMS_XPU_HELPER=1`
- `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT=1`

The passing quality harness instead uses delayed attention all-reduce and leaves
the Q/K helper and restore-weight experiments off by default. Aligning the serve
defaults to that quality-safe bundle fixed OpenAI server output.

## Changes

- `scripts/serve.sh`
  - preserves user overrides for the MiniMax attention/QK toggles
  - defaults `VLLM_MINIMAX_M2_ATTN_DELAY_ALLREDUCE=1`
  - defaults `VLLM_MINIMAX_QK_RMS_XPU_HELPER=0`
  - defaults `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT=0`
  - keeps the repaired 192-expert logits workspace path opt-in
  - keeps parser/tool/generation-config controls for isolated testing
- `scripts/openai-quality-smoke.py`
  - added endpoint smoke test
  - replaced the short sentinel default with long canary prompts
  - validates `message.reasoning` when the MiniMax reasoning parser moves text
    there instead of `message.content`

## Validation

Eager OpenAI server, 2K context:

- artifact:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/openai-quality-smoke-qualityenv-eager-ml2048-20260601T050148Z.json`
- result: `passed=true`, no NUL/control output

Compiled OpenAI server, 32K context:

- artifact:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/openai-quality-smoke-qualityenv-graph-ml32768-20260601T050633Z.json`
- result: `passed=true`, no NUL/control output
- new compiled cache key: `b234935ae7`
- new AOT artifact:
  `c6b129b47a7bce6e1ac7bb116707a25b30df10f84ae3be4497d3f4c95e1b992f`

Endpoint throughput, compiled OpenAI server, 32K context, `p512/n1536`:

- artifact:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-qualityenv-graph-p512n1536-r2-20260601T050839Z.json`
- mean output throughput after first chunk: `82.05 tok/s`
- mean total throughput: `107.15 tok/s`
- mean client TTFT: `393.17 ms`
- mean vLLM TTFT: `391.65 ms`
- observed VRAM: about `32.56 GiB` per B70

This is below the archived offline `89.499 output tok/s` result, but it is the
first quality-clean OpenAI server path for REAP after the NaN/NUL issue.

## Next Work

- Ablate the three serve-env differences one at a time:
  - delayed attention all-reduce
  - Q/K RMS helper
  - Q/K norm restore-weight
- Keep any speed win only if the OpenAI quality smoke and logprobs probe stay
  clean.
- Benchmark the winning serve bundle with the standard p512/n1536 decode shape
  and record both endpoint and offline numbers.
- If a graph cache is promoted, pin its cache key and AOT hash in `REPRO.md`.
