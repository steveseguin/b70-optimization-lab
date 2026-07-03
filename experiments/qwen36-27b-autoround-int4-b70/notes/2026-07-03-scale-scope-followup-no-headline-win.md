# 2026-07-03: scale/scope follow-up after BF16-scale record

## Purpose

After promoting the webhie INT8 LM-head BF16-scale record, run one bounded
same-window screen before moving to deeper source work:

- reconfirm all-head BF16-scale control on two GPUs;
- test `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=fp16`;
- test `VLLM_XPU_LM_HEAD_INT8_SCOPE=target` with BF16 scales as a possible
  service/max-context variant.

All rows used the strict Qwen realistic suite: 12 unique prompts, each prompt
once, `cached_tokens=0`, token-id timing, chat mode with thinking disabled,
`qwen3_next_mtp` k=3, XPU graph cg8, and the webhie AutoRound checkpoint.

## Results

| Row | GPU | Env delta | Median tok/s | p10 | Mean | TTFT med ms | Verdict |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| all-head BF16 control | 0 | `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16` | 64.97114546627634 | 56.1853356120153 | 63.89194995211529 | 607.4999539414421 | control, below record |
| all-head BF16 repeat | 3 | `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16` | 64.73813406443224 | 58.046736810857496 | 64.30636404301636 | 609.2169946059585 | control, below record |
| FP16 scales | 1 | `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=fp16` | 62.9017535577475 | 59.05412293466671 | 62.78957611876073 | 607.6816041022539 | no-win |
| target-only BF16 | 2 | `VLLM_XPU_LM_HEAD_INT8_SCOPE=target`, `...SCALE_DTYPE=bf16` | 64.79993379987856 | 58.86799218461141 | 64.34482159133508 | 519.1574285272509 | service candidate, not a record |

Artifacts:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-control-gpu0-continue-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T230404Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-repeat-gpu3-continue-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T230404Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-fp16scale-gpu1-continue-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T230404Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-targetonly-gpu2-continue-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T230404Z.json
```

## Interpretation

The promoted BF16-scale all-head record remains the headline control:
`65.27648650325429 tok/s`, with earlier support rows at `65.005` and `64.864`.
The same-window repeats here landing at `64.97` and `64.74` are consistent with
normal Qwen27 variance and do not invalidate the promoted best, but they confirm
that future sub-1% deltas need paired/crossover validation.

FP16 scale storage is worse than BF16 scale storage and should not be retested
without a new numerical or kernel reason.

Target-only BF16-scale is not a headline throughput record. It was within about
`0.7%` of the all-head BF16 controls in this window and had much lower median
TTFT (`519 ms` vs `607-609 ms`), but the follow-up quality gate FAILED repeat
stability:

```text
data/qwen36-27b-autoround-int4-b70-baselines/quality-webhie-int8lmhead-bf16scale-targetonly-repeat32-ctx1024-20260703T230755Z.json
```

Quality details:

- exact cases: pass;
- long-context 1K needle: pass;
- baseline comparison: `baseline_match_all=true`;
- repeat32 stability: fail at repeat index 9 (`blue, green, red` instead of
  the dominant `blue, green, red, yellow`).

Do not promote the webhie BF16-scale target-only service variant without a new
quality/stability fix. The older Intel-checkpoint target-only artifact remains
useful as attribution evidence, but target-only is not universally safe across
the current webhie/BF16-scale lane.

## Source Hygiene

The active vLLM stack now also registers the LM-head experimental environment
variables in `vllm/envs.py` to avoid unknown-env warnings:

- `VLLM_XPU_LM_HEAD_INT8`
- `VLLM_XPU_LM_HEAD_INT8_SCOPE`
- `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE`

Patch snapshot:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-active-stack-with-lmhead-bf16-scale-env-registered-20260703.patch
```

SHA256:

```text
900eb93ed12d4784fce21d22d48e2ddf90c4ed6a5ba8e8de646889bcd1b3100d
```

`python3 -m py_compile vllm/envs.py vllm/model_executor/layers/vocab_parallel_embedding.py`
passed in `/home/steve/src/vllm`.

## Next

The config/scope branch is closed for headline decode. Continue with the
structural LM-head/verifier bottleneck:

- new XPU op or kernel path for INT8 LM-head top-1 / candidate-vs-max that
  avoids materializing `[rows, vocab]` logits;
- or a verifier design that only computes the logits actually needed for target
  acceptance and bonus-token ownership while preserving exact target-model
  verification semantics.
