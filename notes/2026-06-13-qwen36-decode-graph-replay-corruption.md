# Qwen3.6 Decode Graph Replay Corruption Boundary

Date: 2026-06-13

## Summary

The fast TP4 PIECEWISE graph lane for
`nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` is not quality-safe yet. The
failure is below the chat wrapper and appears in raw `/v1/completions` with a
fixed rendered ChatML prompt.

The decisive new boundary:

- Fast decode graph replay: `~97-100 tok/s`, but corrupts repeated fixed
  completions.
- Decode graph replay bypassed only for uniform decode:
  `15.993 tok/s`, but passed fixed raw canaries.

This means the next speed work should repair decode replay state/lifetime
correctness, not tune output copying or response formatting.

## New Probe

Added:

- `scripts/probe-fixed-chatml-completion-repeat.py`

It sends raw rendered ChatML to `/v1/completions` and repeats deterministic
fixed prompts. It now supports `--logprobs` and records HTTP errors as
mismatches, which caught the logprob/NaN failure below.

Compile check:

```bash
/home/steve/.venvs/vllm-xpu/bin/python -m py_compile \
  scripts/probe-fixed-chatml-completion-repeat.py \
  scripts/qwen36-text-quality-suite.py
```

## Results

### Accepted Fast Graph Corruption

Known fast controls:

- `data/qwen36-quark-int8-tp4-seq1-mbt8192-p512o512-20260613m.json`
  - corrected output: `99.8368 tok/s`
  - corrupt under fixed raw completions.
- `data/qwen36-quark-int8-tp4-seq1-noasyncgraph-p512o512-20260613n.json`
  - corrected output: `97.7546 tok/s`
  - not clean at depth.

Representative failures:

- `data/qwen36-quark-int8-tp4-seq1-noasyncgraph-fixed-color-repeat512-20260613n.json`
  - `10/512` mismatches.
  - mismatch indices: `85,91,174,180,263,269,352,358,441,447`.
- `data/qwen36-quark-int8-tp4-seq1-noasyncgraph-fixed-json-repeat512-20260613n.json`
  - `11/512` mismatches.
- `data/qwen36-quark-int8-tp4-seq1-noasyncgraph-fixed-color-alone-stopmismatch-20260613n.json`
  - single-prompt-alone mismatch at index `417`.
  - output: `blue whiskey green，orange，red`.

### Clean No-Replay Control

Global no-replay control:

- Launch used `COMPILATION_CONFIG='{"cudagraph_mode":"NONE"}'`.
- `data/qwen36-quark-int8-tp4-seq1-cgnone-fixed-color-alone-stopmismatch-20260613n.json`
  - `512/512` pass.
- `data/qwen36-quark-int8-tp4-seq1-cgnone-fixed-json-alone-stopmismatch-20260613n.json`
  - `512/512` pass.
- `data/qwen36-quark-int8-tp4-seq1-cgnone-p512o512-20260613n.json`
  - corrected output: `15.899 tok/s`.

Selective decode-replay bypass:

- Source guard: `VLLM_XPU_DISABLE_DECODE_CUDAGRAPH_REPLAY=1`.
- Launch:

```bash
MAX_NUM_SEQS=1 \
MAX_NUM_BATCHED_TOKENS=8192 \
LOG_PATH=/tmp/qwen36-quark-int8-tp4-seq1-nodecodereplay-probe-20260613o.log \
VLLM_XPU_DISABLE_DECODE_CUDAGRAPH_REPLAY=1 \
scripts/launch-qwen36-quark-int8-accepted.sh
```

Artifacts:

- `data/qwen36-quark-int8-tp4-seq1-nodecodereplay-fixed-color-repeat128-20260613o.json`
  - `128/128` pass.
- `data/qwen36-quark-int8-tp4-seq1-nodecodereplay-fixed-json-repeat128-20260613o.json`
  - `128/128` pass.
- `data/qwen36-quark-int8-tp4-seq1-nodecodereplay-p512o512-20260613o.json`
  - `15.993 tok/s` after first text.
  - `15.954 tok/s` wall.

Interpretation: this is a correctness control and a replay-boundary proof, not
a promoted speed candidate.

### Negative Fix Attempts

`VLLM_XPU_SYNC_ASYNC_OUTPUT_COPY=1`:

- Launch:

```bash
MAX_NUM_SEQS=1 \
MAX_NUM_BATCHED_TOKENS=8192 \
LOG_PATH=/tmp/qwen36-quark-int8-tp4-seq1-syncoutput-probe-20260613o.log \
VLLM_XPU_SYNC_ASYNC_OUTPUT_COPY=1 \
scripts/launch-qwen36-quark-int8-accepted.sh
```

- Artifact:
  `data/qwen36-quark-int8-tp4-seq1-syncoutput-fixed-color-stopmismatch-20260613o.json`
- Failed at index `55`.
- Output: `blue, green whiskey whiskey whiskey whiskey0000000000000000000000000`.

`VLLM_XPU_CUDAGRAPH_MARK_STEP_BEGIN=1`:

- Added an env-gated `torch.compiler.cudagraph_mark_step_begin()` call before
  each `execute_model`.
- Artifact:
  `data/qwen36-quark-int8-tp4-seq1-markstep-fixed-color-stopmismatch-20260613o.json`
- Failed at index `55`.
- Output: `blue, green whiskey whiskey whiskey whiskey0000000000000000000000000`.

Runtime recapture:

- Added an env-gated `VLLM_XPU_CUDAGRAPH_RECAPTURE_AFTER_N_REPLAYS` diagnostic
  plus `VLLM_XPU_CUDAGRAPH_ALLOW_RUNTIME_RECAPTURE=1`.
- Plain runtime recapture hit:
  `RuntimeError: CUDA graph capturing detected at an inappropriate time.`
- Allowing runtime recapture launched but failed quickly:
  `data/qwen36-quark-int8-tp4-seq1-recap32allow-fixed-color-stopmismatch-20260613n.json`
  at index `4`.
- Conclusion: live recursive recapture perturbs the graph path and is not a
  safe fix.

Strong output:

- `VLLM_XPU_CUDAGRAPH_STRONG_OUTPUT=1`
- Artifact:
  `data/qwen36-quark-int8-tp4-seq1-strongout-fixed-color-stopmismatch-20260613n.json`
- Failed at index `55`.
- Conclusion: weak-ref graph output lifetime is not the primary cause.

### Logprob/NaN Evidence

The logprob probe on the fast replay path failed with a server-side JSON
serialization error:

- Artifact:
  `data/qwen36-quark-int8-tp4-seq1-markstep-fixed-color-logprobs5-http-stopmismatch-20260613o.json`
- Mismatch index: `124`.
- HTTP body:
  `Out of range float values are not JSON compliant: nan`.

The server log also recorded the same ValueError while rendering logprobs.
This points at corrupted logits/logprob tensors, not merely detokenization,
HTTP response handling, or host output-copy ordering.

## External Signals

These were not direct Intel-B70 fixes, but they match the failure class and
informed the next direction:

- vLLM issue `#32834` isolates a different model/quant crash to V1 CUDA graph
  capture/replay, with eager stable but slow:
  `https://github.com/vllm-project/vllm/issues/32834`.
- PyTorch issue `#114844` shows CUDA graph replay does not replay Python-side
  state assignment such as `self.x = res`, silently leaving stale state:
  `https://github.com/pytorch/pytorch/issues/114844`.
- PyTorch issue `#171551` documents overwritten graph outputs and recommends
  cloning or `torch.compiler.cudagraph_mark_step_begin()` for that class:
  `https://github.com/pytorch/pytorch/issues/171551`.
- PyTorch issue `#169970` notes grouped matmul can be problematic with graph
  capture/replay when dynamic allocations/state enter the graph:
  `https://github.com/pytorch/pytorch/issues/169970`.

`cudagraph_mark_step_begin()` did not fix our vLLM/XPU manual graph replay
failure, but the stale-state and grouped-kernel graph warnings remain relevant.

## Focused Patch Snippets

Saved focused patch:

- `patches/vllm-qwen36-decode-replay-boundary-20260613o.patch`

This patch is diagnostic-only:

- `VLLM_XPU_DISABLE_DECODE_CUDAGRAPH_REPLAY=1`
- `VLLM_XPU_CUDAGRAPH_MARK_STEP_BEGIN=1`
- `VLLM_XPU_CUDAGRAPH_STRONG_OUTPUT=1`
- `VLLM_XPU_CUDAGRAPH_RECAPTURE_AFTER_N_REPLAYS`
- `VLLM_XPU_CUDAGRAPH_ALLOW_RUNTIME_RECAPTURE=1`

Only the decode replay bypass produced clean output, and it is too slow to
promote.

## Next Best Work

1. Add a first-divergence replay-vs-no-replay tensor/logits microscope for the
   fixed color prompt. Capture token ids, positions, slot mappings, block table
   slice, hidden-state digest, sample-hidden digest, logits finite counts, and
   top-k logits around the first bad generated token.
2. Inspect all graph-replayed modules for Python-side state writes during
   forward. The PyTorch stale-state issue makes this a plausible source of
   replay-only wrongness.
3. Add an opt-in static-input sanitation mode before replay: fill unused/padded
   regions of input ids, positions, slot mappings, and block tables with
   sentinels or zeroes, then rerun the fixed canary.
4. Add graph-wrapper replay counters by subgraph/layer and correlate the first
   fixed-prompt mismatch with the replay counts for MoE, GDN, attention, and
   logits.
5. If tensor/logit microscope points at one layer family, try a selective
   replay bypass only for that family instead of all decode. The target is to
   recover most of the `~100 tok/s` graph speed while keeping the clean canary
   behavior of the `15.99 tok/s` control.
6. Keep persistent W8A8 MoE layerlet work alive, but do not stack more MoE
   speed claims on top of a corrupt graph replay base.

