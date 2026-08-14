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

### Direct-strided follow-up

A second locked run tested zero-copy direct weights: the existing reordered
Q8 quant bytes were exposed as logical oneDNN `[K,O]` S8 with strides `{1,K}`.
All arms still selected `jit:gemm:any`, but strict F32-source direct weights
were decisively too slow:

| local output O | packed F32 | direct F32 | direct/packed |
| ---: | ---: | ---: | ---: |
| 4992 | 174.449 us | 724.321 us | 4.152x |
| 6656 | 213.616 us | 758.248 us | 3.550x |

The direct BF16-source arms were fast (`68.046/86.050 us`) but deliberately
change activation arithmetic (direct-Q8 NRMSE about `0.003666`). They require
an all-width, coherent quantized-target design and cannot be substituted only
at width 16 while retaining a BF16/exact-target claim. The strict-F32
zero-copy integration route is closed.

Direct follow-up artifacts:

- `/mnt/fast-ai/bench-results/muse-glimmer-30b/q8-woq-direct-width16-20260813/result.json`,
  SHA256 `fefb0f080dd3425a61947fb82068be5fbbaba8d8e571b68c1f915cc0f09338df`;
- corresponding `run.log`, SHA256
  `4e480811db9de896aabca7cd5c3d924d6d1501dceff1e82db28e0d00ab867b96`.

### Full-model outcome

The BF16-source direct design was subsequently integrated as a declared Q8
target with fixed execution width 16 for decode widths 1–16. Combined with
pretrained BF16 DFlash and distributed ARGMAX/local-winner reuse, it passed two
fresh canonical century gates and the frozen 15-prompt cold gate. The final
source, raw evidence, limitations, and runners are promoted in the
[result packet](../../../results/muse-glimmer-30b-q8-woq-b70/README.md) and
[standalone repro](../../../repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/README.md).

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
