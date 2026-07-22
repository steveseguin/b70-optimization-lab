# DeepSeek V4 Flash uniform-K160 on 4x B70

Status: **paused/closed frontier; best verified record preserved**.

The lane closed on 2026-07-21 after the exact target-verified DSpark7 path
reached a strict high of **80.820052 tok/s** for one active generation. No
later verified endpoint result exceeded it. The three independent strict suite
medians were `80.820052`, `76.900178`, and `78.287226 tok/s`, making
`78.287226 tok/s` the median-of-medians.

## Use these entry points

- Standalone record recipe:
  [`repro/deepseek-v4-flash-k160-b70-80tps-20260718/`](../../repro/deepseek-v4-flash-k160-b70-80tps-20260718/README.md)
- Record note:
  [`2026-07-18-sharded-target-argmax-record.md`](../../experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-18-sharded-target-argmax-record.md)
- Closeout and reopen conditions:
  [`2026-07-21-deepseek-v4-flash-frontier-closeout.md`](../../experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-21-deepseek-v4-flash-frontier-closeout.md)
- Validity rules: [`validity-gates.md`](validity-gates.md)
- Rejected paths and lessons: [`bugs-failed-paths.md`](bugs-failed-paths.md)
- Full experiment history:
  [`experiment-ledger.md`](../../experiments/deepseek-v4-flash-reap-xpu-b70/results/experiment-ledger.md)

## Record identity

- Model: `0xSero/DeepSeek-V4-Flash-180B`, revision
  `7c360e1cd4a5168099dbc54d16d929bf6df04990`.
- Hardware: four Intel Arc Pro B70 32 GB GPUs, TP4+EP, concurrency one.
- Runtime: vLLM `264c7f2f7df21ddeeab32ecca0353133344f1ac9`, XPU
  kernels `31315673737d95da0f79179c8f755260ef02c1d6`, oneCCL
  `48fda4f0e074db005596d6899d5227d3f0316c12`.
- Graphs: target PIECEWISE and private breakable draft PIECEWISE.
- Speculation: DSpark7, exact M=7 draft query capture, unchanged target
  verifies accepted tokens at M=8.
- Mechanism: persistent Markov with W1-only replication, exact M8
  compressors, selective M8 W8A16, MXFP4 N128, native M8 router normalization,
  and guarded sharded greedy target argmax/native target-token rejection.
- Benchmark: 12 unique cold prompts, 128 output tokens, median throughput for
  generated tokens 1-100 after TTFT.
- Validity: all 36 realistic requests cache-zero; four ordered six-case exact
  suites pass 24/24.
- LocalMaxxing: `cmrquta9905w3lg013m5vxoqx`.

The public uniform-K160 checkpoint is a useful experimental performance
artifact, not a quality-certified official REAP construction: its hash layers
are pruned and its calibration/ranking provenance is unavailable. Keep that
caveat attached to every result.

## Final decision

The endpoint record is intact and all reusable source, patches, harnesses, and
negative results are preserved. Reopen only for a 10-20M-token EAGLE capture
and hybrid-draft training effort, or a genuinely new mechanism that removes
device execution time. Do not restart configuration sweeps, submission-only
fusion, or already rejected M=1 occupancy experiments.
