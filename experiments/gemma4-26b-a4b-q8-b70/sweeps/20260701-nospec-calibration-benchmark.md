# 2026-07-01 No-Spec Calibration Benchmark

Status: proposed diagnostic lane. Use after the normal realistic/MTP quality
gate, not as a LocalMaxxing headline score.

## Why

The valid MTP record lane is too noisy for sub-1% tuning decisions. The
same-recipe thermal repeatability check measured:

- run medians: `115.515`, `119.019`, `114.520`, `120.202 tok/s`;
- run-median CV: `2.324%`;
- pairwise absolute run-median delta p90: `4.409%`;
- no thermal throttle samples.

That means the MTP lane can make a non-change look like a `+1-4%` result. It is
still the only lane that can validate headline MTP throughput, but it is a poor
instrument for kernel-level micro tuning.

## Candidate Calibration Lane

Disable speculative decoding and cache/history acceleration, but keep the
current target-side VDR2/final-postnorm stack:

```bash
cd /home/steve/qwen36-results-main
GPU_INDEX=0 PORT=18560 \
  LABEL=gemma4-q8-gpu0-nospec-calib-realistic-full512-<stamp> \
  repro/gemma4-26b-a4b-q8-b70/run-vdr2-nospec-calibration.sh
```

The wrapper uses:

```text
EXTRA_LLAMA_ARGS='--parallel 1 --cache-ram 0 --ctx-checkpoints 0'
FLASH_ATTN=on
CTX_SIZE=32768
GGML_SYCL_ENABLE_VMM=1
REALISTIC_GATE=1
REALISTIC_METRIC_TOKENS=100
MAX_TOKENS=512
CANARY_REPEATS=32
```

It also unsets inherited `LLAMA_SPEC_*`, `LLAMA_MTP_*`, and
`LLAMA_GEMMA4_MTP_*` environment variables so the run identity is clean.

## Evidence

Three current-stack repeats on GPU0:

| run | median tok/s 1-100 after TTFT | p10 | mean | per-prompt stdev | full512 median | wall full512 median |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| r1 | `78.6565` | `78.4857` | `78.6081` | `0.0777` | `77.1639` | `75.1194` |
| r2 | `79.0997` | `79.0674` | `79.0915` | `0.0288` | `77.6173` | `75.5503` |
| r3 | `79.1147` | `78.9595` | `79.0858` | `0.0693` | `77.6086` | `75.5608` |

All three runs passed:

- canary: `128/128`;
- fixed realistic final gate;
- `cached_tokens=0` for every prompt;
- fixed suite, each prompt once, no repeated prompt averaging.

Analyzer output:

```text
runs: 3
run medians: 78.657, 79.100, 79.115
run-median mean: 78.957 tok/s
run-median CV: 0.330%
pairwise abs delta p90: 0.577%
```

This is about `7x` tighter than the MTP lane by CV and `7.6x` tighter by p90
run-median delta. It is good enough to rank target-side micro changes that the
MTP lane cannot resolve reliably.

Artifacts:

- `data/gemma4-q8-gpu0-nospec-calib-realistic-full512-20260701T094223Z-nospec-calib-r1/summary.json`
- `data/gemma4-q8-gpu0-nospec-calib-realistic-full512-20260701T094223Z-nospec-calib-r2/summary.json`
- `data/gemma4-q8-gpu0-nospec-calib-realistic-full512-20260701T094223Z-nospec-calib-r3/summary.json`
- `data/gemma4-q8-nospec-calib-realistic-repeatability-20260701T094223Z-nospec-calib.json`
- `data/gemma4-q8-nospec-calib-realistic-repeatability-20260701T094223Z-nospec-calib.md`

## How To Use

Use this lane for target-side changes:

- MoE kernels and routing;
- Q8 reorder / VDR layout changes;
- RMS/postnorm/residual fusion;
- flash-attention / prefill changes;
- runtime flags that affect the target model independent of MTP.

Do not use this lane to validate MTP-only changes:

- draft model quality or quantization;
- speculative acceptance policy;
- verifier/bonus-row logic;
- p-min/n-min/n-max tuning;
- MTP handoff, verifier, or argmax-only shortcuts.

For target-side A/Bs, use same-window paired blocks. Example four-GPU layout:

```text
GPU0: control -> candidate
GPU1: candidate -> control
GPU2: control -> candidate
GPU3: candidate -> control
```

Then run:

```bash
scripts/analyze-gemma-realistic-ab.py \
  --control data/<control-1>/summary.json \
  --control data/<control-2>/summary.json \
  --candidate data/<candidate-1>/summary.json \
  --candidate data/<candidate-2>/summary.json \
  --out data/<label>-nospec-calib-ab.json \
  --markdown-out data/<label>-nospec-calib-ab.md
```

Interpretation:

- `> +0.3%` paired median with a positive lower bound: useful ranking signal;
- `> +0.5%` lower bound: strong diagnostic target-side win;
- still require the normal MTP realistic final gate before claiming a record;
- never submit this diagnostic lane as real-world MTP throughput.

## Future Option

The current VDR2 build has `llama-server` but not `llama-bench`. A dedicated
`llama-bench` target-side CLI microbench is worth building later because it can
remove server streaming overhead and may be even lower variance. Treat it as
kernel calibration only unless it is proven to exercise the same code path and
quality constraints as the service benchmark.
