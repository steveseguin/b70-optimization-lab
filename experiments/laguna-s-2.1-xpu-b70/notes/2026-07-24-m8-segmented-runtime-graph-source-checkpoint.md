# Laguna M8 segmented runtime-graph source checkpoint

Date: 2026-07-24 America/Toronto

## Status

The target-only segmented runtime-graph implementation is source-complete at:

- vLLM `0964fe3d1` (`xpu: segment Laguna M8 graph collectives`);
- parent selector commit `e09f34a008c31cb4c691697215a6eff3aa2eb5be`;
- worktree `/home/steve/src/laguna-vllm-runtime-graph-20260724`.

This checkpoint performed no accelerator, model, endpoint, generation,
network, USB, benchmark, payload, or LocalMaxxing action. It authorizes only
construction and review of a separate changing-input four-card component gate.
The approved record remains `33.89498511171744 tok/s`,
LocalMaxxing `cmrx6p5dv001bo4017hb7sixz`.

## Corrected target topology

Source review found that the earlier direct-capture probe's synthetic
`97 all-gathers -> final all-reduce` pattern is not the actual target-model
forward order. Under the approved record flags, including
`VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH=0`, the exact M8 target forward performs:

1. one embedding BF16 all-reduce of `[8, 3072]`;
2. 48 attention-O fixed-rank reductions implemented as BF16 all-gathers of
   `[1, 8, 3072]` into `[4, 8, 3072]`;
3. one layer-0 dense-MLP down-projection reduction with the same gather
   geometry (`mlp_only_layers=[0]`); and
4. 47 MoE combine reductions with the same gather geometry.

The resulting model-forward contract is one initial all-reduce followed by 96
all-gathers: 97 eager collective boundaries total. The compact FP32 logits
all-gather runs after `set_forward_context` exits and remains outside the
target graph wrapper.

## Implementation boundary

The default-off `VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH` lane:

- requires Laguna target plus quantization-matched DFlash depth 7, TP4/EP4,
  PP1/DP1, one request, synchronous scheduling, compilation `NONE`, runtime
  `PIECEWISE`, capture sizes `[8]`, AOT off, deterministic compiler graph off,
  no LoRA, and no ubatching;
- makes only a one-request target-verifier batch with exactly eight scheduled
  tokens and seven draft tokens graph-eligible;
- leaves the DFlash drafter, M1 through M7 target calls, prefill, logits, and
  all unrelated models eager;
- preallocates one persistent embedding-reduction buffer and 96 persistent
  gather buffers on the runner before capture;
- intercepts collectives only while the typed eligible target forward context
  is active;
- rejects all-reduce/all-gather order, count, geometry, dtype, device,
  contiguity, and alias drift;
- requires 97 eager callbacks on capture and replay, while separately allowing
  the expected capture gather cursor of 96 and replay cursor of zero; and
- pins the graph output and recursively checks tensor pointer, storage offset,
  shape, stride, dtype, and device identity before replay.

No compiler lowering, fusion, target arithmetic substitution, collective
coalescing, logits capture, or draft capture is introduced.

## Verification

The following source-only checks passed:

```text
.venv/bin/python -m ruff format <focused files>
.venv/bin/python -m ruff check <focused files>
PYTHONPATH=/home/steve/.venvs/deepseek-v4-xpu/lib/python3.12/site-packages \
  .venv/bin/python -m pytest -q \
  tests/v1/cudagraph/test_laguna_m8_collectives.py \
  tests/v1/worker/test_gpu_model_runner.py \
  -k 'laguna_m8_breakable or laguna_m8_runner'
18 passed, 34 deselected

PYTHONPATH=/home/steve/.venvs/deepseek-v4-xpu/lib/python3.12/site-packages \
  .venv/bin/python -m pytest -q \
  tests/v1/cudagraph/test_breakable_cudagraph.py \
  tests/v1/cudagraph/test_laguna_m8_collectives.py
10 passed, 10 skipped
```

`compileall` and `git diff --check` also passed. The skipped tests require
CUDA-like graph hardware and are not treated as runtime evidence. An
independent read-only source audit reported no concrete runtime-safety blocker
after the topology correction.

## Next gate

Before any model load or endpoint:

1. run a four-card changing-input substrate gate matching the corrected
   `embedding AR -> 96 AG` order, with every collective eager and persistent;
2. raw-compare every collective output and every fixed-rank BF16 sum across all
   epochs;
3. prove graph-segment and eager-collective counts with trace/runtime
   instrumentation;
4. seal identities and all evidence under internal NVMe/ext4; and
5. stop before model work on any mismatch, stale output, hidden eager fallback,
   device/runtime error, or failure to reduce the intended submission cost.

Passing a synthetic substrate gate will be a prerequisite only. It will not by
itself authorize an endpoint or claim that the full target wrapper is exact or
faster.
