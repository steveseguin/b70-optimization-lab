# DFlash2 transfer feasibility on the official FP8 target

September 14, 2026. This is a **static feasibility audit**, not a GPU result or
recommendation to replace the current server. The user authorized a bounded
test while prioritizing useful improvements across varied workloads and longer
contexts. The AMD throughput report remains community-reported.

Read [the AMD intake](../../../community/1337hero-r9700-qwen38-radiance/README.md),
[lane do-not-repeat index](../DO-NOT-REPEAT.md), and
[runtime rebase evidence](2026-09-12-rebase-onto-vllm-v0290.md).
Machine-readable identities and public metadata are in
[the feasibility receipt](../data/2026-09-14-amd-transfer/dflash2-feasibility.json).
No GPU requests, Torch imports, model-weight downloads, package installation,
or runtime modifications occurred during this audit. New audit files only.

## Source support and the V2 restriction

The live R304 image, `sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2`,
already contains `DFlash2DraftModel`, `qwen3_dflash2.py`, and the V2
`DFlash2Speculator`. The DFlash2 model and selector files are byte-identical to
upstream main `47fbd36e6dc908277e386424beeb8647355c1c8b` inspected today. The
broader DFlash plumbing has newer changes; one disables FlashAttention AOT
schedules for windowed draft models. Explicit draft-only `TRITON_ATTN` avoids
that specific backend path. This is not proof that every newer change is irrelevant.

Current `config/vllm.py` explicitly rejects DFlash2 on V1: its ordinary
`DFlashProposer` never calls the candidate selector and would otherwise silently
degrade to DFlash1. A complete implementation therefore needs V2. The target
Qwen class and V2 runner already support auxiliary hidden-state extraction.

The accepted target-side W8A16 block-FP8 kernel and patched oneDNN, norm,
FP16-linear row chunking, GDN implementation and exact XCCL communicator are
shared modules and remain present when selecting V2. Their actual execution,
state handling and output parity still need a runtime gate. The V1-only
INT4 draft-head initialization does not transfer automatically. The existing
startup guard in `gpu_model_runner.py` is also V1 code, so target tiny-prefill
and speculative-width boundary probes remain necessary on V2.

The DFlash loader can share the target embedding and output-head objects with
the draft. Do not attach INT4 or approximate shortlist behavior to those shared
modules while trying to speed the drafter. The first screen must retain the
full target head. No Radiance target shortlist or lossy collective is required.

## Pinned checkpoint and context

Draft: `tcclaviger/Qwen3.8-27B-DFlash2-FP8`, revision
`ee0cb26a8279b7910cc28d82a8a3e15e4728d56f`.
The [public file receipt](../data/2026-09-14-amd-transfer/dflash2-hf-metadata.json)
lists one `model.safetensors` file, **2,118,882,784 bytes**, LFS SHA256
`7dbb99a8d0120f502e66b256aa7c0866d933ceeee4a02463d9db591811e8404e`.
The only other required model input is `config.json`, 3256 bytes, SHA256
`5b5668a00b26aaebd88c7e3d961f7d1cdef025867fee158dfccb84f29fd8caec`.
README and license metadata should accompany any local intake; these hashes
identify the inspected revision, not unperformed weight verification.

The [config](../data/2026-09-14-amd-transfer/dflash2-config.json) has five layers,
hidden size 5120, vocabulary 248320, target layer taps `[5,19,33,47,61]`, and
64 target layers. These match the official target's dimensions. It uses seven
proposals in an eight-position block, five 2048-token sliding-window attention
layers and maximum position 262144. Block-128 FP8 weights are supported by
the existing XPU W8A16 route; convs, norms and selector remain unquantized.

The 2048-token window bounds direct draft attention; it is not a 2048-token
service limit. Target hidden states contain information from earlier input.
Neither that observation nor the 262K position setting proves good acceptance
or speed at long contexts. Target attention, auxiliary-state extraction and
context-KV preparation still cost work. The draft was trained for the original
target; the official FP8 target's arithmetic may change acceptance.

Current server startup logged 14.38 GiB model memory per rank, 12.53 GiB
available KV memory and 333111 KV tokens, versus only one active request at
33024 maximum context. Thus extra draft weights and caches plausibly fit at the
same context and 0.95 utilization by reducing excess allocated KV capacity.
This is a capacity inference, not a launch result. Do not reduce context or
increase utilization in advance; inspect actual startup memory profiling.

## Candidate configuration, not a launch instruction for the live service

Reuse the exact target-side environment and arguments from the captured R187
profile after rebasing the accepted overlay. The deliberate differences are:

```text
VLLM_USE_V2_MODEL_RUNNER=1
VLLM_XPU_DRAFT_LM_HEAD_INT4=0
VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST=

--speculative-config '{"method":"dflash","model":"/draft","num_speculative_tokens":7,"draft_tensor_parallel_size":2,"attention_backend":"TRITON_ATTN","max_model_len":33024}'
```

Mount the exact pinned draft read-only at `/draft`. Preserve target `/model`,
TP2, `--dtype float16`, `--quantization fp8`, `--kv-cache-dtype auto`,
`--max-model-len 33024`, `--max-num-seqs 1`,
`--max-num-batched-tokens 4096`, `--block-size 64`,
`--gpu-memory-utilization 0.95`, `--no-enable-prefix-caching`,
`--enable-prompt-tokens-details`, and `--language-model-only`.
Retain `VLLM_XPU_FP8_BLOCK_W8A16=1`, `VLLM_XPU_GDN_SPLIT_MIXED=1`,
the existing GDN grouping/state-buffer settings, exact XCCL environment,
`VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT=1`,
`VLLM_XPU_FP16_LINEAR_ROWCHUNK=32`, `VLLM_XPU_FP16_LINEAR_CLASSPAD=0`,
`PYTHONHASHSEED=0`, deterministic compile settings and disabled tuner settings.
No `RADIANCE_*` variable or implementation is needed.

Keep XPU graphs off. Existing `splitting_ops=[]` uses the VLLM compile pipeline,
not `STOCK_TORCH_COMPILE`; V2's unsupported-feature list rejects the latter,
not the former. Therefore the current whole-model compilation configuration
has no identified static rejection. Compilation and numeric behavior on this
new auxiliary-output path remain untested. Do not describe switching to eager
or changing split operators as an unchanged-performance control.

## No existing per-request target-only oracle

Inspection found no speculation-disable field in `SamplingParams`, OpenAI
chat-completion or completion protocols. `trace_decode_token_ids` explicitly
rejects speculative servers. Low acceptance, grammar forcing, logit bias,
one-token requests or forcing a context boundary do not establish a faithful
ordinary-decode oracle.

`num_speculative_tokens_per_batch_size` is a launch-global batch schedule.
The current V2 runner does not consume the scheduler's
`num_spec_tokens_to_schedule` field in the same way as V1; graph-size scheduling
alone is not proof of zero drafting or target-only execution. Do not use
concurrency manipulation as a single-user, same-process oracle.

A strict decomposition needs a V2 no-spec oracle, then DFlash2 versus that
oracle, with V2 no-spec also compared against the qualified V1 target. Without
a separate controlled load or an independently qualified runtime switch,
historical V1 oracle comparison is useful screening but cannot isolate a V2
runner change from a DFlash change. No server cycling was performed here.

## Newest base and bounded qualification

The [latest release metadata](../data/2026-09-14-amd-transfer/upstream-release.json)
still names v0.29.0, released September9. However, the
[XPU tag receipt](../data/2026-09-14-amd-transfer/upstream-xpu-tags.json)
shows a newer September14 nightly at source
`dc36fcce902a63eab06c1b93a5c4a5ee178a0c56`, index digest
`sha256:fa0e2f3966f23d64e1532e45ce2eca2fef619fb63f93d5b9b13cb5bcc0743aec`,
amd64 manifest
`sha256:28915aadfe9665dd70f1cf36e6f7362e25df24e9035785dedd00559652bbef41`.
No image was pulled by this audit. AGENTS.md's rolling-base requirement applies:
R304 is the qualified historical comparison, not today's newest available base.
A campaign must resolve the mutable tag again, retain the accepted overlay,
record its disposition and qualify it before performance promotion.

For a bounded screen, use the complete varied fixed suite, then existing
real-content 2K, 8K and 32K cases. Keep cache hits zero and complete output
tokens; report acceptance, server prefill, HTTP TTFT and decode separately.
Include tiny-prefill and generation/context-boundary cases because R304's
documented speculative-to-nonspeculative GDN state handoff is not a draft-quality
problem. Stop on incorrect outputs, runtime faults or clearly inadequate
performance; do not compensate with selected code prompts, repeated material,
target approximation or lower precision. No speed or exactness result exists
for this candidate in this note.
