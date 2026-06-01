# 2026-06-01 f728 Quality and Speed Split

Goal: answer whether the preserved `f728d2c0cf` REAP cache can honestly recover
the old `89.x` output tok/s lane while keeping async output quality intact.

## Result

It cannot be promoted as-is.

The same preserved cache/AOT pair has two distinct behaviors:

- Without clean-weight owner repair, it direct-loads and reaches near the old
  speed, but async output is corrupt.
- With clean-weight owner repair, async quality passes, but throughput falls
  back to the current low-83 output tok/s band.

That makes the current `88.x` preserved-cache result a throughput-only artifact,
not a usable quality-valid REAP result.

## Key Runs

Fresh `FULL_FORWARD_CUSTOM_OP=0`, restore off, qk-helper on:

- Quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-fullforward0-restore0-qksafe-20260601T1828.json`
- Result: passed, `384` generated tokens, `190` distinct generated token IDs,
  no NUL/control output.
- Benchmark:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T223035Z.json`
- Decode: `83.52` output tok/s, `111.36` total tok/s.

Fresh `FULL_FORWARD_CUSTOM_OP=0`, restore off, attention-delay off:

- Quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-fullforward0-restore0-attndelay0-20260601T1834.json`
- Result: passed, `384` generated tokens, `186` distinct generated token IDs,
  no NUL/control output.
- Benchmark:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T223723Z.json`
- Decode: `83.13` output tok/s, `110.84` total tok/s.

Preserved `f728d2c0cf` without owner-clean-weight shim:

- Benchmark:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T224417Z.json`
- Decode: `88.63` output tok/s, `118.17` total tok/s.
- Async quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-f728-no-shim-control-20260601T1846.json`
- Result: failed. The run generated token id `0` for all `384` tokens, with
  NUL/control output and degenerate text.

Preserved `f728d2c0cf` with runtime owner-clean-weight shim:

- Shim:
  `scripts/sitecustomize_minimax_clean_weight/sitecustomize.py`
- Quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-f728-sitecustomize-owner-restore1-20260601T1842.json`
- Result: passed, `384` generated tokens, `191` distinct generated token IDs,
  no NUL/control output.
- Benchmark:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T224156Z.json`
- Decode: `83.32` output tok/s, `111.09` total tok/s.

## Graph Shape Notes

Old non-REAP quality-clean cache and preserved fast REAP cache have the same
high-level shape:

- `fused_moe=124`
- `minimax_m2_moe_forward=0`
- `_minimax_clean_weight_xpu=992`
- `all_reduce=813`
- graph size about `1,722,005` bytes
- code hash:
  `4fe2c2714bb00a8bf4af9b66b0fa08880e2d8769e2f5301f1f85696b39e1437d`

Fresh quality-safe restore-off graphs are close but not identical:

- `fused_moe=124`
- `minimax_m2_moe_forward=0`
- `_minimax_clean_weight_xpu=0`
- `all_reduce=813` or `875`, depending on attention-delay/qk-helper settings
- graph size about `1,716,053-1,716,214` bytes

The throughput difference is therefore not explained by simply getting MoE back
inline. The preserved fast path appears to depend on stale or missing
clean-weight graph state that also corrupts async output.

## Decision

- Do not submit a new LocalMaxxing update from these runs.
- Do not promote the no-shim `f728d2c0cf` recovery path.
- Keep the runtime `sitecustomize` shim only as a diagnostic tool for stale AOT
  cache validation.
- Current quality-valid direct async speed remains about `83.3-83.5` output
  tok/s for the tested safe paths.

## Next Targets

The easy env/cache wins are exhausted. Further sizeable decode-rate improvement
needs source work, likely one of:

- Make Q/K RMS clean-weight restore graph-safe without changing the fast graph
  scheduling.
- Replace the current restore-weight fallback with a compile-time-stable path
  that never exposes stale owner attributes to captured graphs.
- Add deeper MiniMax MoE/QK fusion that removes real per-token work instead of
  only restoring stale AOT shape.
- Re-run old non-REAP strict artifacts with the newer async quality harness if we
  need to distinguish a genuine hardware/runtime regression from a harness gap.

