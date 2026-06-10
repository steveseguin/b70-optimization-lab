# Qwen3.6 Device-Lost Recovery After Runtime Screens

Date: 2026-06-10

## Incident

After the all-reduce graph-clone-off screen, I restored the accepted no-prefix
TP4 32K runtime. The backend reached `/health`, but the first frontdoor smoke
request failed with HTTP 500.

Backend log:

- Log: `/tmp/qwen36-quark-int8-tp4-piecewise-graph-customar-clone-32k-noprefix.log`
- Error time: about `03:39`
- Error: `UR_RESULT_ERROR_DEVICE_LOST`
- Failing path: `block_table.copy_to_gpu(...)` during the first scheduled chat
  completion request after restore.

The engine then died and the backend stopped serving `/health`.

## Recovery Checks

After killing the dead `qwen36-tp4-noprefix-32k` session:

- No stale vLLM worker processes remained.
- `xpu-smi discovery` still enumerated all four Intel Arc Pro B70 devices.
- `torch.xpu.is_available()` returned `True`.
- `torch.xpu.device_count()` returned `4`.
- All four devices reported as `Intel(R) Arc(TM) Pro B70 Graphics`.

## Recovery Action

I relaunched the accepted no-prefix runtime:

- Session: `qwen36-tp4-noprefix-32k`
- Cache root: `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-customar-clone-32k-noprefix`
- Profile: TP4, 32K, Quark W8A8 INT8, BF16 runtime, no prefix caching,
  XPU PIECEWISE graph, clone-safe custom-op all-reduce.

Post-restart validation:

- Backend `/health`: pass
- Backend `/v1/completions`: pass
- Frontdoor `/v1/chat/completions`: pass, returned exactly `OK`
- Active runtime session: `qwen36-tp4-noprefix-32k`

## Current Assessment

The device-lost error appears recoverable without a host reboot. It happened
after a series of rapid runtime stops, fresh graph compiles, and relaunches.
This is the second device-lost incident observed during unsafe or diagnostic
runtime work on 2026-06-10.

For future screens:

- Always validate actual generation after restore, not only `/health`.
- Record device-lost incidents separately from speed results.
- Treat repeated fresh compile/relaunch loops as reliability stress, not as a
  production-like steady-state profile.
- Keep the accepted runtime on the restored no-prefix profile when stopping.
