# Qwen27 spec greedy top-token IDs: valid but no headline win

Date: 2026-07-04

## Summary

Tested a default-off exact all-greedy speculative verifier path that feeds
target top-token IDs directly into the existing greedy rejection kernel instead
of passing dense target logits into the sampler.

The path is correctness-preserving and the strict fresh-response gate passed,
but it does **not** beat the current `webhie/Qwen3.6-27B-int4-AutoRound` +
runtime INT8 LM-head BF16-scale record. The reason is expected: current
`model.get_top_tokens()` still computes the dense LM-head/logits internally, so
this patch removes sampler/logits plumbing but not the dominant LM-head GEMM.

Do not submit this run to LocalMaxxing. Keep it as integration groundwork for a
future true fused/tiled LM-head top-1 / candidate-max kernel.

## Patch Snapshot

Active-stack patch:

- `patches/qwen36-27b-autoround-int4-b70/vllm-active-stack-with-spec-greedy-topids-no-win-20260704.patch`

Important caveat: `/home/steve/src/vllm` already contained the active Qwen27
optimization stack before this experiment. This patch is an **active-stack
snapshot**, not a minimal upstream-clean patch. The experiment-specific pieces
are:

- `vllm/v1/sample/rejection_sampler.py`
  - added `RejectionSampler.forward_from_top_token_ids(...)`;
  - added `rejection_greedy_sample_from_argmax(...)`, which calls the existing
    XPU greedy rejection kernel using target argmax IDs and bonus token IDs.
- `vllm/v1/worker/gpu_model_runner.py`
  - added `_sync_xpu_spec_top_token_ids(...)`;
  - added the gated `VLLM_XPU_SPEC_GREEDY_TOP_IDS=1` path for all-greedy spec
    decode when logprobs, penalties, masks, logits processors, thinking-budget
    tracking, synthetic acceptance, and margin gates are inactive;
  - routes `_sample(...)` to `forward_from_top_token_ids(...)` when logits are
    intentionally omitted and precomputed spec top-token IDs are present.
- `vllm/envs.py`
  - registered `VLLM_XPU_SPEC_GREEDY_TOP_IDS`,
    `VLLM_XPU_SPEC_GREEDY_TOP_IDS_SYNC_TOKENS`, and
    `VLLM_XPU_SPEC_GREEDY_TOP_IDS_SYNC_STRICT`.

## Validation

Syntax:

```bash
cd /home/steve/src/vllm
/home/steve/.venvs/vllm-xpu/bin/python -m py_compile \
  vllm/envs.py \
  vllm/v1/sample/rejection_sampler.py \
  vllm/v1/worker/gpu_model_runner.py
```

Isolated XPU parity check:

- compared the normal logits-based greedy rejection path against
  `rejection_greedy_sample_from_argmax(...)` on small XPU tensors;
- both produced identical sampled IDs:
  `[[10, 99, -1, -1], [20, 21, 22, 77]]`.

Strict fresh-response endpoint run:

```bash
cd /home/steve/llm-optimizations
LABEL=qwen27-webhie-spec-greedy-topids-20260704 \
MODEL_DIR=/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e \
GPU_INDEX=2 PORT=19412 \
VLLM_XPU_LM_HEAD_INT8=1 \
VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16 \
VLLM_XPU_SPEC_GREEDY_TOP_IDS=1 \
VLLM_XPU_LOCAL_ARGMAX_DEBUG=1 \
scripts/run-qwen36-27b-autoround-vllm-candidate.sh
```

Result artifact:

- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-spec-greedy-topids-20260704-20260704T022335Z.json`

Run directory:

- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-spec-greedy-topids-20260704-20260704T022335Z`

Server proof that the path fired:

- `server.stdout.log` reported `spec top-token IDs enabled`;
- `server.stdout.log` reported `using precomputed spec top_token_ids`.

Note: this run warned that `VLLM_XPU_SPEC_GREEDY_TOP_IDS` was an unknown env
var because the env registry entry was added after the endpoint run. The patch
snapshot includes that registry fix, and syntax validation passed afterward.

## Metrics

Strict gate:

- `realistic_final_gate.passed=true`;
- `cached_tokens=0` on every prompt;
- fixed Qwen realistic suite, each prompt once, chat mode, token-ID timing.

Throughput:

- median generated-token throughput for tokens 1-100 after TTFT:
  `65.25583870721442 tok/s`;
- p10: `57.25624453442291 tok/s`;
- mean: `63.86008319311579 tok/s`;
- full-output after-TTFT median: `65.29285106166057 tok/s`;
- wall-clock full-output median: `49.156984948710175 tok/s`;
- median TTFT: `604.7489704797044 ms`.

Comparison:

- current valid record:
  `65.27648650325429 tok/s`
  (`webhie/Qwen3.6-27B-int4-AutoRound` + runtime INT8 LM-head BF16 scales);
- top-ID sampler candidate:
  `65.25583870721442 tok/s`;
- decision: **no headline win** (`-0.032%`, within noise and below record).

## Interpretation

This confirms the all-greedy top-token verifier plumbing can preserve the strict
fresh-response gate, but it does not attack the measured bottleneck. Phase 1
timing showed the active recipe still spends about `10.61 ms` per verifier step
inside `lm_head_int8.gemm_w8a8` under sync instrumentation, and this patch still
invokes the same dense LM-head work through `get_top_tokens()`.

The useful next step is not another endpoint sweep of this flag. The useful next
step is a real native compact LM-head primitive:

1. compute row-local top token ID/score without materializing full
   `[rows, vocab]` logits;
2. compute candidate token scores needed by the verifier;
3. preserve exact greedy/spec semantics and safe fallback to dense logits for
   logprobs, sampling, masks, penalties, processors, and non-greedy modes;
4. validate against dense logits on controlled probes before any endpoint
   promotion.

