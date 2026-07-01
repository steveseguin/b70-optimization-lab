# 2026-07-01 Final Postnorm Thermal Variance Check

Status: complete. Valid fresh-response repeats; temperature did not explain
the observed throughput variance in this band.

## Goal

The promoted Gemma 4 26B A4B Q8 final-postnorm recipe is reproducible but
high-variance. This sweep tested whether GPU temperature or throttling was a
major contributor by running the exact promoted recipe four times in sequence
on the same GPU while recording privileged XPU telemetry.

## Run Identity

All repeats used the current promoted short-decode recipe:

- GPU: B70 GPU0 only;
- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`, accepted tokens verified by the
  Q8 target;
- runtime/build: llama.cpp `c926ad098`, reordered-Q8 VDR2 build;
- `FLASH_ATTN=on`, `CTX_SIZE=32768`, `GGML_SYCL_ENABLE_VMM=1`;
- `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `POLL=100`;
- `n_max=3`, `n_min=2`, `p_min=0.0475`, `--ctx-checkpoints 0`;
- `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`;
- `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`;
- `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`;
- `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`;
- LM-head subgroup experiment explicitly unset;
- fixed realistic cold suite, `MAX_TOKENS=512`, `CANARY_REPEATS=128`;
- each prompt requested once, `cached_tokens=0`, no prompt/KV/context/history
  reuse.

Wrapper shape:

```bash
cd /home/steve/qwen36-results-main
env -u LLAMA_SYCL_Q8_0_LM_HEAD_1COL_SUBGROUPS \
  GPU_INDEX=0 PORT=18540 \
  FLASH_ATTN=on CTX_SIZE=32768 GGML_SYCL_ENABLE_VMM=1 \
  MAX_TOKENS=512 CANARY_REPEATS=128 REALISTIC_GATE=1 \
  REALISTIC_METRIC_TOKENS=100 \
  LABEL=<thermal-label> \
  repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh
```

Telemetry was collected with `xpu-smi dump` around each run. Temperature
metrics require sudo on this host; the password was read from the local
excluded file and was not printed or recorded.

```bash
sudo -S -p '' xpu-smi dump -d 0 -m 0,1,2,3,4,5,17,18,35 -i 1 \
  < /home/steve/SUDOPASSWORD.txt
```

Metrics:

- `0`: GPU utilization;
- `1`: power;
- `2`: frequency;
- `3`: core temperature;
- `4`: memory temperature;
- `5`: memory utilization;
- `17`: memory bandwidth utilization;
- `18`: memory used;
- `35`: throttle reason.

## Results

Stamp: `20260701T090544Z`.

Telemetry summary:
`data/gemma4-q8-gpu0-finalpostnorm-thermal-full512-20260701T090544Z-telemetry-summary.json`.

| Rep | Summary | Median 1-100 tok/s | p10 | Mean | Full512 after TTFT | Wall full512 | TTFT ms | Core active start/max/end C | Mem active start/max/end C | Active freq mean/min/max MHz | Active power mean/max W | Non-not throttle samples |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| 1 | `data/gemma4-q8-gpu0-finalpostnorm-thermal-full512-20260701T090544Z-r1/summary.json` | 115.515 | 102.417 | 114.152 | 109.487 | 103.651 | 179.1 | 46 / 77 / 76 | 48 / 86 / 86 | 2767 / 1450 / 2800 | 200.1 / 233.58 | 0 |
| 2 | `data/gemma4-q8-gpu0-finalpostnorm-thermal-full512-20260701T090544Z-r2/summary.json` | 119.019 | 111.100 | 119.736 | 110.854 | 105.475 | 178.8 | 64 / 78 / 74 | 72 / 88 / 88 | 2754 / 1200 / 2800 | 202.4 / 234.67 | 14 (`Burst Power Excursion`) |
| 3 | `data/gemma4-q8-gpu0-finalpostnorm-thermal-full512-20260701T090544Z-r3/summary.json` | 114.520 | 108.463 | 117.588 | 111.111 | 106.691 | 178.7 | 64 / 78 / 78 | 74 / 88 / 88 | 2763 / 1200 / 2800 | 203.2 / 234.05 | 5 (`Burst Power Excursion`) |
| 4 | `data/gemma4-q8-gpu0-finalpostnorm-thermal-full512-20260701T090544Z-r4/summary.json` | 120.202 | 106.403 | 119.595 | 110.673 | 106.297 | 178.9 | 65 / 78 / 78 | 74 / 90 / 88 | 2780 / 1900 / 2800 | 203.0 / 233.69 | 1 (`Burst Power Excursion`) |

All four repeats passed the realistic final gate, `cached_tokens=0` for every
prompt, and `512/512` canary rows.

## Interpretation

Temperature is not the main explanation for the observed variance in this
range:

- primary throughput varied from `114.520` to `120.202 tok/s` on the same GPU
  and same recipe;
- active core max was essentially flat at `77-78 C`;
- active memory max was `86-90 C`, and the hottest memory run was also the
  fastest run;
- no thermal-throttle reason was observed;
- the only non-`Not Throttled` samples were `Burst Power Excursion`, and they
  did not line up with lower throughput;
- active frequency stayed near maximum, with mean `2754-2780 MHz` and max
  `2800 MHz`;
- the coolest-start run was not the fastest.

This supports the existing conclusion that the final-postnorm recipe is a
valid but high-variance lane, probably dominated by speculative acceptance,
prompt-level shape, scheduler/runtime timing, and normal GPU/run noise rather
than simple thermal throttling.

## Future Fairness Rule

For promoted record repeats and any close A/B where the delta is within a few
percent:

1. Capture `xpu-smi dump` telemetry beside the benchmark result.
2. Record active core temperature start/max/end, memory temperature
   start/max/end, power mean/max, frequency mean/min/max, and throttle reasons.
3. Flag any real thermal-throttle samples separately from `Burst Power
   Excursion`.
4. Do not compare a hot run against a cold historical outlier without
   telemetry, same-recipe repeats, or a same-window control lane.
5. Treat small one-off deltas as variance until repeated with the fixed
   realistic gate, `cached_tokens=0`, and the exact same canary scale.

Temperature still matters operationally, but this sweep does not justify
discarding or discounting valid record-family runs solely because memory
temperature reached `88-90 C` when no thermal throttle was reported.
