# Qwen3.6 Device-Lost Restart

Date: 2026-06-10

After the rejected RMS+INT8 BF16/FP32 fused-kernel diagnostics, the accepted Qwen3.6 backend later died during an external chat completion request. The log showed:

- `RuntimeError: level_zero backend failed with error: 20 (UR_RESULT_ERROR_DEVICE_LOST)`
- shutdown abort with `UR_RESULT_ERROR_OUT_OF_RESOURCES`
- process exit `139`

The failed request was from `10.0.0.214`, had `prompt_token_ids_len=4138`, and requested `max_tokens=2048`.

Recovery:

- No stale vLLM workers remained.
- `xpu-smi discovery` still enumerated all four Intel Arc Pro B70 devices.
- Relaunched the accepted baseline in tmux session `qwen36-graph-tp4-customar-clone-32k`.
- Backend `/v1/models` became ready on readiness attempt 37.
- Frontdoor `/v1/models` became ready after backend restart.

Lesson: do not run unsafe extension diagnostics on the same visible XPU devices while the production-candidate backend is serving traffic. For future fused-kernel work, stop the backend or isolate a single device and pause frontdoor routing first.
