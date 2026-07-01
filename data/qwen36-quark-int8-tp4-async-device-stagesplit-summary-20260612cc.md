# Qwen3.6 TP4 Async Device Timeline And Stage Split 20260612ca-cc

Scope:

- Current model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`.
- Runtime: accepted vLLM/XPU TP4, Quark W8A8 INT8, 32K context, no prefix
  caching, piecewise graph cache.
- These are diagnostic runs only. Device timing events and staged synchronizes
  slow decode to about `77 tok/s`, so their speed numbers are not candidates.

Patch:

- `patches/vllm-qwen36-async-device-timeline-20260612cc.diff`

Runs:

1. `20260612ca`: device timeline events only.
2. `20260612cb`: sync split between default-stream marker and copy-ready event.
3. `20260612cc`: stage split across sampler end, state update, bookkeeping,
   pre-async-wrap, default-before-copy, and copy-ready.

Key ca/cb finding:

- Device elapsed timings from sample/copy events are tiny:
  - `device_sample_start_to_copy_ready_ms`: about `0.064-0.065 ms`.
  - `device_default_before_copy_to_ready_ms`: about `0.0077 ms`.
  - `device_copy_stream_entry_to_ready_ms`: about `0.0065 ms`.
- Host sync is still multi-ms:
  - ca `sync_ms`: `4.962 ms` mean.
  - cb `sync_ms`: `5.957 ms` mean.
- cb split showed nearly all host wait is waiting for the default-stream marker:
  - `default_ready_sync_ms`: `5.933 ms` mean.
  - `copy_after_default_sync_ms`: `0.021 ms` mean.

Key cc stage split:

- Total async output sync: `5.066 ms` mean.
- `stage_sample_end_sync_ms`: `5.007 ms` mean.
- `stage_state_update_sync_ms`: `0.026 ms` mean.
- `stage_bookkeeping_sync_ms`: `0.0088 ms` mean.
- `stage_pre_async_wrap_sync_ms`: `0.0033 ms` mean.
- `default_ready_sync_ms`: `0.0025 ms` mean.
- `copy_after_default_sync_ms`: `0.0107 ms` mean.

Interpretation:

- The hidden wait is already present at the event recorded immediately after
  `_sample(...)` returns.
- Post-sample state update, bookkeeping, async-wrap setup, the D2H token copy,
  Python result packing, and response queueing are now ruled out as
  multi-millisecond bottlenecks.
- The host returns from `_sample(...)` before the XPU/default-stream work needed
  for the sampled token is complete. The remaining c1 latency target is model
  tail/sampler/logits/default-stream work and its graph/collective queueing,
  not output materialization.

What this prunes:

- Do not spend more time on `.tolist()`, pinned output buffers, scalar token
  ferrying, Python result tuple packing, or response-MQ enqueue for a `2x`
  win.
- Device elapsed event values alone are not enough for host-latency
  attribution because they exclude time spent waiting for the queued default
  stream work to become ready.

Next target:

1. Split the `_sample(...)` path and preceding model/logits tail with staged
   host synchronizes or lower-overhead queue markers.
2. Attribute the remaining `~5 ms` to logits processor, sampler kernels,
   graph-captured model tail, TP collectives, or rank imbalance.
3. Combine this with rank/device route-skew rotation before writing another
   MoE kernel branch.

Restore gate:

- Accepted backend restored in tmux session
  `qwen36-tp4-accepted-restored-after-async-device-stagesplit-20260612cc`.
- Accepted provenance passed exact prompt prefixes and sentinels `4752`,
  `11436`, and `198`.
- Short no-thinking Qwen text quality smoke passed exact OK, copy phrase,
  arithmetic, JSON schema, and repeat stability.
