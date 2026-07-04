# 2026-07-04 - LM-head dense backend swap microbench: no-win

## Question

Before committing to a deeper fused LM-head top-1 / candidate-max kernel, test a
cheaper possibility: use the existing Xe2 W8A8 grouped-GEMM backend as a
single-expert dense LM-head kernel.

This would still materialize full logits, so it is not the final target, but it
would be a low-risk endpoint experiment if it were materially faster than the
current oneDNN `int8_gemm_w8a8` path for Qwen27 LM-head shapes.

## Repro

Script:

```bash
ZE_AFFINITY_MASK=0 /home/steve/.venvs/vllm-xpu/bin/python \
  scripts/bench-qwen27-lmhead-backends.py \
  --rows 1,2,3,4 \
  --warmup 20 \
  --iterations 80 \
  --output-json data/qwen36-27b-autoround-int4-b70-baselines/qwen27-lmhead-backend-microbench-20260704T030000Z.json
```

Shape:

- hidden: `5120`;
- vocab: `248320`;
- rows: `1,2,3,4`;
- input: already quantized INT8 activations plus per-row activation scales;
- weight: INT8 `[5120, 248320]`;
- output dtype: BF16.

Result JSON:

`data/qwen36-27b-autoround-int4-b70-baselines/qwen27-lmhead-backend-microbench-20260704T030000Z.json`

## Results

Median milliseconds by row count:

| Rows | oneDNN BF16 scales | oneDNN FP32 scales | Xe2 grouped BF16 scales | Xe2 grouped FP32 scales |
| ---: | ---: | ---: | --- | ---: |
| `1` | `2.509904` | `2.517084` | error: `ptr_B_scales must be float` | `2.630271` |
| `2` | `2.547205` | `2.550356` | error: `ptr_B_scales must be float` | `2.669159` |
| `3` | `2.494816` | `2.489000` | error: `ptr_B_scales must be float` | `2.683916` |
| `4` | `2.509834` | `2.508397` | error: `ptr_B_scales must be float` | `2.731821` |

## Interpretation

Closed as a no-win:

- oneDNN is already faster for the LM-head shape by about `5-9%`;
- Xe2 grouped W8A8 only accepts FP32 weight scales, so it cannot directly
  preserve the current BF16-scale record identity;
- because it still writes dense logits, even a faster grouped backend would not
  attack the dominant output-materialization waste.

Do not spend endpoint validation runs on a oneDNN -> grouped-GEMM LM-head swap.
The credible Phase 2 path remains a true native tiled/XMX LM-head op that
reduces to exact top-1 / candidate information before writing full logits, or a
separate exact verifier design that reduces accepted verifier rows without
breaking target replacement or bonus-token semantics.
