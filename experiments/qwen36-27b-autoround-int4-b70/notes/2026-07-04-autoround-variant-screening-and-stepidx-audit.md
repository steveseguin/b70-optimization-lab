# Qwen27 AutoRound Variant Screening + MTP Step-Index Audit

Date: 2026-07-04

## Context

Current strict record remains
`webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8 LM-head (BF16 scales)` at
`65.27648650325429 tok/s` median generated-token throughput for tokens 1-100
after TTFT, with the fixed Qwen realistic suite, each prompt once,
`cached_tokens=0`, and target-verified MTP3/cg8.

The same-window baseline in this batch was valid at `64.81299244218022 tok/s`,
which is within the known record-family variance and is not a new promoted row.

## Same-Window Variant Screen

All runs used:

- one B70, TP1;
- `MAX_MODEL_LEN=2048`;
- `MAX_NUM_BATCHED_TOKENS=1024`;
- XPU graph on with
  `COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}'`;
- `qwen3_next_mtp`, `NUM_SPECULATIVE_TOKENS=3`;
- `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`;
- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`;
- `VLLM_XPU_LM_HEAD_INT8=1`;
- `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`;
- strict fresh Qwen realistic suite with `cached_tokens=0` on every prompt.

| model | snapshot | median tok/s | p10 | mean | TTFT median ms | status |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `webhie/Qwen3.6-27B-int4-AutoRound` | `f5750c90b3776db658594df5fe8051098226dd8e` | `64.81299244218022` | `57.62471438592983` | `64.32896790809586` | `606.004755012691` | same-window control |
| `webhie/Qwen3.6-27B-int4-AutoRound-Code` | `2264cf0911559d59b08fe8d59d815565124c647d` | `63.96265270899306` | `59.146278598181816` | `63.034565744480005` | `607.6223229756579` | valid no-win |
| `acyildirimer/Qwen3.6-27B-int4-AutoRound` | `c71c579b605c5bd10d50e94360fec1fb7078b577` | `64.326424542084` | `56.80283143327227` | `63.06638374556055` | `603.9374629035592` | valid no-win |

Artifacts:

- control:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-variant-control-20260704T034311Z-20260704T034311Z.json`
- webhie-Code:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-code-int8lmhead-bf16scale-variant-20260704T034311Z-20260704T034311Z.json`
- acyildirimer:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-acyildirimer-int8lmhead-bf16scale-variant-20260704T034311Z-20260704T034311Z.json`

Conclusion: the local alternate AutoRound checkpoints did not beat the
same-window webhie control, so there is no quality gate or LocalMaxxing
submission to run for them. Keep them as compatibility/reference variants.

## Newer Variant Download

`poma-ai/Qwen3.6-27B-int4-AutoRound` was discovered as a newer AutoRound INT4
variant. It is being downloaded to the USB HF cache:

- cache root: `/mnt/usb-models/hf-cache`;
- snapshot observed during download:
  `/mnt/usb-models/hf-cache/hub/models--poma-ai--Qwen3.6-27B-int4-AutoRound/snapshots/a2fd1827e179753eaa2e77373292f44b7173437c`;
- card describes the default AutoRound recipe (`200` iterations, `128`
  calibration samples), not the webhie `auto-round-best` recipe.

Expected record odds are low, but it is worth one strict compatibility/speed
screen after the download completes because the storage cost is on the USB
drive and the model keeps the same INT4 W4A16 / MTP preserved format.

## MTP `spec_step_idx` Audit

A source audit found that `Qwen3_5MultiTokenPredictor.forward()` supports a
`spec_step_idx` and chooses:

```python
current_step_idx = spec_step_idx % self.num_mtp_layers
```

but the active proposer/wrapper path does not currently plumb different
`spec_step_idx` values into the serial draft-token loop. If Qwen27 had multiple
MTP hidden layers, this could be a real accepted-token improvement: later draft
positions would use position-specific MTP layers instead of reusing layer 0.

For the active local checkpoints, this is a no-op:

| model | `mtp_num_hidden_layers` | `num_nextn_predict_layers` |
| --- | ---: | --- |
| `webhie/Qwen3.6-27B-int4-AutoRound` | `1` | `None` |
| `webhie/Qwen3.6-27B-int4-AutoRound-Code` | `1` | `None` |
| `acyildirimer/Qwen3.6-27B-int4-AutoRound` | `1` | `None` |
| `poma-ai/Qwen3.6-27B-int4-AutoRound` metadata | `1` | `None` |

Conclusion: do not patch `spec_step_idx` for this Qwen27 lane. It is a valid
future audit item only for checkpoints with `mtp_num_hidden_layers > 1`.

## Next Direction

Closed:

- scheduler-only adaptive depth;
- local alternate webhie-Code / acyildirimer variants;
- `spec_step_idx` for one-layer MTP checkpoints.

Still credible:

1. exact verifier/logits work that reduces LM-head call count or real rows
   without lowering accepted tokens/step;
2. a true integrated top-1/candidate-max primitive that beats dense oneDNN,
   unlike the first standalone full-vocab compact kernel;
3. new model variants only if they are same-or-better quality class and pass
   the strict cold-response gate.
