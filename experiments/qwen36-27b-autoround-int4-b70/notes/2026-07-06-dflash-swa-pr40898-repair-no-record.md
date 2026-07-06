# 2026-07-06 - DFlash SWA PR40898-style repair, still no record

Status: **closed repaired-but-no-record** for the current Qwen27 B70 lane.

## Why this was reopened

The earlier DFlash closure was based on the local default/full-attention
compatibility path and a crude mixed sliding/full attention attempt. A later
review found upstream vLLM PR #40898:

```text
https://github.com/vllm-project/vllm/pull/40898
```

The important idea in that PR is not a speed trick. It fixes the DFlash draft
architecture contract:

- DFlash uses sliding-window compute for sliding layers, but target-context
  K/V is prewritten into draft KV cache, so SWA layers need full-size KV cache
  allocation rather than eviction-sized SWA allocation.
- Context slot mapping should be keyed by layer name / layer type, not only by
  a single KV group assumption.
- Sliding draft layers need causal/sliding metadata while the full layer uses
  the non-causal draft metadata.

That was a credible reason to retry DFlash once. The old local mixed-SWA
attempt showed catastrophic acceptance around `1.1`, which could have been a
plumbing bug rather than real draft weakness.

## Patch tested

Preserved patch:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-dflash-pr40898-swa-repair-no-record-20260706.patch
```

Local source files touched:

```text
/home/steve/src/vllm/vllm/model_executor/models/qwen3_dflash.py
/home/steve/src/vllm/vllm/v1/spec_decode/dflash.py
```

Patch summary:

- adds a `DFlashAttention` wrapper that returns a full-size KV cache spec for
  sliding-window DFlash layers while preserving sliding-window compute;
- adds `VLLM_XPU_QWEN3_DFLASH_LAYER_TYPES=auto` so the local draft config uses
  the checkpoint's real layer-type list instead of forcing every draft layer to
  sliding attention;
- maps target-context slot mappings by draft layer name when available;
- builds per-layer attention metadata so sliding draft layers use causal
  metadata and the full draft layer keeps non-causal metadata;
- keeps the patch as an experiment artifact only. It is not part of the
  current promoted Qwen27 record stack.

Syntax check:

```bash
cd /home/steve/src/vllm
/home/steve/.venvs/vllm-xpu/bin/python -m py_compile \
  vllm/model_executor/models/qwen3_dflash.py \
  vllm/v1/spec_decode/dflash.py
```

## Validity policy

All rows below used the fixed realistic Qwen27 suite as a **diagnostic**
fresh-response screen:

- 12 unique chat prompts, each sent once;
- `cached_tokens=0` on every request;
- no prompt/KV/cache/history/response reuse;
- streamed token IDs used for generated tokens 1-100 after TTFT;
- quality was skipped (`RUN_QUALITY=0`), so none of these rows are promoted or
  submitted to LocalMaxxing.

## Results

Target model:

```text
Intel/Qwen3.6-27B-int4-AutoRound
/mnt/fast-ai/llm-cache/hf/hub/models--Intel--Qwen3.6-27B-int4-AutoRound/snapshots/abc86de19eb1ebbf6a7df4582341325c22ddcb7d
```

Draft model:

```text
z-lab/Qwen3.6-27B-DFlash
/mnt/fast-ai/llm-cache/hf/manual/z-lab--Qwen3.6-27B-DFlash
```

Common env deltas:

```bash
QWEN36_27B_ENABLE_MTP=0
QWEN36_27B_SPECULATIVE_CONFIG='{"method":"dflash","model":"/mnt/fast-ai/llm-cache/hf/manual/z-lab--Qwen3.6-27B-DFlash","num_speculative_tokens":<k>}'
VLLM_XPU_QWEN3_DFLASH_LAYER_TYPES=auto
```

| Variant | Strict fresh gate | Median tok/s | p10 tok/s | Mean tok/s | TTFT median | Interpretation |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| DFlash repaired k=2 cg8 | pass, quality skipped | `49.086555` | `45.704856` | `49.731995` | `682.959 ms` | fewer verifier rows, but too little token gain |
| DFlash repaired k=4 cg8 | pass, quality skipped | `54.835514` | `50.515108` | `55.907932` | `1340.725 ms` | best repaired DFlash row, still far below record |
| DFlash repaired k=8 cg8 | pass, quality skipped | `50.917542` | `47.966226` | `53.111151` | `2339.182 ms` | acceptance tail too weak; verifier rows too expensive |

Evidence:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-dflash-swa-pr40898-local-k2-cg8-candidate-summary-20260706Tdflash-swa-k2-codex1.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-dflash-swa-pr40898-local-k4-cg8-candidate-summary-20260706Tdflash-swa-k4-codex1.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-dflash-swa-pr40898-local-k8-cg8-candidate-summary-20260706Tdflash-swa-codex1.json
```

Representative k=2 timing:

```text
gpu_model_runner.forward_total        avg 13.716779 ms
gpu_model_runner.model_forward        avg 13.662545 ms
gpu_model_runner.draft_total          avg  2.380707 ms
spec_decode.propose.model_forward_first avg 0.937401 ms
gpu_model_runner.rejection_sampler    avg  0.394033 ms
lm_head_int8.gemm_w8a8                avg  0.039986 ms
```

Representative k=4 timing from the prior probe:

```text
gpu_model_runner.model_forward        avg ~17.05 ms
gpu_model_runner.draft_total          avg ~ 2.41 ms
```

Representative k=8 timing from the prior probe:

```text
gpu_model_runner.model_forward        avg ~46.47 ms
gpu_model_runner.draft_total          avg ~ 4.41 ms
```

## Interpretation

The repair is useful: the real mixed-SWA DFlash path no longer looks
catastrophic. It starts, graph-captures, passes the fresh-response mechanics,
and produces normal DFlash-like acceptance instead of the old `~1.1` mean
acceptance failure.

It is still not competitive:

- current valid Qwen27 record: `67.51904968102535 tok/s`;
- best repaired DFlash row: `54.83551385325532 tok/s`;
- the target verifier forward dominates once k grows, while k=2 trims verifier
  cost but cannot emit enough verified tokens per step.

Do not submit these rows. Do not promote this patch as a speed path for the
current record.

## Decision

Close DFlash again for the current Qwen27 INT4 one-B70 record lane.

What this patch is good for:

- future upstream DFlash/SWA correctness comparison;
- a starting point if a stronger Qwen3.6 27B DFlash draft appears;
- a reminder that the earlier catastrophic mixed-SWA result was partly a local
  plumbing issue, not necessarily proof that all mixed-SWA DFlash is broken.

What not to do next:

- do not repeat k/capture-size DFlash config sweeps on this draft;
- do not port Hipfire kernels for this draft before a fresh-suite tau win is
  demonstrated;
- do not treat DFlash as the route to `>100 tok/s` for this target/checkpoint.

Next credible Qwen27 work remains a stronger target-matched drafter, a real
accepted-tokens-per-target-step mechanism, or lower-level target-forward/kernel
work. The current MTP3 record is not limited by LM-head materialization in the
measured path; it is dominated by target forward plus recurrent draft work.
