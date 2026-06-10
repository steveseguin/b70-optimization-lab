# Qwen3.6 FlashAttention Split Policy Rejection

Date: 2026-06-10

## Candidate

Tested a guarded XPU FlashAttention decode split override for the Qwen3.6
35B-A3B Quark W8A8 INT8 endpoint.

Patch artifact:

- `patches/vllm-qwen36-xpu-flash-attn-kv-splits-rejected-20260610.patch`

The temporary hook added `VLLM_XPU_FLASH_ATTN_KV_SPLITS` to the XPU wrapper and
forwarded it as `num_splits_kv` to `vllm_xpu_kernels.flash_attn_interface`.
This allowed testing fixed split-KV counts without rebuilding `_xpu_C`.

Rationale:

- Qwen3.6 has 10 full-attention layers and 30 linear-attention layers.
- The accepted p512/n512 run reaches roughly 1024 KV tokens during decode.
- The C++ split heuristic can choose split-KV near the longer end of the
  decode; forcing lower split counts might reduce `ReduceSplitK` overhead.

## Runtime

Common runtime:

- model:
  `/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118`
- TP4, 32K context, no prefix caching
- `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone`
- PIECEWISE XPU graph
- max batched tokens `8192`
- max seqs `48`

Candidate deltas:

- `VLLM_XPU_FLASH_ATTN_KV_SPLITS=1`
- `VLLM_XPU_FLASH_ATTN_KV_SPLITS=2`

## Speed Results

Control artifact:

- `data/qwen36-quark-int8-tp4-noprefix-current-control-continue-20260610.json`

Candidate artifacts:

- `data/qwen36-quark-int8-tp4-noprefix-gdnclone-flashsplit1-single-r8-20260610.json`
- `data/qwen36-quark-int8-tp4-noprefix-gdnclone-flashsplit2-single-r8-20260610.json`

| run | corrected after-first tok/s | e2e tok/s | total tok/s | TTFT ms |
| --- | ---: | ---: | ---: | ---: |
| accepted control | `99.6301` | `98.3908` | `196.7815` | `74.774` |
| split=1 | `99.1570` | `97.9101` | `195.8201` | `75.843` |
| split=2 | `98.7999` | `97.5682` | `195.1364` | `75.541` |

## Decision

Reject. Both lower fixed split counts regressed single-request decode speed.
No quality suite was run because neither candidate passed the speed gate.

The temporary source hook was removed after measurement. The accepted service
was restored:

- tmux session: `qwen36-tp4-gdn-reusequant-clone-envclean-32k`
- backend health: pass
- frontdoor `/v1/models`: pass

## Lesson

For this p512/n512 single-request profile, the existing XPU FlashAttention
split heuristic is better than forcing one or two KV splits. Full attention is
also a minority of this model's layers, so small split-policy wins are unlikely
to move endpoint speed unless they improve the longer-context tail without
hurting the common decode window.
