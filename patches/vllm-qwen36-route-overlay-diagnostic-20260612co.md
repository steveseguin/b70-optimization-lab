# Qwen3.6 Route Overlay Diagnostic Patch Note 20260612co

This records the local instrumentation used for the route-overlay diagnostic.
It is intentionally a patch note instead of a direct `git diff` artifact
because the local `/home/steve/src/vllm` checkout already contains many
unrelated XPU/debug changes in the same files.

Local vLLM files touched by the route-overlay attempt:

- `/home/steve/src/vllm/vllm/model_executor/layers/fused_moe/router/route_capture.py`
- `/home/steve/src/vllm/vllm/v1/worker/gpu_model_runner.py`
- `/home/steve/src/vllm/vllm/v1/worker/xpu_worker.py`

Diagnostic env vars used:

```bash
VLLM_XPU_FORWARD_BOUNDARY_SYNC=1
VLLM_XPU_FORWARD_BOUNDARY_PRINT_EVERY=1
VLLM_XPU_FORWARD_BOUNDARY_SKIP_FIRST=0
VLLM_XPU_ROUTE_OVERLAY=1
VLLM_XPU_ROUTE_OVERLAY_MIN_NUM_TOKENS=1
VLLM_XPU_ROUTE_OVERLAY_MAX_NUM_TOKENS=1
VLLM_XPU_ROUTE_OVERLAY_STAGE_REGEX='^(quark_int8_apply|runner_pre_monolithic)$'
VLLM_XPU_ROUTE_OVERLAY_TOP_EXPERTS=8
VLLM_XPU_ROUTE_OVERLAY_MAX_LAYER_SUMMARIES=96
```

Fresh-cache launch also used:

```bash
TORCHINDUCTOR_CACHE_DIR=/mnt/fast-ai/vllm-cache-exp/qwen36-routeoverlay-freshcache-20260612cn3/torchinductor
VLLM_CACHE_ROOT=/mnt/fast-ai/vllm-cache-exp/qwen36-routeoverlay-freshcache-20260612cn3/vllm
PORT=18081
```

Implementation intent:

- `route_capture.py` gained an env-gated in-memory route overlay snapshot in
  addition to its existing file-capture path.
- `gpu_model_runner.py` reset the overlay immediately before model forward and
  attached the popped overlay snapshot to `[vllm-xpu-forward-boundary]` rows.
- `xpu_worker.py` included the earlier rank-map/device-set hooks needed for
  diagnostics; this file should not be treated as route-overlay-only.

Result:

- The fresh-cache diagnostic started and captured all-rank forward-boundary
  timing rows.
- Route overlay payloads were present but empty: `captures=0`.
- Conclusion: the Python router callback location is too high for the accepted
  compiled replay path. The next implementation should capture route summaries
  lower in the MoE runner or custom-op path, immediately after expert
  selection and before/inside the shared MoE execution path.

Follow-up 20260612cr:

- Added route-overlay health counters: registered layers, capture calls,
  overlay candidates, file candidates, and stream-capture skips.
- The compiled diagnostic confirmed the hooks are registered and called during
  prefill, but one-token decode replay bypasses Python callbacks.
- An eager route-fixture run captured decode routes. That route data is useful
  for offline kernel design, but eager speed is not comparable to the accepted
  graph path.

Related artifacts:

- `data/qwen36-quark-int8-tp4-routeoverlay-diagnostic-summary-20260612co.json`
- `data/qwen36-quark-int8-tp4-routeoverlay-freshcache-20260612cn3.log`
- `data/qwen36-quark-int8-tp4-routeoverlay-freshcache-p512o128-metrics-20260612cn3.json`
- `data/qwen36-quark-int8-tp4-routefixture-diagnostic-summary-20260612cr.json`
