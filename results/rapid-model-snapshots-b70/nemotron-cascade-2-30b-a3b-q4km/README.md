# Nemotron-Cascade-2-30B-A3B Q4_K_M Rapid Snapshot

Audience: benchmark readers and future optimizers who need a strict one-B70
llama.cpp baseline for Nemotron-Cascade-2-30B-A3B on Intel Arc Pro B70.

## Status

- Model: `bartowski/nvidia_Nemotron-Cascade-2-30B-A3B-GGUF`
- Original model: `nvidia/Nemotron-Cascade-2-30B-A3B`
- Model family note: hybrid attention/Mamba MoE model; the official config
  reports 30B total parameters, 3B active parameters, 52 layers, 128 routed
  experts, 6 experts/token, 1 shared expert, and 2 KV heads.
- File: `nvidia_Nemotron-Cascade-2-30B-A3B-Q4_K_M.gguf`
- HF revision: `931b595fc71b7ca14fb9d935af011f69f7c0434c`
- Local path:
  `/mnt/usb-models/llm-models/nemotron-cascade-2-30b-a3b-gguf/nvidia_Nemotron-Cascade-2-30B-A3B-Q4_K_M.gguf`
- File size verified: `24725740992` bytes
- Runtime: llama.cpp SYCL / Intel Level Zero, one Intel Arc Pro B70
- Source snapshot recorded by the runner: `/home/steve/src/llama.cpp`
  `fdb1db877c526ec90f668eca1b858da5dba85560`, clean at run time
- Result status: strict-valid rapid snapshot. This is a useful expected
  performance row for the Nemotron-Cascade family, not a frontier-speed row.

## Headline Strict Row

Use the standalone `ctx=2048` confirmation. It was the best clean repeat, but
the quick screen showed only sub-percent movement across all tested knobs, so
do not over-interpret the exact micro-ranking.

- Evidence:
  `data/rapid-model-snapshots-b70/nemotron-cascade-2-30b-a3b-q4km-llamacpp-faon-cacheoff-ctx2048-confirm-realistic128-20260704T235714Z.json`
- Raw run directory:
  `/mnt/fast-ai/bench-results/rapid-model-snapshots-b70/runs/nemotron-cascade-2-30b-a3b-q4km-llamacpp-faon-cacheoff-ctx2048-confirm-realistic128-20260704T235714Z`
- Primary metric: `50.90422891211857 tok/s` median generated-token throughput
  for tokens 1-100 after TTFT
- p10: `50.87692021463055 tok/s`
- mean: `50.895997279462044 tok/s`
- full after-TTFT median: `50.78920508048189 tok/s`
- wall-clock full-output median: `43.11903319272486 tok/s`
- TTFT median: `449.1593260318041 ms`
- Prompt cache: disabled at the server (`--cache-ram 0`) and per request
  (`{"cache_prompt":false}`)
- `cached_tokens=0` on all `12/12` prompts
- `realistic_final_gate.passed=true`
- LocalMaxxing: approved as `cmr7128uq00jdmn01dn0uttm7`.

## Quick Screen

All rows below used the same strict rapid realistic suite, one cold response per
prompt, server prompt cache disabled, per-request `cache_prompt=false`, and
`cached_tokens=0` on every request. The variants were run across the four B70s
to compress wall time; promoted rows still come from standalone strict runs,
not synthetic/repeated prompts.

| Label | Median tok/s 1-100 after TTFT | Result |
| --- | ---: | --- |
| `ctx2048-confirm` | `50.90422891211857` | promoted standalone |
| `poll25-ctx2048` | `50.856293784698224` | no material win |
| `threads12-ctx2048` | `50.838267693508485` | no material win |
| `ub512-ctx1024` | `50.83017137381361` | no material win |
| `poll100-ctx2048` | `50.8048271561332` | no material win |
| `b512-ctx2048` | `50.79901348426901` | no material win |
| `ctx2048` | `50.775306767545416` | standalone support |
| `threads4-ctx2048` | `50.76776961605512` | no material win |
| `ub512-ctx4096` | `50.75260067786769` | no material win |
| `ctx1024` | `50.73945988841308` | no material win |
| `ctx4096` | `50.730541899355686` | strict-valid baseline |
| `ub512-ctx2048` | `50.70570595655513` | no material win |

Conclusion: the easy quality-preserving knobs were flat. `ctx=2048` is a small
short-context fit improvement over `ctx=4096`, but the practical lesson is that
this GGUF lands around `50.7-50.9 tok/s` on one B70 under the strict fresh
suite.

## Reproduce

```bash
cd /home/steve/llm-optimizations

MODEL=/mnt/usb-models/llm-models/nemotron-cascade-2-30b-a3b-gguf/nvidia_Nemotron-Cascade-2-30B-A3B-Q4_K_M.gguf \
MODEL_ALIAS=nemotron-cascade-2-30b-a3b-q4km \
LABEL=nemotron-cascade-2-30b-a3b-q4km-llamacpp-faon-cacheoff-ctx2048-confirm-realistic128 \
GPU_INDEX=0 PORT=19740 \
CTX_SIZE=2048 BATCH_SIZE=1024 UBATCH_SIZE=256 POLL=50 THREADS=8 \
FLASH_ATTN=on CACHE_TYPE_K=f16 CACHE_TYPE_V=f16 \
MAX_TOKENS=128 METRIC_TOKENS=100 \
scripts/run-rapid-llamacpp-realistic-candidate.sh
```

The runner defaults to server prompt cache disabled (`--cache-ram 0`) and
per-request prompt cache disabled (`{"cache_prompt":false}`). Do not remove
either for headline claims.

## Validity

This row uses the shared rapid realistic suite:

- `repro/rapid-model-snapshots-b70/realistic-suite-v1.json`;
- one cold response per prompt;
- `temperature=0`;
- no speculation, no n-gram/history acceleration, no response reuse;
- no context checkpoints;
- server and per-request llama.cpp prompt cache disabled;
- `cached_tokens=0` for every request.

The benchmark uses streamed text/reasoning deltas for token timing because
llama.cpp does not provide vLLM-style streamed token IDs here. The promoted row
emitted enough streamed deltas for the 100-token metric window. Output previews
were normal prose, with no visible `<think>` leakage and zero reasoning deltas.

## Notes For Future Work

- The official model card describes vLLM support with `--trust_remote_code`,
  `--reasoning-parser nemotron_v3`, and `--mamba-ssm-cache-dtype float32`, but
  the rapid lane used llama.cpp because GGUF setup was already calibrated and
  sufficient for a first strict snapshot.
- The official instruct-mode note says to prepend `<think></think>` at the
  assistant response start when forcing instruct mode. The llama.cpp `--jinja`
  + `--reasoning off` path produced clean non-thinking outputs in the strict
  suite, so no manual ChatML override was needed for this row.
- Treat Q5/Q6/Q8 variants as separate quality/performance rows if downloaded
  later. Q4_K_M fits one B70 comfortably enough for this short-context suite,
  but the hybrid/Mamba footprint leaves less slack than smaller MoE GGUFs.
- Useful source references:
  - <https://huggingface.co/nvidia/Nemotron-Cascade-2-30B-A3B>
  - <https://huggingface.co/nvidia/Nemotron-Cascade-2-30B-A3B/blob/a33e221952f0b9c30423526177d4abf258e42487/config.json>
  - <https://huggingface.co/bartowski/nvidia_Nemotron-Cascade-2-30B-A3B-GGUF>
