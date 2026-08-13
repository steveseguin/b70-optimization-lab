# Muse Q8_0 oneDNN WOQ microbenchmark

Isolated oneDNN 3.11 SYCL benchmark for the fixed Muse TP verifier shapes:

- tokens: 16;
- input/reduction: 6656;
- local output: 4992 and 6656;
- Q8_0 group size: 32, symmetric zero point;
- oneDNN weight scales: F16, grouped `{32, 1}` over logical `[K, O]` S8 weights;
- floating-point math mode: BF16 with `apply_to_int=true`.

The program does not depend on or modify llama.cpp. It refuses to select a GPU
unless both `--run` is supplied and `ONEAPI_DEVICE_SELECTOR` is exactly
`level_zero:0`.

## Compile

```bash
source /opt/intel/oneapi/setvars.sh --force
/opt/intel/oneapi/compiler/2026.0/bin/icpx \
  -O3 -DNDEBUG -std=c++17 -Wall -Wextra -Wpedantic \
  -fsycl -fsycl-targets=spir64_gen \
  -Xsycl-target-backend=spir64_gen '-device bmg-g31' \
  -I/opt/intel/oneapi/dnnl/2026.0/include \
  muse_q8_woq.cpp \
  -L/opt/intel/oneapi/dnnl/2026.0/lib \
  -Wl,-rpath,/opt/intel/oneapi/dnnl/2026.0/lib -ldnnl \
  -o muse_q8_woq
```

## Authorized run form

Only after production is stopped and the operator declares the shared lock
free:

```bash
source /opt/intel/oneapi/setvars.sh --force
flock -n /run/lock/muse-glimmer-gpu-exclusive.lock \
  env ONEAPI_DEVICE_SELECTOR=level_zero:0 \
  ./muse_q8_woq --run --warmup 4 --repeats 11 --inner 8 \
  --json result.json
```

The four arms are rotated between repeat batches:

1. oneDNN WOQ with F32 activation;
2. oneDNN WOQ with explicit BF16 activation;
3. Q8_0-to-BF16 weight dequantization plus F32-to-BF16 activation conversion
   and a oneDNN BF16 matmul in llama.cpp's incumbent operand orientation;
4. resident BF16 oneDNN matmul, as a GEMM-only ceiling.

Weight packing is performed and timed once outside the hot loop. Results use
host wall time with one queue wait per `inner` batch, report median/p10/p90,
and compare every arm to a direct Q8_0-by-F32 CPU reference and to arm 3.

The JSON also records each primitive descriptor's `impl_info_str`. oneDNN
3.11 does not expose attribute-scale memory through `exec_arg_md` (the query
returns a zero descriptor), so the benchmark reconstructs and validates the
same scale contract used internally and by benchdnn: F16 `[K/32,O]`, strides
`[O,1]`, with the supplied allocation checked for exact byte size. If a newer
runtime exposes a nonzero queried descriptor, it must match that supplied
descriptor or the benchmark aborts; query availability is reported in JSON.

## 2026-08-13 B70 result

The authorized single-device run held
`/run/lock/muse-glimmer-gpu-exclusive.lock`, selected exactly
`ONEAPI_DEVICE_SELECTOR=level_zero:0`, and used the documented defaults:
four warmups, 11 repeats, and eight operations per timed batch. All six
primitive descriptors selected `jit:gemm:any`; no reference implementation or
runtime error occurred.

| local output O | WOQ F32 src | WOQ BF16 src | Q8 dequant + BF16 | resident BF16 |
| ---: | ---: | ---: | ---: | ---: |
| 4992 | 163.256 us | 106.015 us | 495.386 us | 117.721 us |
| 6656 | 204.329 us | 110.527 us | 650.449 us | 156.050 us |

The F32-source WOQ arm was `3.034x` and `3.183x` faster than the measured
dequant-plus-BF16 path at O=4992 and O=6656. It remained `38.7%` and `30.9%`
slower than a resident-BF16 GEMM, but avoids materializing the BF16 weight.
Against the direct Q8_0-by-F32 CPU reference its NRMSE was only
`1.457e-6`, cosine rounded to `1.0`, and maximum absolute error was
`4.120e-4` for both shapes. The BF16-source WOQ arm was faster, but its NRMSE
was approximately `0.003666`; it is not the accuracy-leading integration
candidate.

The one-time pack measurements (`3.990/0.165 ms` at O=4992 and
`16.421/0.205 ms` at O=6656) are intentionally outside the hot loop and are
order/JIT-cache biased: F32 was always packed first. Do not compare the two
pack numbers as steady-state reorder throughput.

This is a **GO for a bounded loader/integration design**, not yet a production
result. A viable implementation must replace the resident Q8 AoS allocation
with packed S8 plus grouped F16 scales, rather than duplicate all 312 main
projection weights, and must pass real-model output/quality tests. The earlier
generic SYCL MMQ real-model lane remains rejected; see
`../notes/2026-08-13-q8-width16-mmq-negative.md`.

Artifacts:

- structured result: `data/muse-q8-woq-width16-onednn-20260813.json`, SHA256
  `ff2d04f1ab37ff6e4a531d888fda06f7dabdaf9a275d876e0e2f91d7f132cbf4`;
- external combined log:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/q8-woq-width16-20260813/run.log`,
  SHA256
  `20e0bbdb68e2dbd4a516c529ee3af6cc8f966d57b86500349fafbbd237dd5daf`;
- compiled BMG-G31 binary used for the run: SHA256
  `10a125f684d8301e5acbebb4a7f1f8d47746942333f4dee1f640e5b421f00f7d`;
- source used for the run: SHA256
  `f5764fc4e457bb7289044fd387ce061925dfa04d76e370e62c69b906d59c8b23`.
