# 2026-06-27 `n_min=1` Strict Screen Negative And Control Repeat

Goal: test one remaining acceptance-shape gap around the current VDR2 strict
record: keep `n_max=3` but allow `n_min=1` so a single verified draft token can
be accepted. The control lane repeated the current record identity exactly.

Promotion gate:

- fixed suite: `repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json`;
- each prompt sent once as a cold response;
- `cached_tokens=0` on every row;
- no prompt/KV/context checkpoint/response reuse;
- no n-gram/history acceleration;
- target/verifier unchanged: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- Q4_0 MTP draft tokens verified by the Q8 target;
- primary metric: median generated-token throughput for tokens 1-100 after
  TTFT.

Common identity:

```text
llama.cpp c926ad098, local B70 SYCL/AOT Gemma patch stack
target: gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf
draft:  MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf
GPU count: 1 complete replica per B70
CTX_SIZE=8192 BATCH_SIZE=1024 UBATCH_SIZE=1024 THREADS=8 POLL=100
FLASH_ATTN=off REASONING=off --parallel 1 --cache-ram 0 --ctx-checkpoints 0
VDR2 reordered-Q8 target stack, f16 target/draft KV
```

## Results

| Run | Spec config | Valid | Median 1-100 tok/s | p10 | Mean | Full512 after TTFT | Wall full512 | TTFT ms | Decision |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-strict-vdr2-controlrepeat-n3-nmin2-p00475-ub1024-20260627T2340fg/summary.json` | `n_max=3`, `n_min=2`, `p_min=0.0475` | yes | **91.047632** | 80.129557 | 89.125659 | 85.990582 | 83.293830 | 179.330 | valid high observation; needs confirmation before submission |
| `data/gemma4-q8-gpu1-strict-vdr2-n3-nmin1-p00475-ub1024-20260627T2340fg/summary.json` | `n_max=3`, `n_min=1`, `p_min=0.0475` | yes | 88.188165 | 80.497095 | 88.878919 | 85.125590 | 81.726720 | 180.263 | loss |
| `data/gemma4-q8-gpu2-strict-vdr2-n3-nmin1-p00350-ub1024-20260627T2340fg/summary.json` | `n_max=3`, `n_min=1`, `p_min=0.035` | yes | 87.521617 | 78.225637 | 87.581852 | 83.597424 | 81.203176 | 182.026 | loss |
| `data/gemma4-q8-gpu3-strict-vdr2-n3-nmin1-p00650-ub1024-20260627T2340fg/summary.json` | `n_max=3`, `n_min=1`, `p_min=0.065` | yes | 88.652313 | 79.393914 | 88.903467 | 81.527875 | 79.360861 | 179.908 | loss |

All rows passed `realistic_final_gate.passed=true`, had
`cached_tokens_all_zero=true`, and passed the 8-repeat canary screen.

## Conclusion

`n_min=1` is not useful under the current strict VDR2 identity. It adds verifier
work / acceptance noise faster than it recovers fresh one-token drafts; all
tested thresholds were below the current promoted `90.98312252660529 tok/s`
record.

The control repeat produced a strict-valid `91.047632 tok/s` observation,
slightly above the current LocalMaxxing record. Because this is the same config
and only `+0.0645 tok/s`, treat it as a confirmation candidate rather than a
new promoted row until another exact-control repeat batch supports a `91+`
frontier. Do not submit based on this single marginal row alone.

## Exact Control Repeat Confirmation

Follow-up exact repeats of the promoted config were launched on all four B70s:

| Run | Valid | Median 1-100 tok/s | p10 | Mean | Full512 after TTFT | Wall full512 | TTFT ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `data/gemma4-q8-gpu0-strict-vdr2-recordrepeat2-n3-nmin2-p00475-ub1024-20260627T2350fg/summary.json` | yes | 85.040859 | 75.851156 | 85.700230 | 83.355187 | 80.377607 | 180.265 |
| `data/gemma4-q8-gpu1-strict-vdr2-recordrepeat2-n3-nmin2-p00475-ub1024-20260627T2350fg/summary.json` | yes | 86.571676 | 78.367372 | 87.740004 | 84.925802 | 81.795617 | 180.039 |
| `data/gemma4-q8-gpu2-strict-vdr2-recordrepeat2-n3-nmin2-p00475-ub1024-20260627T2350fg/summary.json` | yes | 84.942619 | 80.412436 | 87.453054 | 83.690496 | 80.483797 | 180.989 |
| `data/gemma4-q8-gpu3-strict-vdr2-recordrepeat2-n3-nmin2-p00475-ub1024-20260627T2350fg/summary.json` | yes | 86.223820 | 79.922673 | 86.728697 | 81.522415 | 78.693445 | 179.985 |

Decision: the `91.047632 tok/s` control row did **not** confirm. Treat it as
normal variance, not a new record. Keep LocalMaxxing at
`90.98312252660529 tok/s` (`cmqwxep4a03qiqr010chjn93s`) unless a future
source/runtime change creates a repeatable improvement.
