# Qwen3.6 TP4 Worker/Async Output Timeline 20260612bz

Scope:

- Current model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`.
- Runtime: accepted vLLM/XPU TP4, Quark W8A8 INT8, 32K context, no prefix
  caching, piecewise graph cache.
- Diagnostic only. The accepted backend was restored afterward and passed
  provenance plus a short no-thinking quality smoke.

Patch/artifacts:

- `patches/vllm-qwen36-worker-output-timeline-20260612bz.diff`
- `data/qwen36-quark-int8-tp4-worker-output-timeline-20260612bz.log`
- `data/qwen36-quark-int8-tp4-worker-output-timeline-p512o384-metrics-20260612bz.json`
- `data/qwen36-quark-int8-tp4-worker-output-timeline-summary-20260612bz.json`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-worker-output-timeline-20260612bz.log`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-worker-output-timeline-20260612bz.json`
- `data/qwen36-quark-int8-tp4-accepted-quality-after-worker-output-timeline-nothink-smoke-20260612bz.json`

Speed sanity:

- p512/o384/c1 stream, two measured repeats after a warmup:
  `100.009 tok/s` corrected output throughput.
- vLLM decode histogram mean: `9.975 ms/generation token`.
- vLLM TPOT/inter-token histogram mean: `10.001 ms/token`.

Worker/output split:

- Engine step total mean: `9.973 ms`.
- Engine `future_result` mean: `9.783 ms`.
- `sample_tokens` executor response wait mean: `4.649 ms`.
- Rank-0 worker response enqueue mean: `4.325 ms`.
- Rank-0 `AsyncModelRunnerOutput.get_output()` mean: `4.241 ms`.
- Response message-queue enqueue mean: `0.081 ms`.
- Result tuple packing mean: `0.00047 ms`.

Async output split:

- Async object created to `get_output()` start: `0.269 ms` mean.
- D2H copy-submit end to `get_output()` start: `0.168 ms` mean.
- D2H copy submit itself: `0.096 ms` mean.
- `async_copy_ready_event.synchronize()`: `4.044 ms` mean.
- Copy-submit end to sync done: `4.214 ms` mean.
- Token scalar/list conversion: `0.019 ms` mean.

Conclusion:

- The output object is not sitting behind a long Python worker queue. It reaches
  `get_output()` roughly `0.17 ms` after the copy submission ends.
- Python result packing and response-MQ enqueue are not the bottleneck.
- The live `~4 ms` worker-output cost is still the async output event wait.
  Combined with the isolated `~0.01 ms` tiny D2H copy benchmark, this points at
  upstream device dependency exposure rather than host token-copy mechanics.

Next target:

- Add device/event markers around sampler/logits completion, token-ID copy
  submission, `async_copy_ready_event.record()`, and rank-0 worker handoff.
- Keep rank/device route-skew attribution in the queue; this run did not yet
  explain why the event waits several milliseconds after a tiny copy.
