# 2026-07-09 - Position-specific intrinsic-MTP FC runtime smoke

Status: **overlay/server smoke passed, but compiled multi-position dispatch was
later invalidated**. This is not a headline throughput result and is not
LocalMaxxing eligible. The final offline matrix is recorded in
`2026-07-09-position-fc-mtp5-transfer-insufficient.md`; the runtime correction
is recorded in `2026-07-09-position-runtime-audit-and-compile-guard.md`.

## Architecture correction

The checkpoint name is Qwen3.6, but its runtime architecture is
`Qwen3_5ForConditionalGeneration` / `Qwen3_5MTP`. The launcher still supplies
the deprecated method name `qwen3_next_mtp`; vLLM normalizes that to `mtp`.
Position-specific runtime support therefore belongs in `qwen3_5_mtp.py`, not
`qwen3_next_mtp.py`.

The checkpoint has one packed MTP transformer layer and one full-precision
`mtp.fc.weight`. Every speculative depth currently reuses both. Full layer
cloning is not mechanically equivalent because each new attention layer gets
its own unpopulated draft KV cache. The first bounded experiment specializes
only the full-precision FC by depth while retaining the proven shared
attention/cache path.

## Implemented contract

- trainer scopes: `position-fc`, `position-fc-norms`;
- optional frozen indices, e.g. `--freeze-position-fcs 0`;
- `conditional-prefix` loss masks later rows once a prior greedy token differs;
- candidate keys: `mtp.position_fcs.{i}.weight`, BF16 `[5120, 10240]`;
- overlay field: `text_config.xpu_mtp_num_position_fcs`;
- active runtime: bounds-checked selection by zero-based `spec_step_idx` in
  `Qwen3_5MultiTokenPredictor`;
- loader validation:
  `--model-loader-extra-config '{"enable_weights_track":true}'`.

Tools:

```text
scripts/train-qwen27-intrinsic-mtp-adapter.py
scripts/evaluate-qwen27-intrinsic-mtp-offline.py
scripts/create-qwen27-position-fc-overlay.py
experiments/qwen36-27b-autoround-int4-b70/scripts/run-position-fc-mtp5-training-4gpu.sh
```

## XPU smoke

The three-position smoke froze position 0 and trained positions 1/2 over 16
starts. Its artifact is outside Git on the model USB drive:

```text
/mnt/usb-models/llm-optimization-artifacts/qwen27-position-fc/smoke-20260709
model_extra_tensors.safetensors sha256:
36035714f7e2cca01372b66818738213f68ce411436f78210ccef783c1cea5a3
```

Validation passed:

- actual XPU forward/backward and safetensors export;
- frozen position 0 remained outside the optimizer;
- exported keys/shapes validated and evaluator readback selected all three FCs;
- candidate overlay resolved to `Qwen3_5MTP` and loaded with weight tracking;
- cold OpenAI smoke passed;
- one unique realistic prompt ran once for 512 tokens with
  `cached_tokens=0` and no cache/history reuse;
- graph-off diagnostic median was `52.595204633799824 tok/s`, TTFT
  `449.391 ms`.

Correction: `cudagraph_mode=NONE` did not disable vLLM's no-guard torch compile
wrapper. The cached graph referenced only `position_fcs.0.weight`, so this smoke
did not prove later draft positions selected their own FC. It remains valid as
an overlay/load/OpenAI/cache-zero mechanical smoke only. Offline acceptance
evaluation explicitly selected each position and is unaffected.

Evidence:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-position-fc-runtime-load-smoke-20260709-20260709T224746Z
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-position-fc-runtime-load-smoke-20260709-candidate-summary-20260709T224746Z.json
```

The throughput is diagnostic only: graph was disabled, the artifact had only a
tiny training smoke, one prompt was measured, and quality was skipped. It proves
the artifact/runtime contract, not a speed win.

## Completed acceptance gate

The four-GPU MTP5 matrix completed. The best all-FC candidate reached
`2.763428` visible tokens/step on training-heldout starts and `2.773804` on a
separate unseen v6b context corpus. This transferred, but it did not materially
exceed the current approximately `2.747` MTP3 endpoint depth and cannot pay for
the extra MTP5 verifier rows. It was therefore closed without an endpoint run.
The next experiment retains that candidate and adds position-specific low-rank
residual capacity without adding new draft KV caches.
