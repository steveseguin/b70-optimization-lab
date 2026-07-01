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

## 2026-06-13q Follow-Up: Replay Boundary Repairs Tried

New probe support:

- Added `--request-id-prefix` to
  `scripts/probe-fixed-chatml-completion-repeat.py` so server-side microscope
  traces can be aligned with deterministic canary repeats.
- Added an XPU replay microscope to `vllm/v1/worker/gpu_model_runner.py`.
  It can trace selected request IDs with input IDs, positions, slot mappings,
  hidden/sample-hidden/logit summaries, local-argmax sampled IDs, and request
  counters.

Key trace finding:

- Under local argmax + direct gather + logit NaN sanitizer, the JSON canary can
  diverge before any replayed decode in that request.
- For the bad JSON repeat, eager prefill (`cudagraph_mode=NONE`) already had a
  different sample-hidden digest from the adjacent good repeat:
  - good: sampled `{`, prefill sample-hidden sum `-72.3495`
  - bad: sampled `{`, prefill sample-hidden sum `-64.6469`
- The next decode sampled `answer` in the good request and `question` in the
  bad request.
- Interpretation: a prior replayed decode can poison later request state or
  graph/static buffers; this is not only a first post-prefill decode-boundary
  issue and not only LM-head/logit gather.

Fast-but-not-clean candidate:

- `VLLM_XPU_LOCAL_ARGMAX_DECODE=1`
- `VLLM_XPU_LOCAL_ARGMAX_DIRECT_GATHER=1`
- `VLLM_XPU_SANITIZE_LOGITS_NAN=1`
- JSON/color short gates can pass and `p512/o512` c1 decode is about
  `91.4 tok/s`, but long deterministic gates fail, so this is not promotable.

Repairs tested and rejected:

- `VLLM_XPU_DISABLE_FIRST_DECODE_CUDAGRAPH_REPLAY=1`
  - First implementation missed the active request count; patched to use
    `input_batch.req_ids`.
  - Trace confirmed the first post-prefill decode ran eager (`NONE`).
  - JSON still failed at repeat `70`.
  - Artifact:
    `data/qwen36-quark-int8-tp4-seq1-localargmax-directsanitize-firstdecodeeager2-fixed-json-repeat512-20260613q.json`
  - Trace:
    `data/qwen36-replay-microscope-firstdecodeeager2-json-068-070-20260613q.jsonl`

- `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=0`
  - Launcher default is now overrideable.
  - JSON still failed at repeat `139`, same `answer` -> `question` branch flip.
  - Artifact:
    `data/qwen36-quark-int8-tp4-seq1-localargmax-directsanitize-gdnreuse0-fixed-json-repeat512-20260613q.json`

- `VLLM_XPU_ZERO_FRESH_GDN_STATE=1`
  - Added env-gated explicit zeroing of GDN `conv_state` and `ssm_state` for
    fresh prefill state indices before the prefill convolution/recurrent core.
  - JSON still failed at repeat `139`.
  - Artifact:
    `data/qwen36-quark-int8-tp4-seq1-localargmax-directsanitize-zerofreshgdn-fixed-json-repeat512-20260613q.json`

- `VLLM_ENABLE_FLA_PACKED_RECURRENT_DECODE=0`
  - JSON still failed at repeat `139`.
  - Artifact:
    `data/qwen36-quark-int8-tp4-seq1-localargmax-directsanitize-nopackedrec-fixed-json-repeat512-20260613q.json`

- `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=0`
  - Startup failed in `parallel_state.graph_capture` because the communicator
    graph-capture context asserts `CudaCommunicator`.
  - Root error: `AssertionError` at `parallel_state.py:565`.
  - Artifact:
    `data/qwen36-localargmax-directsanitize-realcommgraph-20260613q.log`
  - Conclusion: the current XPU path cannot capture communicator context via
    the CUDA graph-capture helper; noop communicator capture is required unless
    we implement an XPU-specific context.

- `VLLM_XPU_USE_CUSTOM_OP_COLLECTIVES=0`
  and `VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP=0`
  - Launcher flags are now overrideable.
  - JSON still failed at repeat `139`.
  - Artifact:
    `data/qwen36-quark-int8-tp4-seq1-localargmax-directsanitize-stockcollectives-fixed-json-repeat512-20260613q.json`

Current conclusion:

- The corruption is still tied to decode graph replay, but not fixed by:
  first-decode eager, GDN quant-reuse changes, explicit fresh GDN state zeroing,
  disabling packed recurrent decode, or stock compile-time collectives.
- The repeat-139 stability of several variants suggests a deterministic replay
  state/buffer lifetime bug rather than random numerical instability.

Next best ideas:

1. Selectively bypass graph replay for GDN/Mamba subgraphs only, if the
   piecewise runner can route that family eager while keeping MoE/dense replay.
2. Add a layer-family replay microscope or state fingerprint around GDN cache
   writes: record state indices, `has_initial_state`, conv/SSM state norms for
   fresh prefill blocks, and per-layer GDN output digests.
3. Investigate the XPU graph/noop communicator capture path. A proper XPU
   communicator graph-capture context may be required if noop capture lets
   replayed collectives interact with stale external state.
4. Test static input and metadata sanitation before every PIECEWISE replay:
   zero unused/padded request rows, block-table rows, logits indices, and
   metadata tensors before copying active data.
5. If selective family bypass is not practical, implement a low-overhead
   periodic replay quarantine that disables replay for an entire request after
   a fixed number of successful graph-replayed requests, then use canaries to
   find whether corruption is count-based or request-content-based.

## 2026-06-13y/ad Follow-Up: No-Async Boundary Isolation

New positive control:

- `COMPILATION_CONFIG='{"cudagraph_mode":"NONE"}'`
- `VLLM_XPU_SANITIZE_LOGITS_NAN=1`
- `VLLM_XPU_ZERO_FRESH_GDN_STATE=1`
- `VLLM_EXTRA_ARGS='--no-async-scheduling'`
- Artifacts:
  - `data/qwen36-quark-int8-tp4-seq1-zeronative-noasync-graphnone-fixed-json-repeat512-20260613y.json`
    - `512/512` pass.
  - `data/qwen36-quark-int8-tp4-seq1-zeronative-noasync-graphnone-fixed-color-repeat512-20260613y.json`
    - `512/512` pass.

Interpretation:

- With async scheduling disabled and native fresh-GDN state zeroing enabled,
  full graph replay disablement is clean for both fixed canaries.
- This confirms the remaining no-async corruption is still tied to
  PIECEWISE/compiled graph replay, not to HTTP, tokenizer, sampling, or fresh
  GDN state initialization.

Native GDN zeroing update:

- Moving `VLLM_XPU_ZERO_FRESH_GDN_STATE=1` into the native XPU GDN wrapper fixed
  the previous async/direct-sanitize JSON repeat:
  - `data/qwen36-quark-int8-tp4-seq1-localargmax-directsanitize-zeronative-fixed-json-repeat512-20260613r.json`
    - `512/512` pass.
- It did not fully repair color on the async/direct path:
  - `data/qwen36-quark-int8-tp4-seq1-localargmax-directsanitize-zeronative-fixed-color-repeat512-20260613r.json`
    - failed at repeat `56`.
- The GDN trace for no-async JSON showed fresh prefill GDN states are zero for
  adjacent good/bad requests, but layer-0 projected GDN inputs already differ
  before the native GDN core. That points upstream of GDN state reuse.
  - Trace:
    `data/qwen36-gdn-trace-zeronative-noasync-json-052-053-20260613x.jsonl`

No-async PIECEWISE observations:

- Plain no-async + PIECEWISE + native GDN zero:
  - Color passed:
    `data/qwen36-quark-int8-tp4-seq1-zeronative-noasync-fixed-color-repeat512-20260613u.json`
    - `512/512` pass.
  - JSON failed:
    `data/qwen36-quark-int8-tp4-seq1-zeronative-noasync-fixed-json-repeat512-20260613u.json`
    - failed at repeat `372`.
- No-async replay microscope, focused on the JSON fail shifted by tracing:
  - `data/qwen36-replay-microscope-zeronative-noasync-json-052-053-20260613w.jsonl`
  - All TP ranks agreed within each request.
  - Good and bad requests had identical prompt IDs/positions/logits indices.
  - First sampled token was `{` for both, but first-step logits/top-k already
    differed. The second token diverged to `answer` vs `question`.
  - This is request-to-request model/graph state contamination, not rank-local
    sampling disagreement.

Repairs tested in this follow-up:

- `VLLM_XPU_SKIP_COMPILED_PREFILL=1`
  - Startup initially failed during capture/profile with
    `Shape: 8193 out of considered ranges: [(1, 8192)]`.
  - Patched capture/profile to ignore this live-runtime knob.
  - Runtime still failed JSON:
    `data/qwen36-quark-int8-tp4-seq1-zeronative-noasync-skipprefill-fixed-json-repeat512-20260613z2.json`
    - failed at repeat `54`.
  - Conclusion: bypassing only the top-level compiled prefill call is not
    enough; the bad state is not solely top-level prefill compilation.

- `VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1`
  - Added as a live-only env guard to set non-uniform prefill
    `cudagraph_mode=NONE` while preserving uniform decode replay.
  - Startup first failed when the guard applied during dummy/capture; patched
    it to require `force_uniform_decode is None` and `not force_eager`.
  - Runtime still failed JSON:
    `data/qwen36-quark-int8-tp4-seq1-zeronative-noasync-prefillgraphoff-fixed-json-repeat512-20260613ab.json`
    - failed at repeat `54`.
  - Conclusion: prefill replay alone is not the full bad boundary.

- `VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1`
  plus `VLLM_XPU_DISABLE_FIRST_DECODE_CUDAGRAPH_REPLAY=1`
  - JSON passed:
    `data/qwen36-quark-int8-tp4-seq1-zeronative-noasync-prefillfirstoff-fixed-json-repeat512-20260613ac.json`
    - `512/512` pass.
  - Color failed later:
    `data/qwen36-quark-int8-tp4-seq1-zeronative-noasync-prefillfirstoff-fixed-color-repeat512-20260613ac.json`
    - failed at repeat `120` with
      `blue, green, orange,\n</think>\n\nred`.
  - Server log during JSON showed short-repeat generation around `52 tok/s`,
    so this is a useful partial boundary, but it is not correctness-safe.

- `VLLM_XPU_DISABLE_INITIAL_DECODE_CUDAGRAPH_REPLAY_STEPS=6`
  plus prefill replay off:
  - Added a generalized live-only first-N decode replay quarantine.
  - Color failed earlier:
    `data/qwen36-quark-int8-tp4-seq1-zeronative-noasync-prefilloff-decode6off-fixed-color-repeat512-20260613ad.json`
    - failed at repeat `24` with `blue, green, red, yellow`.
  - Conclusion: a token-count quarantine is not monotonic and can perturb the
    generation path. Do not promote.

- `cudagraph_copy_inputs=true`
  - Launch config:
    `COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","cudagraph_copy_inputs":true}'`
  - Startup failed in generated inductor kernels during profiling:
    `Assertion index out of bounds: 0 <= ... < 1048576`, then worker
    cancellation.
  - Log:
    `data/qwen36-zeronative-noasync-copyinputs-20260613ae.log`
  - Conclusion: promising failure class match, but the stock copy-input path is
    not currently launchable on this XPU/AOT path.

Current best correctness state:

- Clean and safe: `cudagraph_mode=NONE` or full uniform-decode replay bypass.
- Fast but unsafe: PIECEWISE replay.
- Best partial speed/correctness boundary so far:
  prefill replay off + first-decode replay off; JSON clean at 512 and short
  server-log decode around `52 tok/s`, but color still fails, so it is not
  promotable.

Next deeper repair targets:

1. Add replay call-site/family counters and a per-request graph replay trace to
   identify which PIECEWISE subgraph is replayed immediately before the color
   branch flip.
2. Try selective family-level replay bypass, starting with GDN/Mamba and then
   logits/LM-head, instead of request-level first-N decode heuristics.
3. Repair or replace the `cudagraph_copy_inputs=true` path for XPU. The stock
   path matches the suspected stale-input class but fails at startup with an
   inductor bounds assertion.
4. Add static metadata sanitation before replay for positions, logits indices,
   slot mappings, and block tables. This is lower overhead than global graph
   disablement and directly targets stale/padded replay inputs.
5. Keep the graph-disabled lane as the only quality-safe fallback until both
   JSON and color pass at 512 repeats under any faster replay candidate.

## Replay Boundary Follow-Up

Patch snapshot:

- `patches/vllm-qwen36-decode-replay-boundary-followup-20260613af.patch`

Added opt-in replay tracing in `vllm/compilation/cuda_graph.py`:

- `VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_FILE`
- `VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_MAX_LINES`
- `VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_RANK`
- `VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_SUBMOD_REGEX`
- `VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_REQ_REGEX`
- `VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_INPUTS`
- `VLLM_XPU_CUDAGRAPH_DISABLE_SUBMOD_REGEX`

Artifacts:

- `data/qwen36-cgtrace-noasync-20260613af.log`
- `data/qwen36-quark-int8-tp4-seq1-cgtrace-noasync-json-repeat80-20260613af.json`
- `data/qwen36-cg-replay-trace-noasync-json-20260613af-r0.jsonl`
- `data/qwen36-cg-replay-trace-noasync-json-20260613af-r1.jsonl`
- `data/qwen36-cg-replay-trace-noasync-json-20260613af-r2.jsonl`
- `data/qwen36-cg-replay-trace-noasync-json-20260613af-r3.jsonl`
- `data/qwen36-cgbypass-firsthalf-20260613ag.log`
- `data/qwen36-cgbypass-secondhalf-20260613ag.log`
- `data/qwen36-quark-int8-tp4-seq1-cgbypass-firsthalf-json-repeat96-20260613ag.json`
- `data/qwen36-quark-int8-tp4-seq1-cgbypass-secondhalf-json-repeat96-20260613ag.json`

Findings:

- The focused JSON canary still failed at repeat `53` with
  `{"question": "12 30.", "unit": "widgets"}`.
- Prompt pass for the adjacent good/bad requests was direct:
  `cudagraph_mode=NONE`, `36` tokens.
- Every decode token replayed all `41` PIECEWISE graph wrappers.
- The traced wrappers map to even `submod_N` entries from the compiled
  backbone graph: `submod_0, submod_2, ..., submod_80`.
- The bad request has more replay events only because the already-corrupt
  branch generates a longer/wrong continuation. The count difference does not
  identify the first bad subgraph by itself.

Selective hybrid replay bypass was not a valid repair path yet:

- First-half direct / second-half replay failed immediately at repeat `0` with
  `{"\n\n`.
- Second-half direct / first-half replay failed at repeat `4` with
  `{"answer": "42", "unit":baka": "widgets"}`.
- Interpretation: once a subgraph is run direct, downstream captured graphs are
  still replaying against their captured/static input addresses. Per-subgraph
  bypass is therefore invalid unless the replay boundary buffers are refreshed
  or all downstream graph segments are also forced direct.

Next action:

- Run `VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_INPUTS=1` on the same adjacent JSON
  request pair.
- Compare captured input addresses against live replay tensor addresses for
  the first good/bad decode steps.
- If live dynamic tensor addresses differ from captured graph inputs, add an
  opt-in small/dynamic replay-input copy path before `cudagraph.replay()`.

## Replay Correctness Follow-Up 2026-06-13am-ar

Patch snapshot:

- `patches/vllm-qwen36-decode-replay-directdigest-nativequantoff-20260613am.patch`

New instrumentation and knobs:

- `direct_start` / `direct_finish` replay trace events, including optional
  output digests.
- Recursive output digest tracing with
  `VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_DIGEST=1`.
- `VLLM_XPU_DISABLE_NATIVE_INT8_ACTIVATION_QUANT=1`, which keeps W8A8 GEMM
  but falls back from native XPU per-token activation quant to the Python
  `per_token_quant_int8` path.
- `VLLM_XPU_CUDAGRAPH_CLEAR_ON_PREFILL=1`, a rejected request-boundary graph
  clear/recapture diagnostic.
- `VLLM_XPU_CUDAGRAPH_PER_WRAPPER_POOL=1` and
  `VLLM_XPU_CUDAGRAPH_NO_GLOBAL_POOL=1`, per-wrapper/no-global graph pool
  diagnostics.

Artifacts:

- `data/qwen36-cgtrace-inputs-20260613ah.log`
- `data/qwen36-quark-int8-tp4-seq1-cgtrace-inputs-json-repeat80-20260613ah.json`
- `data/qwen36-cg-replay-trace-inputs-json-20260613ah-r0.jsonl`
- `data/qwen36-cgtrace-digest-20260613ai.log`
- `data/qwen36-quark-int8-tp4-seq1-cgtrace-digest-json-repeat80-20260613ai.json`
- `data/qwen36-cg-replay-trace-digest-json-20260613ai-r0.jsonl`
- `data/qwen36-cgtrace-directdigest-20260613aj.log`
- `data/qwen36-quark-int8-tp4-seq1-cgtrace-directdigest-json-repeat80-20260613aj.json`
- `data/qwen36-cg-replay-trace-directdigest-json-20260613aj-r0.jsonl`
- `data/qwen36-gdnreuseoff-20260613ak.log`
- `data/qwen36-quark-int8-tp4-seq1-gdnreuseoff-noasync-fixed-json-repeat512-20260613ak.json`
- `data/qwen36-syncreplay-20260613al.log`
- `data/qwen36-quark-int8-tp4-seq1-syncreplay-zeronative-noasync-fixed-json-repeat512-20260613al.json`
- `data/qwen36-nativequantoff-20260613am.log`
- `data/qwen36-quark-int8-tp4-seq1-nativequantoff-noasync-fixed-json-repeat512-20260613am.json`
- `data/qwen36-clearprefill-20260613an.log`
- `data/qwen36-quark-int8-tp4-seq1-clearprefill-noasync-fixed-json-repeat512-20260613an.json`
- `data/qwen36-decodeoff-trace-20260613ao.log`
- `data/qwen36-quark-int8-tp4-seq1-decodeoff-directdigest-json-repeat80-20260613ao.json`
- `data/qwen36-cg-replay-trace-decodeoff-directdigest-json-20260613ao-r0.jsonl`
- `data/qwen36-perpool-20260613ap.log`
- `data/qwen36-quark-int8-tp4-seq1-perpool-noasync-fixed-json-repeat80-20260613ap.json`
- `data/qwen36-stockcollectives-20260613aq.log`
- `data/qwen36-quark-int8-tp4-seq1-stockcollectives-noasync-fixed-json-repeat80-20260613aq.json`
- `data/qwen36-stockcollectives-fresh-20260613ar.log`
- `data/qwen36-quark-int8-tp4-seq1-stockcollectives-fresh-noasync-fixed-json-repeat80-20260613ar.json`

Findings:

- Input-address replay trace ruled out a simple stale pointer bug. Captured
  graph input addresses and live replay tensor addresses matched for the
  failing JSON request.
- Digest tracing narrowed the first adjacent good/bad divergence to the
  boundary between replayed `submod_0` and direct `submod_1`
  `gdn_attention_core_xpu` in the first layer.
- Direct-output tracing showed the bad request is already corrupt during the
  next direct prefill `submod_0`: identical prompt inputs produced tiny garbage
  and NaNs in rank-0 BF16 outputs such as the `[36, 2048]` tensor.
- With `VLLM_XPU_DISABLE_DECODE_CUDAGRAPH_REPLAY=1`, the JSON canary passed
  `80/80` repeats and the request `52`/`53` `submod_0` direct prefill digests
  were identical and NaN-free. This confirms the direct prefill corruption is a
  downstream effect of repeated decode graph replay.

Rejected candidates:

- `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=0`: still failed at repeat `53`.
- `VLLM_XPU_SYNC_CUDAGRAPH_REPLAY=1`: still failed at repeat `53`.
- `VLLM_XPU_DISABLE_NATIVE_INT8_ACTIVATION_QUANT=1`: still failed at repeat
  `53`; native activation quant is not the primary trigger.
- `VLLM_XPU_CUDAGRAPH_CLEAR_ON_PREFILL=1`: failed immediately with
  `CachingHostAllocator.h:773 it->second->use_count > 0` during runtime graph
  recapture. Runtime recapture remains unsafe on this XPU stack.
- `VLLM_XPU_CUDAGRAPH_PER_WRAPPER_POOL=1`: startup passed, but JSON still
  failed at repeat `53`; shared graph-pool aliasing is not sufficient.
- Custom collective lowering off with a fresh cache root
  (`VLLM_XPU_USE_CUSTOM_OP_COLLECTIVES=0`,
  `VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP=0`) still failed at repeat `53`.
  The fresh compile log no longer showed `vllm::all_reduce` alias warnings, so
  the custom collective op path is not the primary trigger.

Current interpretation:

- The failure is not tokenizer, sampler, HTTP, weak output refs, activation
  quant, GDN quant-buffer reuse, simple async replay ordering, graph-pool
  sharing, or custom collective lowering.
- The remaining likely trigger is a graph-captured custom kernel or custom op
  with hidden mutable/scratch state that corrupts later direct prefill
  allocations or writes after enough decode replays.

Next actions:

1. Add a selective W8A8 INT8 linear BF16 fallback diagnostic. If it survives
   replay-on JSON past repeat `53`, the native `int8_gemm_w8a8` path is the
   leading suspect.
2. If the BF16 fallback is too large to fit globally, add a layer/submod-scoped
   fallback or trace around layer-0 dense projections first.
3. Add replay-count-triggered direct-output digest around `submod_0` with the
   normal replay-on path to confirm whether the corruption appears abruptly at a
   specific replay count.
4. Keep `VLLM_XPU_DISABLE_DECODE_CUDAGRAPH_REPLAY=1` as the correctness-safe
   fallback while searching for a replay-on repair.

## INT8 Linear / MoE Fallback Follow-Up 2026-06-13as-av

Patch snapshot:

- `patches/vllm-qwen36-decode-replay-moe-bf16fallback-20260613av.patch`

New diagnostics:

- `VLLM_XPU_INT8_LINEAR_BF16_FALLBACK=1`
  - Dequantizes each XPU W8A8 linear weight to BF16 once after loading and
    runs `F.linear` instead of the native XPU INT8 GEMM path.
- `VLLM_XPU_INT8_MOE_BF16_FALLBACK=decode`
  - Dequantizes Quark W8A8 MoE weights to BF16 once after loading and uses a
    Python/Torch exact-ish routed MoE fallback only for single-token decode.
  - Keeps the native XPU MoE path for prefill to avoid the larger memory and
    compile blast radius.

Artifacts:

- `data/qwen36-int8linear-bf16fallback-20260613as.log`
- `data/qwen36-quark-int8-tp4-seq1-int8linear-bf16fallback-noasync-fixed-json-repeat80-20260613as.json`
- `data/qwen36-tritonmoe-20260613at.log`
- `data/qwen36-moebf16decode-lowmem-20260613au.log`
- `data/qwen36-moebf16decode-20260613av.log`
- `data/qwen36-quark-int8-tp4-seq1-moe-bf16decode-noasync-fixed-json-repeat80-20260613av.json`

Findings:

- Global INT8 linear BF16 fallback still failed at repeat `53` with a
  runaway `!` sequence. Native XPU W8A8 dense GEMM is not sufficient to explain
  the replay corruption.
- Forced `--moe-backend triton` did not start because the Triton backend does
  not support the Quark INT8 activation/weight quant key combination for this
  model.
- Decode-only BF16 MoE fallback loaded successfully at
  `gpu_memory_utilization=0.95`:
  - model load memory: `23.59 GiB`
  - available KV cache memory: `6.49 GiB`
  - graph capture memory: `0.34 GiB`
- Decode-only BF16 MoE fallback still failed at repeat `53` with
  `{"question": "12 30.", "unit": "widgets"}`. The native XPU fused MoE decode
  kernel is also not sufficient to explain the replay corruption.

Updated interpretation:

- The remaining high-probability zone is now the GDN/attention decode path or
  its metadata/state/scratch interaction with replay, because direct digest
  already showed the first adjacent good/bad difference entering
  `gdn_attention_core_xpu`, while dense INT8, activation quant, custom
  collectives, and native MoE have all been rejected as sole causes.

Next actions:

1. Inspect `gdn_attn.py` and `gdn_linear_attn.py` for persistent decode
   metadata, state-index tensors, temporary buffers, and XPU custom op calls
   that may be captured by graph replay.
2. Add the smallest GDN-specific correctness knob:
   either force the GDN decode core to run outside replay, clone/zero its
   mutable state inputs, or disable a suspicious XPU fused path.
3. Re-run the same JSON canary to check whether the repeat-53 failure moves or
   disappears.

## GDN Native Fallback Follow-Up 2026-06-13aw-ay

Patch snapshot:

- `patches/vllm-qwen36-decode-replay-gdn-native-fallback-20260613ay.patch`

New diagnostic knob:

- `VLLM_XPU_GDN_NATIVE_FALLBACK=decode`
  - For non-spec decode only, bypasses the fused native
    `torch.ops._xpu_C.gdn_attention` path and unpacks the projected QKV/Z/B/A
    tensors before calling the existing Python/Triton GDN core.
  - Prefill remains on the native fused XPU GDN op.
- `VLLM_XPU_GDN_NATIVE_FALLBACK=all`
  - Intended to bypass native fused XPU GDN for both prefill and decode.
  - Currently rejected because the prefill FLA/Triton path fails under Intel
    Triton on the first live request.
- The decode fallback now calls `_forward_core(...)`, so
  `VLLM_ENABLE_FLA_PACKED_RECURRENT_DECODE=0` can switch the fallback from the
  packed recurrent decode path to the alternate recurrent update path.

Artifacts:

- `data/qwen36-gdnfallbackdecode-20260613aw.log`
- `data/qwen36-quark-int8-tp4-seq1-gdnfallbackdecode-noasync-fixed-json-repeat80-20260613aw.json`
- `data/qwen36-gdnfallbackall-20260613ax.log`
- `data/qwen36-quark-int8-tp4-seq1-gdnfallbackall-noasync-fixed-json-repeat80-20260613ax.json`
- `data/qwen36-gdnfallbackdecode-nopacked-20260613ay.log`
- `data/qwen36-quark-int8-tp4-seq1-gdnfallbackdecode-nopacked-noasync-fixed-json-repeat80-20260613ay.json`

Results:

- `VLLM_XPU_GDN_NATIVE_FALLBACK=decode`
  - Startup passed.
  - Model load memory: `8.58 GiB`.
  - Available KV cache memory: `20.67 GiB`.
  - Graph capture reported `-6.16 GiB`.
  - JSON canary failed at repeat `66` after `67` completed requests.
  - Mismatch:
    `{"answer": "42", " whiskey whiskey whiskey whiskey": "widgets"}`.
- `VLLM_XPU_GDN_NATIVE_FALLBACK=all`
  - Startup passed, but the first live request returned HTTP 500.
  - Root failure:
    `RuntimeError: PassManager::run failed` inside Intel Triton while compiling
    the FLA prefill `chunk_gated_delta_rule` path.
  - Rejected as a correctness test until the prefill fallback can be made
    compile-safe.
- `VLLM_XPU_GDN_NATIVE_FALLBACK=decode` plus
  `VLLM_ENABLE_FLA_PACKED_RECURRENT_DECODE=0`
  - Startup passed.
  - Graph capture reported `-0.04 GiB`.
  - JSON canary again failed at repeat `66` after `67` completed requests.
  - Mismatch:
    `{"answer": "42", " whiskey whiskey whiskey whiskey "unit": "widgets"}`.

Updated interpretation:

- Bypassing fused native XPU GDN decode moves the failure from repeat `53` to
  repeat `66`, so native GDN decode is implicated in the original corruption
  window.
- The remaining repeat-66 failure is not explained by the packed recurrent
  fallback path, because disabling packed recurrent decode did not move the
  failure.
- The next trace should compare adjacent good/bad requests under
  `VLLM_XPU_GDN_NATIVE_FALLBACK=decode` to determine whether the first
  divergence has moved past the GDN boundary or remains in graph replay output.

Next actions:

1. Run replay output digest tracing for adjacent requests `65` and `66` with
   `VLLM_XPU_GDN_NATIVE_FALLBACK=decode`.
2. If the first divergence is still before/at the first GDN boundary, add GDN
   fallback-branch state/output trace and compare selected conv/SSM state.
3. If the first divergence moves to a later subgraph, target that graph family
   next rather than continuing to widen GDN fallbacks.

## Sampler And Prefill Replay Repair 2026-06-14ba-bd

Patch snapshots:

- `patches/vllm-qwen36-decode-replay-gdn-native-fallback-20260613ay.patch`
- `patches/vllm-qwen36-xpu-greedy-topk-fallback-20260614bd.patch`

New diagnostic/correctness knob:

- `VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1`
  - On XPU, replaces greedy `logits.argmax(dim=-1)` with
    `torch.topk(logits, k=1, dim=-1).indices`.
  - This is mathematically equivalent for greedy sampling, so it should not
    change quality when the logits are correct.

Key trace finding:

- With `VLLM_XPU_GDN_NATIVE_FALLBACK=decode`, the JSON canary moved from the
  original repeat-53 failure to repeat 66.
- Replay microscope on adjacent requests showed the model logits were already
  correct at the first remaining JSON failure:
  - good and bad request top-1 logit token was `3715` on all ranks.
  - `sampler_output.sampled_token_ids` was wrong on the bad request
    (`62085` on rank 0 and `5` on ranks 1-3).
- Replacing XPU greedy `argmax` with top-k fixed that sampler-side corruption.

Artifacts:

- `data/qwen36-gdnfallbackdecode-microscope-20260614ba.log`
- `data/qwen36-replay-microscope-gdnfallbackdecode-json-20260614ba-r{rank}.jsonl`
- `data/qwen36-gdnfallbackdecode-topkgreedy-20260614bb.log`
- `data/qwen36-quark-int8-tp4-seq1-gdnfallbackdecode-topkgreedy-json-repeat96-20260614bb.json`
- `data/qwen36-quark-int8-tp4-seq1-gdnfallbackdecode-topkgreedy-color-repeat96-20260614bb.json`
- `data/qwen36-gdnfallbackdecode-topkgreedy-colortrace-20260614bc.log`
- `data/qwen36-replay-microscope-topkgreedy-color-20260614bc.jsonl`
- `data/qwen36-quark-int8-tp4-seq1-gdnfallbackdecode-topkgreedy-json-repeat96-20260614bc.json`
- `data/qwen36-quark-int8-tp4-seq1-gdnfallbackdecode-topkgreedy-color-repeat96-20260614bc.json`

Results before the prefill replay guard:

- `VLLM_XPU_GDN_NATIVE_FALLBACK=decode` plus
  `VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1`:
  - JSON canary passed `96/96`.
  - Color canary still failed after JSON warmup at repeat `74`.
- The color microscope showed a different failure class:
  - The first generated color token was already wrong.
  - At `num_computed_tokens_cpu=0`, request `73` produced the expected
    first-token top-1 `11855` (`blue`), while request `74` produced top-1
    `9092`.
  - The sampler followed the top logit correctly.
  - `sample_hidden_states` were corrupt before logits and split by rank group:
    ranks 0-1 and ranks 2-3 had different fingerprints.

Working correctness stack:

- `VLLM_XPU_GDN_NATIVE_FALLBACK=decode`
- `VLLM_XPU_ZERO_FRESH_GDN_STATE=1`
- `VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1`
- `VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1`
- `--no-async-scheduling`

Validation artifacts:

- `data/qwen36-gdnfallbackdecode-topkgreedy-prefillbypass-20260614bd.log`
- `data/qwen36-quark-int8-tp4-seq1-gdnfallbackdecode-topkgreedy-prefillbypass-json-repeat96-20260614bd.json`
- `data/qwen36-quark-int8-tp4-seq1-gdnfallbackdecode-topkgreedy-prefillbypass-color-repeat96-20260614bd.json`
- `data/qwen36-quark-int8-tp4-seq1-gdnfallbackdecode-topkgreedy-prefillbypass-color-repeat256-20260614bd.json`
- `data/qwen36-quark-int8-tp4-replaycorrectness-quality-suite-20260614bd.json`
- `data/qwen36-quark-int8-tp4-replaycorrectness-p512o512-metrics-20260614bd.json`

Validation results:

- JSON canary: `96/96` passed.
- Color canary immediately after JSON warmup: `96/96` passed.
- Extended color canary after that: `256/256` passed.
- Text quality suite with thinking disabled: passed exact-answer, copy,
  arithmetic, JSON schema, 8-run repeat hash stability, and 4k-token needle
  recall.
- Short p512/o512 speed read, completions, stream, EOS ignored, two measured
  repeats after a 64-token warmup:
  - corrected after-first-chunk output throughput: `85.85 tok/s` mean.
  - end-to-end output throughput: `84.50 tok/s` mean.
  - client TTFT: `106.49 ms` mean.
  - vLLM decode time per generation token: `11.65 ms` mean.
- Startup provenance:
  - model load memory: `8.58 GiB`.
  - available KV cache memory: `20.66 GiB`.
  - graph capture memory delta: `-0.05 GiB`.
  - graph capture still active for mixed prefill/decode buckets, but the
    non-uniform prefill runtime replay boundary is bypassed.

Updated interpretation:

- The original repeat-53 JSON failure needed the GDN decode fallback.
- The next repeat-66 JSON failure was an XPU greedy `argmax` correctness issue.
- The next repeat-74 color failure was non-uniform prefill PIECEWISE replay
  corruption, not sampling.
- The current exact-output correctness stack passes the canaries that previously
  failed, without changing model weights or logits semantics.

Next actions:

1. Promote the working stack into a reproducible launcher or model-slot file so
   it is not lost.
2. Run a small quality suite against the working stack and the BF16/eager
   fallback where practical, comparing token IDs on deterministic prompts.
3. Measure the speed cost of `VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1`.
   If decode speed is unaffected, keep it for correctness and move performance
   work back to decode/MoE.
4. If prefill speed matters, localize the bad non-uniform prefill subgraph with
   `VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_SUBMOD_REGEX` and replace the broad prefill
   bypass with a narrower submodule or batch-boundary guard.

Promotion:

- `scripts/launch-qwen36-quark-int8-accepted.sh` now defaults to the passing
  correctness stack:
  - `VLLM_XPU_GDN_NATIVE_FALLBACK=decode`
  - `VLLM_XPU_ZERO_FRESH_GDN_STATE=1`
  - `VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1`
  - `VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1`
  - `VLLM_EXTRA_ARGS=--no-async-scheduling` when no extra args are supplied.
- Each value remains environment-overridable for controlled A/B tests.

## Guard Cost Ablations 2026-06-14be-bj

New reproducibility helper:

- `scripts/run-qwen36-ablation-candidate.sh`
  - Launches `scripts/launch-qwen36-quark-int8-accepted.sh` with caller-provided
    env overrides.
  - Waits for `/v1/models`.
  - Runs p512/o512 completions speed, fixed raw-ChatML JSON/color repeat
    canaries, and optionally the text quality suite.
  - Writes a single summary JSON with return codes, metrics, canary failures,
    env knobs, and artifact paths.

Artifacts:

- Native GDN, top-k sampler, prefill replay bypass, short pass:
  - `data/qwen36-ablation-no-gdnfallback-summary-20260614be.json`
  - `data/qwen36-ablation-no-gdnfallback-p512o512-20260614be.json`
  - `data/qwen36-ablation-no-gdnfallback-json-repeat96-20260614be.json`
  - `data/qwen36-ablation-no-gdnfallback-color-repeat96-20260614be.json`
- Native GDN, raw XPU argmax, prefill replay bypass:
  - `data/qwen36-ablation-no-gdnfallback-no-topk-summary-20260614bf.json`
- Native GDN, top-k sampler, prefill replay enabled:
  - `data/qwen36-ablation-no-gdnfallback-prefill-replay-summary-20260614bg.json`
- Native GDN promotion attempt after four speed repeats:
  - `data/qwen36-ablation-native-gdn-topk-prefillbypass-promotion-summary-20260614bh.json`
  - `data/qwen36-ablation-native-gdn-topk-prefillbypass-promotion-quality-suite-20260614bh.json`
- Conservative GDN fallback with sampler variants:
  - `data/qwen36-ablation-gdnfallback-clone-argmax-summary-20260614bi.json`
  - `data/qwen36-ablation-gdnfallback-max-sampler-summary-20260614bj.json`

Results:

- Accepted conservative stack from `20260614bd`:
  - corrected p512/o512 decode: `85.85 tok/s`.
  - passed JSON `96/96`, color `96/96`, extended color `256/256`, and quality
    suite.
- Native GDN with top-k sampler and prefill replay bypass:
  - Short run corrected p512/o512 decode: `94.00 tok/s`.
  - Short run passed JSON `96/96` and color `96/96`.
  - Longer promotion run after four p512/o512 speed repeats failed:
    - JSON failed at repeat `49` with
      `{"answer":"12","unit":"widgets"}`.
    - Color failed at repeat `22` with `blue, green, orange,`.
  - Quality suite still passed, showing the fixed canary repeats are catching a
    slot/reuse/runtime reliability issue that coarse quality checks miss.
  - Decision: do not promote native GDN yet.
- Native GDN plus raw XPU `argmax`:
  - corrected p512/o512 decode: `97.90 tok/s`.
  - JSON failed at repeat `39`; color failed at repeat `23`.
  - Decision: raw XPU `argmax` remains rejected.
- Native GDN plus prefill replay enabled:
  - corrected p512/o512 decode: `93.69 tok/s`, effectively no decode gain.
  - JSON passed `96/96`; color failed at repeat `36`.
  - Decision: prefill replay bypass is still required and does not explain the
    decode speed gap.
- Conservative GDN fallback plus `clone_argmax`:
  - corrected p512/o512 decode: `90.04 tok/s`.
  - JSON failed at repeat `39`; color failed at repeat `23`.
  - Decision: clone-before-argmax is not a valid replacement for top-k.
- Conservative GDN fallback plus `torch.max(...).indices`:
  - corrected p512/o512 decode: `93.56 tok/s`.
  - JSON failed at repeat `39`; color failed at repeat `23`.
  - Decision: `torch.max` shares the bad XPU reduction behavior and is rejected.

Updated interpretation:

- The top-k sampler fallback costs roughly `3.5-4 tok/s`, but the cheaper
  argmax-family alternatives tested so far are corrupt under repeated slot reuse.
- The GDN decode fallback costs roughly `8 tok/s` in short runs, but native GDN
  is not reliable enough to promote; the failure only appeared after a longer
  warm/reuse sequence.
- The prefill graph bypass is a correctness guard, not a decode throughput
  limiter.
- The best validated speed remains the conservative stack at `~85.85 tok/s`.
  The best tempting but rejected speed remains `~94-98 tok/s`, depending on
  which guard is removed.

Next actions:

1. Keep the accepted launcher conservative until a replacement passes long
   repeat canaries after speed warmup.
2. For sampler recovery, stop testing argmax-family variants unless we can route
   to a genuinely different XPU kernel; top-k is the only validated greedy
   reduction so far.
3. For the next real speed win, target GDN native replay/state correctness or a
   narrower GDN fallback:
   - trace native GDN failures after several p512/o512 warm requests;
   - compare first failing JSON/color request against the GDN fallback stack;
   - inspect conv/SSM state indices and native op output at the first bad token.
4. Continue larger decode work in parallel:
   - all-rank timing trace for the conservative stack;
   - persistent W8A8 MoE layerlet prototype;
   - TP/collective replay and topology work.

## Native GDN Trace Follow-Up 2026-06-14bk-bn

Trace artifacts:

- `data/qwen36-ablation-native-gdn-jsontrace-summary-20260614bk.json`
- `data/qwen36-ablation-native-gdn-jsontrace-json-repeat80-20260614bk.json`
- `data/qwen36-native-gdn-jsontrace-20260614bk.jsonl`
- `data/qwen36-native-gdn-jsontrace-microscope-20260614bk.jsonl`

Reproduction profile:

- Native GDN decode:
  - `VLLM_XPU_GDN_NATIVE_FALLBACK=0`
- Top-k sampler retained.
- Prefill graph replay bypass retained.
- Four p512/o512 speed repeats before the JSON canary.
- JSON request IDs around the prior failure window were traced with:
  - `JSON_REQUEST_ID_PREFIX=native-gdn-jsontrace`
  - `VLLM_XPU_GDN_TRACE_REQ_REGEX='native-gdn-jsontrace-0000(4[5-9]|5[0-2])'`
  - `VLLM_XPU_GDN_TRACE_DECODE_ONLY=1`
  - `VLLM_XPU_REPLAY_MICROSCOPE_REQ_REGEX` using the same window.

Result:

- The failure reproduced at request index `48`:
  - request ID `native-gdn-jsontrace-000048`
  - output `{"answer":"12","unit":"widgets"}`
- The adjacent traced good request `000047` produced the expected answer path.
- Replay microscope showed sampling followed logits correctly.
- Divergence was already in model logits:
  - request `000047` step 2 top token was `763`.
  - request `000048` step 2 top token was `3147`, starting the compact
    `{"answer":"12"...}` path.

Native GDN state finding:

- On the first decode step after the prompt (`xpu_num_computed_tokens=36`) and
  rank 0:
  - layer 0 `projected_states_qkvz`, `projected_states_ba`, `z`, and
    `conv_state` were identical between good request `000047` and bad request
    `000048`.
  - layer 0 selected `ssm_state` entering native GDN differed before the native
    op:
    - good request selected SSM sum: `284.500885`
    - bad request selected SSM sum: `266.058289`
  - layer 0 `core_attn_out` differed slightly after native GDN.
  - from layer 1 onward, projected inputs and states diverged and the difference
    amplified through later layers.

Interpretation:

- The native-GDN failure is not a sampler issue and not a broad prefill replay
  issue.
- The first visible mismatch is selected GDN SSM state at the first decode step.
- That points to stale/incomplete/non-deterministic GDN state production or reuse
  around prefill/decode handoff.

Rejected trace-derived fixes:

- `VLLM_XPU_ZERO_ALL_PREFILL_GDN_STATE=1`
  - Added as a diagnostic knob to zero all selected GDN state for every prefill.
  - Artifact: `data/qwen36-ablation-native-gdn-zero-all-prefill-state-summary-20260614bl.json`
  - Result: failed JSON at repeat `49` and color at repeat `22`.
  - Decision: not sufficient.
- `VLLM_XPU_GDN_NATIVE_FALLBACK_INITIAL_DECODE_STEPS=1`
  - Artifact: `data/qwen36-ablation-native-gdn-initial1-summary-20260614bm.json`
  - Corrected p512/o512 decode: `94.00 tok/s`.
  - Result: failed JSON at repeat `49` and color at repeat `22`.
  - Decision: not sufficient.
- `VLLM_XPU_GDN_NATIVE_FALLBACK_INITIAL_DECODE_STEPS=4`
  - Artifact: `data/qwen36-ablation-native-gdn-initial4-summary-20260614bn.json`
  - Corrected p512/o512 decode: `93.99 tok/s`.
  - Result: failed JSON at repeat `49` and color at repeat `22`.
  - Decision: not sufficient.

Current status:

- Native GDN still offers the tempting `~94 tok/s` lane but remains rejected.
- Full decode GDN fallback remains the only validated reliable GDN path, at
  `~85.85 tok/s`.

Next actions:

1. Compare the same traced request window against the accepted full decode GDN
   fallback stack to confirm whether fallback normalizes the selected layer-0
   SSM state or merely tolerates the mismatch.
2. Add a prefill-side GDN state trace for repeated identical prompts, not just
   decode-side trace, to determine whether the selected SSM mismatch is created
   during prefill or by decode metadata/state-index selection.
3. If prefill creates the mismatch, inspect native prefill GDN state write
   coverage and `has_initial_state` handling.
4. If decode metadata selects the wrong SSM slot, trace
   `non_spec_state_indices_tensor`, block IDs, and GDN state index mapping across
   requests 47/48.
5. In parallel, shift performance work back to non-GDN paths that do not risk
   correctness: all-rank timing and W8A8 MoE layerlet.

## W8A8 GDN Prefill Repair And Graph Gate 2026-06-14d1-d6

Problem:

- The prior W8A8 lane used `VLLM_XPU_GDN_NATIVE_FALLBACK=decode`, which still
  let native/chunked GDN prefill run on XPU.
- Quality runs showed that native/chunked GDN prefill was not safe for this
  model/runtime: one path hit device loss/OOR behavior, and the generic FLA
  chunked prefill fallback failed to compile on Intel XPU
  (`TritonIntelStrideVersioning` in `chunk_delta_h.py`).

Patch:

- `vllm/_xpu_ops.py`
  - defaulted native GDN fallback to `decode,prefill`;
  - added structured fallback parsing and timing around native GDN;
  - skipped the generic chunked prefill fallback warmup when the recurrent
    prefill fallback is enabled.
- `vllm/model_executor/layers/mamba/gdn_linear_attn.py`
  - added an XPU-only recurrent prefill fallback behind
    `VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1`;
  - used the recurrent update path for full prefill state production;
  - gathered the final state from each sequence's final token so prefill and
    decode handoff state stays correct.

Artifacts:

- Quality fix:
  - `data/qwen36-ablation-w8a8-safe-prefill-recurrent-gmem90-fixed-quality-summary-20260614d1.json`
- Fast PIECEWISE graph with packed decode:
  - `data/qwen36-ablation-w8a8-safe-prefill-recurrent-gmem90-fixed-canaries-summary-20260614d2.json`
- Fast PIECEWISE graph with packed decode disabled:
  - `data/qwen36-ablation-w8a8-safe-prefill-recurrent-gmem90-nopacked-canaries-summary-20260614d3.json`
- Eager/no graph with packed decode disabled:
  - `data/qwen36-ablation-w8a8-safe-prefill-recurrent-gmem90-eager-nopacked-canaries-summary-20260614d4.json`
- Eager/no graph with packed decode enabled:
  - `data/qwen36-ablation-w8a8-safe-prefill-recurrent-gmem90-eager-packed-canaries-summary-20260614d5.json`
- Compiled with cudagraph/XPU graph disabled and packed decode enabled:
  - `data/qwen36-ablation-w8a8-safe-prefill-recurrent-gmem90-graphnone-packed-gate-summary-20260614d6.json`

Results:

- Recurrent prefill quality fix passed:
  - quality suite `pass_all=true`;
  - `baseline_match_all=true`;
  - exact arithmetic/copy/json/exact cases passed;
  - repeat and long-context cases passed.
- PIECEWISE graph plus packed decode stayed fast but failed:
  - corrected p512/o512 decode mean: `85.26 tok/s`;
  - JSON failed at repeat `49` with
    `{"answer": "12.0", "unit": "widgets"}`;
  - color passed `96/96`.
- PIECEWISE graph plus packed decode disabled still failed:
  - JSON passed `96/96`;
  - color failed at repeat `33` with
    `blue, green, orange, </think> red`.
- Eager/no graph plus packed decode disabled passed:
  - JSON `128/128`;
  - color `128/128`.
- Eager/no graph plus packed decode enabled passed:
  - JSON `64/64`;
  - color `64/64`.
- Compiled with `COMPILATION_CONFIG='{"cudagraph_mode":"NONE"}'`,
  `XPU_GRAPH=0`, `VLLM_XPU_ENABLE_XPU_GRAPH=0`,
  `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=0`, recurrent prefill fallback enabled, and
  packed decode enabled passed the full gate:
  - corrected p512/o512 decode mean: `13.98 tok/s`;
  - JSON `128/128`;
  - color `128/128`;
  - quality suite `pass_all=true`, `baseline_match_all=true`.

Interpretation:

- The recurrent GDN prefill fallback is correct under no graph replay.
- Packed recurrent decode appears correct outside graph replay.
- The remaining correctness fault is decode graph replay or its interaction with
  static buffers/slot reuse, not the recurrent prefill math and not packed decode
  alone.
- The correctness-safe W8A8 lane is now graph replay disabled at
  `GPU_MEMORY_UTILIZATION=0.90`. It is valid but much too slow for the final
  performance target.
- The fast graph lane remains rejected until it can pass the same repeat
  canaries and quality suite after warm speed runs.

Promotion:

- `scripts/launch-qwen36-quark-int8-accepted.sh` now defaults to the safe lane:
  - `GPU_MEMORY_UTILIZATION=0.90`;
  - `COMPILATION_CONFIG='{"cudagraph_mode":"NONE"}'`;
  - `XPU_GRAPH=0`;
  - `VLLM_XPU_ENABLE_XPU_GRAPH=0`;
  - `VLLM_XPU_FORCE_GRAPH_WITH_COMM=0`;
  - `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=0`;
  - `VLLM_XPU_GDN_NATIVE_FALLBACK=decode,prefill`;
  - `VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1`;
  - `VLLM_XPU_ZERO_FRESH_GDN_STATE=1`;
  - `VLLM_EXTRA_ARGS=--no-async-scheduling` when no override is supplied.
- `scripts/run-qwen36-ablation-candidate.sh` now records graph mode, XPU graph
  toggles, packed decode, memory utilization, and compilation config in summary
  JSON for future A/B runs.

Next actions:

1. Keep this no-graph lane as the correctness oracle for W8A8 XPU.
2. Repair selective decode graph replay instead of broad no-graph execution:
   - compare first divergence between PIECEWISE and no-graph on the same canary
     window;
   - trace graph replay input/output digests around GDN state, MoE outputs, and
     collectives;
   - test copy/sanitize of only replayed static buffers that are reused across
     requests.
3. Recover performance by re-enabling only proven-safe graph islands:
   - start with non-GDN/non-MoE subgraphs;
   - promote one island at a time through JSON/color canaries and quality suite;
   - reject any island that fails after warm p512/o512 runs.
4. Continue the larger no-quality-loss performance work:
   - all-rank decode timing with graph disabled as the correctness baseline;
   - persistent W8A8 MoE layerlet replay harness;
   - TP/collective replay and topology tests.

## Prefix Replay And Submod0 Direct-Compare 2026-06-14e1-e4

Goal:

- Determine whether a safe prefix of PIECEWISE graph replay can be promoted, or
  whether corruption starts in the first replay island.
- Compare the first replay island against direct execution on the same live
  inputs.

Patch:

- `vllm/compilation/cuda_graph.py`
  - added `VLLM_XPU_CUDAGRAPH_REPLAY_MAX_PIECEWISE_INDEX` to replay only a
    prefix of piecewise graphs and run later graphs direct;
  - added direct-vs-replay trace support with
    `VLLM_XPU_CUDAGRAPH_COMPARE_DIRECT_REGEX`;
  - added diagnostic output zeroing with
    `VLLM_XPU_CUDAGRAPH_ZERO_REPLAY_OUTPUT_REGEX` and
    `VLLM_XPU_CUDAGRAPH_ZERO_REPLAY_OUTPUT_INDICES`.
- `scripts/run-qwen36-ablation-candidate.sh`
  - records replay prefix, replay sync, compare-direct, and replay-output
    zeroing envs in summary JSON.

Artifacts:

- Prefix0 replay:
  - `data/qwen36-ablation-w8a8-safe-prefill-recurrent-gmem90-piecewise-prefix0-summary-20260614e1.json`
- Prefix0 direct-compare trace:
  - `data/qwen36-ablation-w8a8-safe-prefill-recurrent-gmem90-piecewise-prefix0-compare-summary-20260614e2.json`
  - `data/qwen36-prefix0-compare-20260614e2-r0.jsonl`
  - `data/qwen36-prefix0-compare-20260614e2-r1.jsonl`
  - `data/qwen36-prefix0-compare-20260614e2-r2.jsonl`
  - `data/qwen36-prefix0-compare-20260614e2-r3.jsonl`
- Prefix0 with replay sync:
  - `data/qwen36-ablation-w8a8-safe-prefill-recurrent-gmem90-piecewise-prefix0-sync-summary-20260614e3.json`
- Prefix0 with selected replay outputs zeroed:
  - `data/qwen36-ablation-w8a8-safe-prefill-recurrent-gmem90-piecewise-prefix0-zero-empty-summary-20260614e4.json`
- Prefix0 direct-return diagnostic:
  - `data/qwen36-ablation-w8a8-safe-prefill-recurrent-gmem90-piecewise-prefix0-return-direct-summary-20260614e5.json`
  - `data/qwen36-prefix0-return-direct-20260614e5-r0.jsonl`
  - `data/qwen36-prefix0-return-direct-20260614e5-r1.jsonl`
  - `data/qwen36-prefix0-return-direct-20260614e5-r2.jsonl`
  - `data/qwen36-prefix0-return-direct-20260614e5-r3.jsonl`

Results:

- Prefix0 replay alone failed:
  - corrected p512/o512 decode mean: `14.20 tok/s`;
  - JSON failed at repeat `4` with `{"answer": "42", "unit": "widgets widgets"}`;
  - color passed `64/64`.
- Direct-vs-replay compare on `piecewise:0/41` showed:
  - 78 compare records per TP rank;
  - real numeric outputs matched exactly on every rank:
    - output `$[0]` zeros buffer: `0` max diff;
    - output `$[2]` qkvz projection: `0` max diff;
    - output `$[3]` ba projection: `0` max diff;
    - output `$[6]` embedding all-reduce: `0` max diff;
  - only deliberate `empty` outputs differed:
    - `$[1]` GDN `z` scratch/output buffer;
    - `$[5]` `self_attention_output` scratch/output buffer;
  - max observed diff on empty buffers: `34.302734375`.
- The direct-compare run itself passed JSON `8/8` and color `1/1`, but this is
  not accepted as a speed or correctness win because the extra direct execution
  perturbs runtime state.
- Prefix0 with `VLLM_XPU_SYNC_CUDAGRAPH_REPLAY=1` failed:
  - corrected p512/o512 decode mean: `14.41 tok/s`;
  - JSON failed at repeat `29` with malformed quoting:
    `{"answer": 42', 'unit': 'widgets'}`;
  - color failed at repeat `12` with `blue, green- red- yellow`.
- Prefix0 with replay outputs `$[1]` and `$[5]` zeroed failed identically:
  - corrected p512/o512 decode mean: `14.40 tok/s`;
  - JSON failed at repeat `29` with malformed quoting:
    `{"answer": 42', 'unit': 'widgets'}`;
  - color failed at repeat `12` with `blue, green- red- yellow`.
- Prefix0 with replay followed by direct submod0 and direct output returned
  still failed:
  - metrics skipped;
  - JSON failed at repeat `32` with nested/braced output:
    `{"{"answer": "42", "unit": "widgets"}"}`;
  - color passed `64/64`;
  - trace logs were about `4.8 MB` per TP rank.

Interpretation:

- A safe replay prefix does not currently exist. Replaying only `piecewise:0`
  is enough to corrupt deterministic canaries.
- The first replay island's math outputs compare cleanly against direct
  execution on live inputs. The mismatch is not the W8A8 projection math,
  embedding all-reduce, or RMSNorm result inside submod0.
- Simple stream synchronization and zeroing the known-empty replay outputs do
  not repair the failure.
- Returning direct submod0 outputs does not repair the failure either. The
  fault is therefore not just the first graph island's returned tensor values.
- The likely fault is graph replay state outside submod0 tensor equality:
  scheduler/slot state, a later consumer interaction, allocator/pool state, or
  another graph/direct boundary side effect. The direct-compare side effect
  passing short canaries was not a valid repair.

Rejected:

- Prefix-only replay as an incremental promotion strategy.
- Replay sync as the fix for prefix0 corruption.
- Zeroing submod0 empty outputs `$[1]` and `$[5]` as the fix for prefix0
  corruption.
- Returning direct submod0 outputs as the fix for prefix0 corruption.

Next:

1. Stop treating PIECEWISE replay as an incremental promotion path until a
   deeper graph-runtime issue is found.
2. Keep graph-disabled W8A8 as the correctness oracle.
3. Move effort to one of two paths:
   - full direct decode optimization, especially persistent W8A8/GDN/MoE
     layerlets with explicit owned buffers;
   - lower-level XPU graph/runtime debugging outside vLLM with a reduced
     submod0/submod1 reproducer.
4. If graph replay is revisited, build the reduced reproducer first:
   - submod0 output tuple plus submod1 GDN consumer;
   - repeated replay/direct loops with token-ID canary state;
   - explicit checks for allocator/pool reuse, stream ordering, and custom-op
     mutation.

## 2026-06-14 Native-Decode / Safe-Prefill Follow-Up

Goal:

- Find a correctness-preserving path between the slow accepted graph-disabled
  launcher and the fast but rejected forced-graph lane.
- Determine whether corruption is in native GDN decode, prefill state handling,
  collectives, or forced communication graph replay.

Code changes:

- `vllm/model_executor/layers/mamba/gdn_linear_attn.py`
  - replaced the XPU recurrent-prefill in-place boolean mask assignment with an
    out-of-place `torch.where` zeroing path. This fixed the device-lost crash
    seen in recurrent prefill fallback.
- `scripts/check-qwen36-gdn-prefill-state-stability.py`
  - added a focused single-layer GDN prefill state stability harness.
- `scripts/run-qwen36-ablation-candidate.sh`
  - summary JSON now includes normalized speed fields and gate decisions.
  - added missing graph/collective flags to future summaries:
    `VLLM_XPU_USE_CUSTOM_OP_COLLECTIVES`,
    `VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP`,
    `VLLM_XPU_CUSTOM_ALLREDUCE_GRAPH_CLONE_INPUT`, and
    `VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT`.

Artifacts:

- Forced graph, native decode, safe prefill, short gate:
  - `data/qwen36-ablation-native-decode-safe-prefill-graph-summary-20260614f1.json`
- Forced graph, full gate before prefill crash fix:
  - `data/qwen36-ablation-native-decode-safe-prefill-graph-full-summary-20260614f2.json`
  - `data/qwen36-ablation-native-decode-safe-prefill-graph-full-20260614f2.log`
- Forced graph, full gate after `torch.where` crash fix:
  - `data/qwen36-ablation-native-decode-safe-prefill-where-full-summary-20260614f3.json`
- GDN prefill state stability harness:
  - `data/qwen36-gdn-prefill-state-stability-f4.json`
  - `data/qwen36-gdn-prefill-state-stability-f4.md`
- Forced graph, layer-0 decode fallback:
  - `data/qwen36-ablation-native-decode-safe-prefill-layer0-summary-20260614f5.json`
- Forced graph, layers 0-3 decode fallback:
  - `data/qwen36-ablation-native-decode-safe-prefill-layer0-3-summary-20260614f6.json`
- Forced graph, layers 0-3 trace:
  - `data/qwen36-ablation-native-decode-safe-prefill-layer0-3-tracecolor-summary-20260614f7.json`
  - `data/qwen36-replay-microscope-layer03-color-f7.jsonl`
- Forced graph, layers 0-3 with all GDN prefill state zeroed:
  - `data/qwen36-ablation-native-decode-safe-prefill-layer0-3-zeroall-summary-20260614f8.json`
- Graph disabled, layers 0-3 decode fallback:
  - `data/qwen36-ablation-native-decode-safe-prefill-layer0-3-graphnone-summary-20260614f9.json`
  - `data/qwen36-ablation-native-decode-safe-prefill-layer0-3-graphnone-metrics-summary-20260614fa.json`
- Forced graph, full slot trace:
  - `data/qwen36-ablation-native-decode-safe-prefill-layer0-3-slottrace-summary-20260614fb.json`
  - `data/qwen36-replay-microscope-layer03-color-slots-fb.jsonl`
- Forced graph with stock collectives:
  - `data/qwen36-ablation-native-decode-safe-prefill-layer0-3-stockcollectives-summary-20260614fc.json`
- Graph enabled but without forced comm capture / no-op comm capture:
  - `data/qwen36-ablation-native-decode-safe-prefill-layer0-3-graphnocomm-summary-20260614fd.json`
  - `data/qwen36-ablation-native-decode-safe-prefill-layer0-3-graphnocomm-metrics-summary-20260614fe.json`

Results:

- `20260614f1` short gate looked promising:
  - corrected p512/o512 decode mean: `93.31 tok/s`;
  - JSON `64/64` passed;
  - color `64/64` passed;
  - quality suite skipped.
- `20260614f2` full gate crashed before metrics:
  - `UR_RESULT_ERROR_DEVICE_LOST`;
  - crash site was recurrent prefill fallback boolean-mask assignment in
    `gdn_linear_attn.py`.
- `20260614f3` after the `torch.where` crash fix completed but was rejected:
  - corrected p512/o512 decode mean: `93.15 tok/s`;
  - quality suite passed and matched baseline;
  - JSON failed at repeat `48` with answer `12`;
  - color failed at repeat `91` with `blue, green, red, yellow`.
- `20260614f4` standalone GDN prefill state stability passed:
  - 16 iterations;
  - max diff `0` for core output, `z`, conv state, and SSM state;
  - this rules out a simple raw GDN prefill cache-row nondeterminism outside
    the full vLLM/graph runtime.
- `20260614f5` forced graph with layer-0 decode fallback was rejected:
  - corrected p512/o512 decode mean: `90.02 tok/s`;
  - JSON `128/128` passed;
  - color failed at repeat `19` with early stop:
    `blue, green, orange,`.
- `20260614f6` forced graph with layers 0-3 decode fallback was rejected:
  - metrics skipped;
  - JSON `128/128` passed;
  - color failed at repeat `127` with `blue, green, red, yellow`.
- `20260614f7` replay microscope showed the bad token was already in logits:
  - bad request: `f7-color-000022`;
  - output: `blue, green, red, yellow`;
  - at the decisive step after `blue, green,`, token `red` had logit `23.875`
    and `orange` had `22.5`;
  - the bad request's first prefill logits were already different from
    adjacent good requests, before any decode token for that request.
- `20260614f8` forced graph with all GDN prefill state zeroed was rejected:
  - JSON `128/128` passed;
  - color failed at repeat `127` with `blue, green, red, yellow`;
  - stale/fresh GDN state zeroing alone is not the fix.
- `20260614f9` graph-disabled lane passed canaries:
  - JSON `128/128` passed;
  - color `256/256` passed.
- `20260614fa` graph-disabled metrics:
  - corrected p512/o512 decode mean: `15.47 tok/s`;
  - decode mean: `64.63 ms/token`;
  - correct but not useful as a speed win.
- `20260614fb` full slot trace:
  - bad request again failed at repeat `22`;
  - prefill padding slots were clean `-1`;
  - decode slot mappings were one real slot per step;
  - this did not support a simple padded slot-map overwrite.
- `20260614fc` forced graph with stock collectives was rejected:
  - JSON `128/128` passed;
  - color failed at repeat `127`;
  - custom all-reduce alone is not the fix.
- `20260614fd` graph enabled without forced comm capture passed canaries:
  - JSON `128/128` passed;
  - color `256/256` passed.
- `20260614fe` graph enabled without forced comm capture metrics:
  - corrected p512/o512 decode mean: `15.70 tok/s`;
  - decode mean: `63.71 ms/token`;
  - correct but effectively graph-disabled speed.

Interpretation:

- The fast `~90-93 tok/s` path requires forced communication graph capture.
- Forced communication graph capture corrupts deterministic output across
  repeated single-request runs.
- The corruption can surface in a later request's direct prefill logits, after
  previous requests used graph-enabled decode. That points to replay/runtime
  state poisoning rather than sampler randomness.
- Disabling graph replay or not forcing comm capture restores canary
  correctness, but both fall back to about `15-16 tok/s`.
- Stock collectives do not fix the forced-graph failure, so the bug is not only
  the custom all-reduce op implementation.
- Clean prefill padding slots reduce the likelihood of a simple padded
  slot-mapping overwrite, though cache/scratch aliasing is still possible.

Rejected:

- Promoting forced-graph native decode with recurrent safe prefill.
- Layer-0-only GDN decode fallback.
- Layers 0-3 GDN decode fallback.
- Zeroing all GDN prefill state as the repair.
- Stock collectives as the repair for forced graph.
- Graph enabled without forced comm capture as a speed win.

Accepted as oracles only:

- Graph-disabled W8A8 lane: correct, about `15.47 tok/s`.
- Graph-enabled without forced comm capture: correct, about `15.70 tok/s`.

Next:

1. Treat `VLLM_XPU_FORCE_GRAPH_WITH_COMM=1` plus
   `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1` as the corruption boundary.
2. Build a reduced forced-comm graph replay reproducer around the first graph
   island and its collective/scratch behavior, rather than continuing endpoint
   A/B guesses.
3. Add or reuse trace hooks that can compare state before and after replay
   across requests, including allocator addresses, graph-owned output buffers,
   collective wait tensors, and any persistent scratch tensors.
4. In parallel, keep the graph-disabled lane as the correctness oracle while
   optimizing direct decode only if graph-runtime repair stalls.

## 2026-06-14g Forced-Graph Recapture Diagnostic

Goal:

- Determine whether the forced-comm graph corruption is stale graph replay
  state or corruption that happens within a single replay/capture transaction.
- Try to turn that diagnosis into a narrower mitigation by recapturing only the
  first PIECEWISE graph island.

Patch:

- `vllm/compilation/cuda_graph.py`
  - added `VLLM_XPU_CUDAGRAPH_RECAPTURE_REGEX` so
    `VLLM_XPU_CUDAGRAPH_RECAPTURE_AFTER_N_REPLAYS` can target selected graph
    wrappers instead of every wrapper.
- `scripts/run-qwen36-ablation-candidate.sh`
  - summary JSON now records `VLLM_XPU_CUDAGRAPH_RECAPTURE_AFTER_N_REPLAYS`,
    `VLLM_XPU_CUDAGRAPH_RECAPTURE_REGEX`, and
    `VLLM_XPU_CUDAGRAPH_ALLOW_RUNTIME_RECAPTURE`.

Results:

- Global recapture every replay:
  - artifact:
    `data/qwen36-ablation-forcedcomm-recapture1-canary-summary-20260614g1.json`
  - JSON canary: `128/128` pass.
  - Color canary: `128/128` pass.
- Global recapture every 8 replays:
  - artifact:
    `data/qwen36-ablation-forcedcomm-recapture8-canary-summary-20260614g2.json`
  - JSON canary: `128/128` pass.
  - Color canary: `128/128` pass.
- Global recapture every 64 replays:
  - artifact:
    `data/qwen36-ablation-forcedcomm-recapture64-canary-summary-20260614g3.json`
  - JSON canary: `128/128` pass.
  - Color canary: `128/128` pass.
  - measured artifact:
    `data/qwen36-ablation-forcedcomm-recapture64-metrics-summary-20260614g4.json`
  - p512/o512 corrected decode mean: `14.76 tok/s`.
- Selective recapture of only `piecewise:0/` every 64 replays:
  - artifact:
    `data/qwen36-ablation-forcedcomm-recapture64-piecewise0-canary-summary-20260614g5.json`
  - JSON canary: `128/128` pass.
  - Color canary: `128/128` pass.
  - measured artifact:
    `data/qwen36-ablation-forcedcomm-recapture64-piecewise0-metrics-summary-20260614g6.json`
  - p512/o512 corrected decode mean: `14.71 tok/s`.
- No-recapture forced-graph control after the recapture runs:
  - artifact:
    `data/qwen36-ablation-forcedcomm-norecapture-control-metrics-20260614g7.log`
  - no benchmark result; startup failed with `UR_RESULT_ERROR_DEVICE_LOST` in
    `torch.xpu.empty_cache()` during rank-0 model load.
  - treat this as a reliability issue from repeated XPU launches, not a model
    speed result.

Interpretation:

- Periodic runtime recapture makes the previously corrupt forced-comm graph path
  pass the deterministic JSON/color canaries, so stale graph replay state is now
  the strongest root-cause hypothesis.
- Runtime recapture is not a deployable speed fix. Both global recapture and
  selective `piecewise:0/` recapture fall back to roughly the graph-disabled
  decode band (`14-15 tok/s`).
- The next useful repair is a low-overhead refresh/sanitize of the stale graph
  state that recapture repairs, not more layer fallbacks or broader recapture.

Rejected:

- Promoting global recapture as a performance candidate.
- Promoting selective `piecewise:0/` recapture as a performance candidate.

Next:

1. Add trace counters for actual recapture events by wrapper label to confirm
   whether `piecewise:0/` selective recapture is unexpectedly triggering slow
   graph-stack behavior.
2. Replace runtime recapture with cheaper state refresh:
   - identify graph-owned/static input buffers for `piecewise:0/`;
   - copy/sanitize only those buffers before replay;
   - avoid destroying/rebuilding the graph.
3. Revisit `cudagraph_copy_inputs=true` failure with a minimal XPU-safe copy
   implementation instead of the stock path that hit an inductor bounds assert.
4. Add a launch-cooldown/retry guard for repeated XPU benchmark runs because
   the device-lost failure appeared during startup after several heavy runs.

## 2026-06-14h Run-Config Drift Correction

Problem found:

- Several `20260614g/h` follow-up runs were not comparable to the original fast
  forced-comm graph lane because they omitted
  `COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'`.
- The accepted launcher defaults missing `COMPILATION_CONFIG` to
  `{"cudagraph_mode":"NONE"}`, so those runs silently measured the correct but
  slow graph-none class.
- This explains the apparent regression to `~15 tok/s`; it was harness drift,
  not a confirmed model/runtime speed regression.

Harness fix:

- `scripts/run-qwen36-ablation-candidate.sh`
  - for explicit fast forced-comm graph runs
    (`VLLM_XPU_GDN_NATIVE_FALLBACK=prefill`, `XPU_GRAPH=1`,
    `VLLM_XPU_ENABLE_XPU_GRAPH=1`, `VLLM_XPU_FORCE_GRAPH_WITH_COMM=1`), the
    runner now auto-fills
    `COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'` when omitted;
  - it also exports `GPU_MEMORY_UTILIZATION=0.90` for summary/provenance
    consistency;
  - `ABLATION_FAST_GRAPH_AUTOCONFIG=0` disables this behavior for intentional
    negative controls.

Harness verification:

- Autoconfig smoke run intentionally omitted `COMPILATION_CONFIG`:
  - artifact:
    `data/qwen36-ablation-fastlane-autoconfig-smoke-metrics-summary-20260614h8.json`
  - runner printed
    `COMPILATION_CONFIG={"cudagraph_mode":"PIECEWISE"}`;
  - p512/o512 corrected decode mean: `87.92 tok/s`;
  - one-repeat smoke is slower than the best restored control, but it is clearly
    in the fast graph class rather than the accidental `~15 tok/s` graph-none
    class.

Corrected fast baseline:

- Restored fast config, no request quarantine:
  - artifact:
    `data/qwen36-ablation-fastlane-config-restored-control-metrics-summary-20260614h4.json`
  - p512/o512 corrected decode mean: `93.45 tok/s`;
  - decode mean: `10.70 ms/token`;
  - this restores the original fast class.

Corrected safety result:

- Restored fast config, no request quarantine:
  - artifact:
    `data/qwen36-ablation-fastlane-config-restored-clean-canary-control-summary-20260614h6.json`
  - JSON canary: `128/128` pass;
  - color canary: failed at repeat `127`;
  - bad output: `blue, green, red, yellow` instead of
    `blue, green, orange, red`.
- Conclusion: the true fast class is still unsafe. The previous speed concern
  is corrected, but the corruption concern remains real.

Rejected corrected candidates:

- Request-level eager quarantine every 32 new requests:
  - slow-env pass:
    `data/qwen36-ablation-fastlane-eagerreq32-canary-summary-20260614h1.json`
    was not valid fast-path evidence because the compile config was missing;
  - restored fast-path run:
    `data/qwen36-ablation-fastlane-config-restored-eagerreq32-canary-summary-20260614h5.json`
    hit `UR_RESULT_ERROR_DEVICE_LOST` on the first request in
    `block_table.copy_to_gpu`;
  - do not promote. Treat as rejected/unstable pending a smaller isolated
    reproducer.
- Runtime recapture every 64 replays:
  - slow-env `20260614g` pass was not valid fast-path evidence because it used
    `GDN=decode,prefill` and no PIECEWISE compile config;
  - restored fast-path run:
    `data/qwen36-ablation-fastlane-config-restored-recapture64-canary-summary-20260614h7.json`
    failed JSON by repeat `5` and color by repeat `10`;
  - JSON failure produced an extra trailing quote/brace:
    `{"answer": "42", "unit": "widgets"}"}`;
  - color failure produced only `blue`.

Current status:

- Fast baseline is restored: `~93.45 tok/s` corrected decode.
- Fast baseline is still corrupt under repeated deterministic canaries.
- Correctness oracles remain graph-none / no forced comm graph at `~15-16 tok/s`.
- Runtime recapture and request-level eager quarantine are not accepted repairs
  on the actual fast path.

Next:

1. Stop broad endpoint A/B until each candidate uses the harness autoconfig or
   explicitly records why PIECEWISE is disabled.
2. Build the reduced forced-comm PIECEWISE replay reproducer around request
   boundaries, not runtime recapture.
3. Trace static graph input/output buffer identities, allocator addresses, and
   collective scratch tensors across good and bad requests.
4. Test a targeted static-buffer refresh/copy-input patch for the first
   request-boundary graph island, then gate it on:
   - restored fast config;
   - JSON/color canaries at 128+ repeats;
   - p512/o512 speed against the `20260614h4` baseline.

## 2026-06-14i Graph-0 Output Alias Diagnostic

Goal:

- Stop guessing which PIECEWISE graph handoff is poisoning later requests.
- Trace the restored fast lane at the first deterministic color canary failure
  and test the narrowest possible replay-output lifetime repair.

Patch:

- `vllm/compilation/cuda_graph.py`
  - trace rows now include tensor stride, storage offset, storage data pointer,
    storage byte size, and an input-address check against captured graph-entry
    addresses;
  - added env-gated replay-output cloning:
    - `VLLM_XPU_CUDAGRAPH_CLONE_REPLAY_OUTPUT_REGEX`
    - `VLLM_XPU_CUDAGRAPH_CLONE_REPLAY_OUTPUT_INDICES`
  - the clone path returns selected cloned graph outputs while leaving the
    captured graph and all unselected outputs untouched.
- `scripts/analyze-qwen36-cudagraph-trace.py`
  - added a focused analyzer for trace JSONL plus deterministic canary JSON;
  - fixed request-index parsing for vLLM completion IDs such as
    `cmpl-h12-color-000022-0-...`, so nearby good/bad requests line up.
- `scripts/run-qwen36-ablation-candidate.sh`
  - summary provenance now records the trace, zero-output, clone-output, and
    compare-direct env knobs.

Trace artifacts:

- Graph0 only:
  - run:
    `data/qwen36-ablation-fastlane-state-trace-piecewise0-color-summary-20260614h9.json`
  - trace: `data/qwen36-cudagraph-state-h9-r0.jsonl`
  - analysis: `data/qwen36-cudagraph-state-h9-analysis.json`
- Later boundaries `10,20,30,40`:
  - run:
    `data/qwen36-ablation-fastlane-state-trace-piecewise-10-20-30-40-color-summary-20260614h10.json`
  - analysis: `data/qwen36-cudagraph-state-h10-analysis.json`
- Early boundaries `1-9`:
  - run:
    `data/qwen36-ablation-fastlane-state-trace-piecewise-1-9-color-summary-20260614h11.json`
  - analysis: `data/qwen36-cudagraph-state-h11-analysis.json`
- Graph0 all replay outputs:
  - run:
    `data/qwen36-ablation-fastlane-state-trace-piecewise0-alloutputs-color-summary-20260614h12.json`
  - analysis: `data/qwen36-cudagraph-state-h12-analysis.json`

Trace findings:

- All trace runs failed at the same first bad color request, repeat `22`, with:
  `blue, green, red, yellow`.
- Graph0 input addresses matched captured entry addresses on the bad request.
  That argues against a simple wrong current-input pointer at graph0 replay.
- With only graph0 outputs `0-3` traced, requests `20`, `21`, and bad request
  `22` looked identical at computed-token step `33`.
- By `piecewise:10`, the bad request already differed from adjacent good
  requests.
- Tracing early graphs showed `piecewise:1` already differed, so the divergent
  handoff had to be graph0 output state not covered by the first four outputs.
- Tracing all graph0 outputs found the first concrete bad handoff:
  - graph0 output index `5`, shape `[1, 2048]`, dtype `bfloat16`;
  - adjacent good requests had digest sum `-10.821243286132812`;
  - bad request `22` had digest sum `-9.161483764648438`;
  - outputs `0-3` and `6` remained identical.

Repair attempts:

- Disable only `piecewise:0/41` replay:
  - artifact:
    `data/qwen36-ablation-fastlane-disable-piecewise0-canary-summary-20260614h13.json`
  - rejected immediately;
  - JSON failed at repeat `0` with repeated braces/exclamation output;
  - color failed at repeat `0` with only `blue`;
  - conclusion: graph0 cannot simply be bypassed without preserving its boundary
    contract.
- Clone only graph0 output index `5`:
  - artifact:
    `data/qwen36-ablation-fastlane-clone-piecewise0-output5-canary-summary-20260614h14.json`
  - JSON canary: `64/64` pass;
  - color canary: `192/192` pass;
  - this is a real diagnostic improvement, but it did not include a preceding
    metrics warmup.
- Clone graph0 output index `5`, then run metrics and canaries:
  - artifact:
    `data/qwen36-ablation-fastlane-clone-piecewise0-output5-metrics-summary-20260614h15.json`
  - p512/o512 corrected decode mean: `92.21 tok/s`;
  - decode mean: `10.85 ms/token`;
  - JSON failed at repeat `48` with answer `12`;
  - color failed at repeat `91` with `blue, green, red, yellow`;
  - rejected.
- Clone graph0 output indices `5,6`, then run metrics and canaries:
  - artifact:
    `data/qwen36-ablation-fastlane-clone-piecewise0-output5-6-metrics-summary-20260614h16.json`
  - p512/o512 corrected decode mean: `92.64 tok/s`;
  - decode mean: `10.80 ms/token`;
  - JSON failed at repeat `48` with answer `12`;
  - color failed at repeat `91` with `blue, green, red, yellow`;
  - rejected.

Interpretation:

- The restored fast lane remains about `92-93 tok/s`, so the harness drift
  issue is fixed, but the lane is still not quality-safe.
- Graph0 output `5` is the first confirmed corrupt graph handoff for a clean
  color-only failure.
- Cloning graph0 output `5` repairs the standalone canary sequence, which makes
  graph-output alias/lifetime a real fault class, not just a theory.
- The metrics-warmed failure has either:
  - another graph output alias after the long p512/o512 workload;
  - a later warmed-state poison that is not graph0 output `5`;
  - or a mutable downstream consumer that still mutates a graph-owned handoff
    after the cloned output boundary.
- Output cloning is therefore useful diagnostic code, not a production repair.

Rejected:

- Disabling `piecewise:0/41` replay.
- Promoting graph0 output `5` cloning without the metrics-warmed gate.
- Promoting graph0 output `5,6` cloning after the metrics-warmed gate.

Current status:

- Best corrected fast baseline remains:
  `data/qwen36-ablation-fastlane-config-restored-control-metrics-summary-20260614h4.json`
  at `93.45 tok/s`.
- Best clone diagnostic speed:
  `data/qwen36-ablation-fastlane-clone-piecewise0-output5-6-metrics-summary-20260614h16.json`
  at `92.64 tok/s`, but rejected for correctness.
- No production candidate is accepted yet.

Next:

1. Run the same graph-output trace after the metrics warmup sequence used by
   `h15/h16`, targeting the failing JSON repeat `48` and color repeat `91`.
   The clean-only h12 trace is no longer sufficient.
2. Add an alias-lifetime trace that directly logs whether graph0 output `5`
   shares storage or data pointers with graph1 tensor arguments or downstream
   mutable scratch buffers.
3. Replace manual index cloning with a principled handoff rule:
   clone or allocate an owned per-replay buffer only when a graph output is later
   used as a mutable input by the next graph island.
4. Only after the metrics-warmed canaries pass, re-run:
   - at least four p512/o512 measured repeats;
   - JSON/color canaries at 128+ repeats after metrics;
   - quality suite against the graph-disabled oracle.

## 2026-06-14j Metrics-Warmed GDN State Isolation

Why:

- h15/h16 showed graph0 output cloning was only a shallow repair.
- h22 then traced the metrics-warmed failure itself and showed the bad request
  is already divergent during graph0 direct prefill, before decode replay can
  explain it.
- The graph wrapper saw identical visible tensor arguments for adjacent
  good/bad JSON requests, so the next hypothesis was hidden/persistent GDN
  state or an untraced static buffer.

Runs:

- h17:
  `data/qwen36-ablation-fastlane-clone-piecewise0-output5-6-warmed-trace-summary-20260614h17.json`
  - config: graph0 output `5,6` cloning plus trace, metrics warmup first;
  - result: rejected as infrastructure failure, not a quality result;
  - endpoint hit `UR_RESULT_ERROR_DEVICE_LOST` inside the XPU GDN prefill
    recurrent fallback at the tensor `.all()` branch.
- h18:
  `data/qwen36-ablation-fastlane-clone-piecewise0-output5-6-warmed-trace-gdnmask-summary-20260614h18.json`
  - code change: replaced the XPU tensor `.all()`/boolean scatter final-state
    branch with a device-side `torch.where` path;
  - p512/o512 corrected decode: `92.99 tok/s`;
  - JSON: `64/64` pass;
  - color: `192/192` pass;
  - conclusion: the XPU mask branch fixed the device-loss hazard and passed a
    shallow gate.
- h19:
  `data/qwen36-ablation-fastlane-gdnmask-no-output-clone-summary-20260614h19.json`
  - config: XPU mask branch only, no graph output clone;
  - p512/o512 corrected decode: `91.45 tok/s`;
  - JSON: `64/64` pass;
  - color: `192/192` pass;
  - conclusion: graph output clone was not required for the shallow gate.
- h20:
  `data/qwen36-ablation-fastlane-gdnmask-no-output-clone-promotion-summary-20260614h20.json`
  - config: XPU mask branch only, deeper four-metrics-repeat promotion;
  - corrected decode: `91.94 tok/s`;
  - quality suite: pass and baseline match;
  - JSON failed at repeat `48` with `{"answer": "12.0", "unit": "widgets"}`;
  - color failed at repeat `137` with `blue, green, red, yellow`;
  - rejected.
- h21:
  `data/qwen36-ablation-fastlane-gdnmask-clone-output5-6-promotion-summary-20260614h21.json`
  - config: XPU mask branch plus graph0 output `5,6` cloning;
  - corrected decode: `92.95 tok/s`;
  - quality suite: pass and baseline match;
  - JSON failed at repeat `48`;
  - color failed at repeat `137`;
  - rejected.
- h22:
  `data/qwen36-ablation-fastlane-gdnmask-clone-output5-6-deep-trace-summary-20260614h22.json`
  - config: XPU mask branch plus output `5,6` clone and trace around the known
    failing requests;
  - corrected decode: `93.03 tok/s`;
  - JSON failed at repeat `48`;
  - color failed at repeat `137`;
  - trace: `data/qwen36-cudagraph-state-h22-r0.jsonl`;
  - analysis:
    `data/qwen36-cudagraph-state-h22-json-analysis.json` and
    `data/qwen36-cudagraph-state-h22-color-analysis.json`;
  - key finding: for JSON, graph0 `direct_finish` outputs already differ at
    compute step 0 between adjacent good request `47` and bad request `48`,
    while traced tensor arguments did not differ. This moves the root cause
    inside graph0 direct prefill or hidden/static state, not decode replay.
- h23:
  `data/qwen36-ablation-fastlane-gdnmask-zero-fresh-promotion-summary-20260614h23.json`
  - config: XPU mask branch, no output clone,
    `VLLM_XPU_ZERO_FRESH_GDN_STATE=1`;
  - corrected decode: `93.93 tok/s`;
  - quality suite: pass and baseline match;
  - JSON failed after `49` completed repeats;
  - color failed after `138` completed repeats;
  - rejected.
- h24:
  `data/qwen36-ablation-fastlane-gdnmask-zero-all-prefill-promotion-summary-20260614h24.json`
  - config: XPU mask branch, no output clone,
    `VLLM_XPU_ZERO_ALL_PREFILL_GDN_STATE=1`;
  - corrected decode: `93.95 tok/s`;
  - quality suite: pass and baseline match;
  - JSON failed after `49` completed repeats;
  - color failed after `138` completed repeats;
  - rejected.
- h25:
  `data/qwen36-ablation-fastlane-gdnmask-zero-all-prefill-fallbackpatch-promotion-summary-20260614h25.json`
  - diagnostic code change: also applied all-prefill zeroing inside the Python
    recurrent prefill fallback, not only the native XPU op wrapper;
  - corrected decode: `92.69 tok/s`;
  - quality suite: pass and baseline match;
  - JSON failed after `49` completed repeats;
  - color failed after `92` completed repeats;
  - rejected and the diagnostic code edit was removed from the active tree.

Current accepted code state:

- Keep the XPU recurrent fallback mask branch from h18. It avoids the h17
  device-loss path and does not lower the deeper gate by itself.
- Keep the ablation runner env logging for
  `VLLM_XPU_ZERO_FRESH_GDN_STATE`; this prevents future config drift.
- Do not promote:
  - graph0 output `5` or `5,6` cloning;
  - fresh-state zeroing;
  - existing all-prefill state zeroing;
  - the Python fallback all-prefill zeroing diagnostic edit.

Decision:

- Stale GDN cache state zeroing is not enough to fix the metrics-warmed
  repeat-48/repeat-137 corruption.
- The root is now most likely one of:
  - graph0 compiled direct prefill internal static buffer reuse;
  - an untraced Python recurrent fallback intermediate;
  - a projection/conv/GDN output alias inside graph0 that is not visible from
    the cuda_graph wrapper tensor-argument trace.

Next:

1. Add targeted Python fallback GDN prefill trace for only adjacent good/bad
   requests around JSON `46-49` and color `135-138`.
2. Digest these tensors at graph0/layer0 prefill:
   `projected_states_qkvz`, `projected_states_ba`, `mixed_qkv_non_spec`,
   `conv_state` at selected state indices, `initial_state`,
   `core_attn_out_non_spec`, and `last_recurrent_state`.
3. If the divergence first appears before GDN core, inspect projection/input
   quant static buffers.
4. If the divergence first appears inside GDN core with identical inputs/state,
   isolate the recurrent fallback kernel.
5. If GDN internals remain identical but graph0 output differs, instrument the
   post-GDN norm/output projection handoff.

## 2026-06-14k Python GDN Fallback Trace

Why:

- h22 showed graph0 direct prefill output diverges even when the cuda_graph
  wrapper sees identical visible tensor arguments.
- h23-h25 rejected GDN cache-state zeroing as a repair.
- The next question was whether the corruption begins inside the GDN recurrent
  path or before it.

Instrumentation:

- Added an env-gated Python fallback trace in
  `vllm/model_executor/layers/mamba/gdn_linear_attn.py`.
- Trace file/env family:
  `VLLM_XPU_GDN_TRACE_FILE`,
  `VLLM_XPU_GDN_TRACE_RANK`,
  `VLLM_XPU_GDN_TRACE_PREFILL_ONLY`,
  `VLLM_XPU_GDN_TRACE_LAYER_REGEX`,
  `VLLM_XPU_GDN_TRACE_REQ_REGEX`,
  `VLLM_XPU_GDN_TRACE_MAX_LINES`,
  `VLLM_XPU_GDN_TRACE_TENSOR_LIMIT`,
  `VLLM_XPU_GDN_TRACE_STATE_LIMIT`.
- Stages captured:
  - `fallback_pre_conv`
  - `fallback_post_conv`
  - `fallback_pre_recurrent`
  - `fallback_post_recurrent`

h26:

- Run:
  `data/qwen36-ablation-fastlane-gdnmask-fallbacktrace-summary-20260614h26.json`
- Trace:
  `data/qwen36-gdn-fallback-trace-h26-r{rank}.jsonl`
  - note: the trace writer does not expand `{rank}`; rank was filtered by env,
    so this literal filename still contains rank-0 data.
- Config:
  - fast-lane config restored;
  - no graph-output clone;
  - four p512/o512 metrics repeats;
  - JSON `128`, color `160`;
  - trace rank `0`, layers `0-2`, JSON `46-49`, color `135-138`.
- Result:
  - metrics passed but trace hooks made speed diagnostic only:
    corrected decode `92.69 tok/s`;
  - JSON failed after `49` completed repeats;
  - color failed after `92` completed repeats, earlier than the untraced color
    window.
- Trace captured:
  - 36 rows;
  - JSON repeats `46`, `47`, and bad `48`;
  - layers `0`, `1`, `2`;
  - four fallback stages per layer/request.

h26 finding:

- Adjacent good JSON requests `46` and `47` were identical for the traced
  fallback tensors aside from expected state-slot indices.
- Bad JSON request `48` already differed at
  `language_model.model.layers.0.linear_attn` / `fallback_pre_conv`.
- Example layer-0 `fallback_pre_conv`:
  - good `mixed_qkv_non_spec.sum`: `-2096.06005859375`;
  - bad `mixed_qkv_non_spec.sum`: `-1850.251220703125`;
  - good head began `[-1.53125, 0.9921875, 0.609375, ...]`;
  - bad head was near zero: `[7.95e-11, -1.38e-10, ...]`.
- The selected conv/SSM state for the fresh prompt was zero in both cases.
- Conclusion: the corruption begins before conv and before recurrent state
  handling. GDN cache state is not the first divergence.

h27:

- Run:
  `data/qwen36-ablation-fastlane-gdnmask-forwardtrace-json-summary-20260614h27.json`
- Attempted to trace `hidden_states`, `projected_states_qkvz`, and
  `projected_states_ba` in `forward_xpu`.
- Result:
  - JSON reproduced after `49` completed repeats;
  - trace file:
    `data/qwen36-gdn-forward-trace-h27-r0.jsonl`;
  - only fallback stages appeared, not the `forward_xpu` stages.
- Conclusion:
  - the active compiled path did not execute the newly instrumented
    `forward_xpu` trace in a way that wrote rows;
  - tracing needs to happen at the custom op wrapper boundary instead.

h28:

- Added `pre_fallback_core` trace inside
  `vllm/_xpu_ops.py::_gdn_attention_core_xpu_impl`, before unpacking
  `projected_states_qkvz/ba` into fallback tensors.
- Run:
  `data/qwen36-ablation-fastlane-gdnmask-coretrace-json-summary-20260614h28.json`
- Result:
  - rejected as infrastructure failure;
  - endpoint died during metrics with
    `UR_RESULT_ERROR_DEVICE_LOST` in block table CPU-to-XPU copy before the
    targeted JSON trace window;
  - no `qwen36-gdn-core-trace-h28-r0.jsonl` was written.

Current conclusion:

- The corruption is upstream of GDN conv/recurrent state.
- Next target is the projection/custom-op boundary:
  `projected_states_qkvz`, `projected_states_ba`, and possibly incoming
  `hidden_states`.
- The h28 core-boundary trace caused or coincided with device loss and must be
  retried more safely:
  - avoid per-step trace checks during metrics, or
  - run metrics warmup with trace disabled and enable trace dynamically only for
    canary requests, or
  - use a lighter digest that avoids selected-state reads at the custom-op
    wrapper boundary.

## 2026-06-14l Suggestions.md Triage And Cleanup

Source:

- `/home/steve/suggestions.md`

Accepted direction:

- Stop spending time on more GDN zeroing, output cloning, sampler fallbacks, or
  broad layer fallbacks. h26 already showed the first visible bad tensor is
  upstream of GDN conv/recurrent state, and these knobs only move the failure
  point.
- Treat PIECEWISE forced-comm graph as a fast but unsafe lane until it survives
  warmed long canaries. The restored fast identity remains about `93-98 tok/s`,
  but it is not production-usable while replay corrupts.
- Keep the clean current baseline as the quality oracle:
  GDN fallback + top-k + prefill graph bypass + no async scheduling at about
  `85-86 tok/s`.

Next work to try, in order:

1. Metadata/static replay input sanitation before XPU graph replay.
   - Gate with a new env such as
     `VLLM_XPU_CUDAGRAPH_SANITIZE_METADATA_TAIL=1`.
   - Before replay, zero or sentinel-fill inactive tails for positions, slot
     mappings, block tables, logits indices, and attention metadata.
   - Keep this narrow; do not copy all tensors unless the targeted sanitation
     proves insufficient.
   - Pass condition: restored fast-lane canaries survive after metrics warmup
     without decode speed collapsing.
2. Repair an XPU-safe copy-input graph path.
   - Reproduce the prior `cudagraph_copy_inputs=true` inductor bounds failure
     with logs and generated-kernel context.
   - Add a minimal XPU-safe copy-input mode if the failure is a workspace or
     active-region bounds issue.
   - Gate separately, for example
     `VLLM_XPU_CUDAGRAPH_COPY_INPUTS_SAFE=1`.
3. If graph replay remains unsafe, move performance effort to clean direct
   decode.
   - Prototype persistent W8A8 MoE layerlet kernels using the existing
     scratchpad-ring work as the base.
   - Keep weights, expert pointers, scales, route buffers, scratch, and output
     buffers resident.
   - Validate against the graph-disabled or clean `85-86 tok/s` oracle before
     any speed claim.
4. Profile communication and parallelism after correctness is stable.
   - Run collective replay for current TP4, reversed rank map, and TP2.
   - Test PP=2/TP=2 only if communication is a measurable single-request wall.
   - Track aggregate throughput separately from single-request decode.

Rejected next steps:

- More GDN state zeroing or cloning.
- More sampler fallback variants beyond the already accepted top-k fallback.
- Claiming any PIECEWISE forced-comm run as a win until it passes warmed JSON
  and color canaries.
- Comparing runs without the full benchmark identity in `AGENTS.md`.

Disk cleanup:

- Removed generated compile/runtime cache contents under
  `/mnt/fast-ai/vllm-cache-exp`.
- Reclaimed `459 GiB`.
- Root filesystem moved from full (`0 GiB` available, `100%`) to
  `459 GiB` available (`48%` used).
- Left model/cache directories intact:
  - `/mnt/fast-ai/llm-models`: `275 GiB`
  - `/mnt/fast-ai/llm-cache`: `70 GiB`

Immediate implementation target:

- Start with metadata/static replay input sanitation because it is the cheapest
  graph-replay correctness probe that directly tests the stale padded-input /
  graph-pool poisoning hypothesis from `suggestions.md`.

## 2026-06-14m Suggestions.md Second Review

Why this update exists:

- `/home/steve/suggestions.md` changed after the prior triage.
- The new file is more specific about software-only paths and current baselines.
- Do not erase the older corruption notes; keep them as history, but update the
  active queue with the newer evidence.

Current baseline framing from the updated suggestions file:

- `baseline-conservative`: graph none, GDN fallback decode+prefill, no async,
  about `12.8 tok/s`, JSON `96/96`, color `96/96`, quality skipped. Use as a
  correctness oracle only.
- `fast-conservative-quality`: PIECEWISE + forced comm + GDN fallback decode,
  no async, about `77.8 tok/s`, JSON `96/96`, color `96/96`, `pass_all`.
  This is the fully quality-validated safe row from this table.
- `native-decode-safe-prefill-graph`: PIECEWISE + forced comm + native GDN
  prefill, no async, about `93.3 tok/s`, JSON `64/64`, color `64/64`, quality
  skipped. Treat as the fastest canary-validated candidate, not fully promoted
  until the quality suite and longer warmed canaries pass.

Additional ideas and corrections to carry forward:

1. Native GDN decode/prefill stability is now the nearest-term speed branch.
   - The updated suggestions file makes this priority #1 because native paths
     have already measured near or above `90 tok/s`.
   - Required next gate: promote the `native-decode-safe-prefill-graph` lane
     through full quality, longer JSON/color canaries, and repeated p512/o512.
   - If it fails warm validation, continue the stale graph-pool / allocator
     investigation at the upstream projection/custom-op boundary rather than
     adding more GDN state zeroing.
2. W8A8 MoE layerlet + prefix offsets should remain a top implementation bet.
   - The code and harness are already partially present:
     `csrc/xpu/moe_layerlet.cpp`, grouped-GEMM offset interfaces, and
     `xpu_moe.py` workspace reuse.
   - Current failure mode from suggestions: about `72 tok/s` and immediate
     color canary failure, likely offset or scale alignment rather than a
     fundamental kernel problem.
   - Next debugging target: trace the first divergent tensor versus reference
     under `VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW=1`, then fix offset computation or
     scale broadcasting before testing
     `VLLM_XPU_W8A8_USE_OFFSETS=1`,
     `VLLM_XPU_W8A8_OFFSETS_PREFIX_OP=1`, and
     `VLLM_XPU_MOE_W8A8_MIDDLE_LAYERLET=1` together.
   - Only combine `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1` after quality is clean.
3. Replace no-op communication capture with real XPU graph collectives.
   - `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1` is still a workaround.
   - A real XPU graph-captured custom all-reduce could remove host dispatch and
     sync overhead, and may reduce graph/collective state leaks.
   - This is larger work but has medium-high upside.
4. Graph replay overhead cleanup is a performance item, not only a correctness
   item.
   - The metadata-sanitation experiment reportedly cost roughly `8 tok/s`,
     proving replay input preparation and metadata copies are material.
   - Follow-up targets: block-table updates, redundant host-to-device copies in
     `cuda_graph.py`, metadata tensor reuse, and per-replay event/stream
     creation.
5. Custom all-reduce clone removal is a possible win but must be treated as
   dangerous.
   - Existing notes already say the inner clone was required for earlier safe
     custom all-reduce lanes.
   - Revisit only under the exact newer native-prefill graph identity and with
     full gates. Test `VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT=0` and
     `VLLM_XPU_CUSTOM_ALLREDUCE_GRAPH_CLONE_INPUT=0` separately, not together
     first.
6. Keep a broader software-only backlog:
   - TP4 vs PP2/TP2 or PP4 reshape if collectives remain hot.
   - Kernel fusion for RMSNorm/residual, activation+quant, RoPE+QKV, and
     SiLU/mul/quant.
   - Causal-conv1d / GDN Xe2 tile and scratch tuning.
   - Runtime autotuning of PIECEWISE split points.
   - XPU/Inductor compilation config search, but avoid async scheduling until
     quality evidence changes.
   - Weight layout / pre-packed oneDNN or Xe2-blocked INT8 layouts.
   - Engine-core scheduler overhead reduction for batch-1 decode.
   - Persistent MoE/attention kernels and compute/communication overlap.

Updated near-term priority:

1. Full quality promotion attempt for the `93.3 tok/s`
   `native-decode-safe-prefill-graph` lane.
2. If the lane fails, trace the first warmed divergence at the graph replay /
   projection boundary with the lightest possible digest.
3. Fix W8A8 MoE layerlet prefix-offset correctness, because it attacks the
   largest remaining INT8 MoE overhead without reducing quality.
4. Profile and then work real XPU graph collectives / all-reduce overlap if TP
   synchronization remains a measured wall.
5. Do graph replay metadata-copy cleanup after the correctness lane is stable,
   so speed wins are not confused with corruption workarounds.

