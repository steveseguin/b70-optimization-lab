# Qwen3.8 27B FP8 TP2 real-content depth R56 diagnostic

Date: 2026-09-01

## Result

The final public R50 image passed the complete MTP0/MTP1 real-content depth
matrix. Each arm ran technical prose, Python code, and structured-document
prompts at exact 2K, 4K, 8K, 16K, 24K, and 32K active depths. All 36 requests
were cache zero, both canary passes succeeded, and all 18 complete MTP1 output
token arrays exactly matched the corresponding MTP0 arrays.

| Active context | MTP0 tok/s | MTP1 tok/s | MTP1 uplift | MTP1 TTFT |
| ---: | ---: | ---: | ---: | ---: |
| 2K | 33.735 | 52.029 | 54.23% | 0.592 s |
| 4K | 33.394 | 52.905 | 58.43% | 1.150 s |
| 8K | 32.538 | 51.930 | 59.60% | 2.346 s |
| 16K | 31.769 | 53.134 | 67.25% | 4.877 s |
| 24K | 31.017 | 49.990 | 61.17% | 7.643 s |
| 32K | 30.331 | 50.088 | 65.14% | 10.580 s |

Each point is the median of the three directly measured content classes. No
point is interpolated or extrapolated. MTP1 accepted 1,667 of 1,884 draft
tokens (`88.482%`). Its TTFT cost versus MTP0 was 2.06-2.60% across the curve.

## Memory correction

The first MTP1 launch used the old 9 GiB memory / 12 GiB combined
memory-plus-swap limit. It did not reach service readiness: model staging
repeatedly hit the cgroup memory ceiling and accumulated 14,440 `memory.max`
events. It was stopped without producing a benchmark row.

The depth launcher now defaults to 12 GiB memory and 16 GiB combined
memory-plus-swap. The successful server loaded both workers in about 12 seconds,
compiled in about 49 seconds, and finished with zero `memory.max`, OOM, or
OOM-kill events. This is a recipe robustness fix, not a throughput claim.

## Publication boundary

This is valid diagnostic evidence but is not promotable from this boot. The
boot journal contains an earlier GPU reset that predates the successful matrix.
There were no new GPU faults or resets after the MTP1 server launch, but the
preregistered policy still requires clean-boot fresh-server repeats before this
curve may replace the current public Grade-C curve. The qualified short-profile
headline remains `51.808087 tok/s`; this workload is not substituted for it.

Machine-readable values and raw-artifact hashes are in the
[R56 result](../data/2026-09-01-qwen38-fp8-real-content-depth-r56-diagnostic-result.json).
The exact workload and gates are in the
[R56 preregistration](../data/2026-09-01-qwen38-fp8-real-content-depth-r56-prereg.json).
