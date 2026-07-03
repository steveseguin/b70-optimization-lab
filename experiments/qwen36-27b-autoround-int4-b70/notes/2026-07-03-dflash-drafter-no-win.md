# 2026-07-03: DFlash drafter compatibility and k sweep

## Why

After the internal `qwen3_next_mtp` path hit a verifier/LM-head bottleneck and
the EAGLE3 compressed drafter proved unstable or too slow, DFlash was the next
target-verified external-drafter candidate. The goal was to improve accepted
tokens per target forward without using warmed continuation history or any
cache/reuse shortcut.

## Source / Model Card Facts

Model:

```text
z-lab/Qwen3.6-27B-DFlash
/mnt/fast-ai/llm-cache/hf/manual/z-lab--Qwen3.6-27B-DFlash
```

Local files:

- `model.safetensors`: `3460432504` bytes;
- `config.json`: `1135` bytes.

Config facts:

- architecture: `DFlashDraftModel`;
- model type: `qwen3`;
- tensor type: BF16;
- hidden size: `5120`;
- layers: `5`;
- vocab size: `248320`;
- sliding window: `2048`;
- `dflash_config.mask_token_id=248070`;
- `dflash_config.target_layer_ids=[1, 16, 31, 46, 61]`.

The model card says this drafter must be used with target
`Qwen/Qwen3.6-27B` and warns that inference-engine support may not be complete
because of architectural changes including causal/interleaved SWA layers. It
also recommends a temporary vLLM install from PR `40898` for interleaved SWA and
correct target-hidden-state handling. Our local vLLM tree already contains
DFlash model/proposer support, so this test was a local compatibility sweep
against the Intel AutoRound INT4 target.

## Run Setup

Common setup:

```bash
cd /home/steve/llm-optimizations
DRAFTER=/mnt/fast-ai/llm-cache/hf/manual/z-lab--Qwen3.6-27B-DFlash
QWEN36_27B_ENABLE_MTP=0
QWEN36_27B_ENABLE_XPU_GRAPH=1
MAX_MODEL_LEN=2048
MAX_NUM_BATCHED_TOKENS=1024
MAX_NUM_SEQS=1
GPU_MEMORY_UTILIZATION=0.90
VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1
VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0
VLLM_EXTRA_ARGS='--speculative-config {"method":"dflash","model":"...","num_speculative_tokens":K}'
scripts/run-qwen36-27b-autoround-vllm-candidate.sh
```

All promoted/valid rows below used the fixed Qwen realistic suite in chat mode,
one cold response per prompt, `cached_tokens=0` on every prompt, and streamed
token IDs for the tokens-1-100-after-TTFT primary metric.

## Results

| Variant | Status | Median tok/s | p10 tok/s | Mean tok/s | Median TTFT | Notes |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| k=8, cg8 | pass/no-win | `49.994` | `42.859` | `51.256` | `2043 ms` | first compatibility pass |
| k=8, cg16 | pass/no-win | `47.408` | `40.832` | `48.623` | `2025 ms` | same-window control for higher-k sweep |
| k=10, cg16 | pass/no-win | `48.279` | `41.030` | `58.128` | `2417 ms` | mean inflated by fast rows; median below record |
| k=12, cg16 | pass/no-win | `47.771` | `45.434` | `48.662` | `2912 ms` | no record threat |
| k=15, cg16 | invalid/crash | n/a | n/a | n/a | n/a | `UR_RESULT_ERROR_DEVICE_LOST` before readiness |

Result files:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-dflash-k8-cg8-compat-realistic128-chat-tokenids-qwensuite-20260703T121501Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-dflash-k8-cg16-realistic128-chat-tokenids-qwensuite-20260703T121956Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-dflash-k10-cg16-realistic128-chat-tokenids-qwensuite-20260703T121956Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-dflash-k12-cg16-realistic128-chat-tokenids-qwensuite-20260703T121956Z.json
```

k=15 crash run directory:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-dflash-k15-cg16-realistic128-chat-tokenids-qwensuite-20260703T121956Z
```

Crash signature:

```text
RuntimeError: level_zero backend failed with error: 20 (UR_RESULT_ERROR_DEVICE_LOST)
Engine core initialization failed
```

## Acceptance Observations

DFlash acceptance falls off sharply after the first few drafted positions on
the realistic suite. Representative k=8/cg8 intervals:

```text
Per-position acceptance rate:
0.881, 0.524, 0.310, 0.095, 0.071, 0.048, 0.048, 0.048
Avg Draft acceptance rate: 25.3%
```

Representative k=10/cg16 intervals:

```text
0.833, 0.548, 0.357, 0.190, 0.048, 0.048, 0.048, 0.000, 0.000, 0.000
Avg Draft acceptance rate: 20.7%
```

The drafter can propose many tokens cheaply, but the accepted positions beyond
roughly the third token are sparse enough that the extra draft overhead does
not beat the internal MTP3 promote-source recipe.

## Decision

DFlash is closed no-win for the current Intel AutoRound INT4 target and local
vLLM/XPU runtime:

- it is valid and fresh-response clean at k=8/10/12;
- it does not beat the conservative BF16-LM-head strict record (`53.522 tok/s`)
  or the later runtime INT8-LM-head variant (`62.628 tok/s`);
- k=15, the model-card-style high draft length, device-losses before readiness;
- the model-card caveat about PR `40898` remains relevant, so this result should
  not be interpreted as a general DFlash failure on all runtimes or target
  precisions.

Future revisit conditions:

1. local vLLM gains or is rebased onto the DFlash/SWA PR path the model card
   recommends;
2. a stock BF16 `Qwen/Qwen3.6-27B` control is needed to separate AutoRound
   quantization mismatch from runtime limitations;
3. a DFlash quantized or compressed drafter appears that improves TTFT and
   draft cost without reducing target quality.
