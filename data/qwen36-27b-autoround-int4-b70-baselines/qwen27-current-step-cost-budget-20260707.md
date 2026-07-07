# Qwen27 Step-Cost Budget

Classification: diagnostic planning artifact, not a benchmark and not a LocalMaxxing submission.

## Baseline

- strict fresh headline: `68.23626314761921` tok/s
- target-verified tokens/step: `2.746954076850984`
- inferred verifier step cost: `40.256513914139006` ms
- MTP3 hard ceiling: `4.0` target-verified tokens/step
- current rank-64 branch envelope: `3.9681349578256793` tokens/step

## Throughput Targets

| target tok/s | step ms needed at current depth | step ms to save | save % | tokens/step needed at current step | MTP3 hard ceiling reaches? | branch envelope tok/s | branch extra step budget |
|---:|---:|---:|---:|---:|:---:|---:|---:|
| 80.0 | 34.337 | 5.920 | 14.70% | 3.221 | yes | 98.571 | 9.345 |
| 90.0 | 30.522 | 9.735 | 24.18% | 3.623 | yes | 98.571 | 3.834 |
| 100.0 | 27.470 | 12.787 | 31.76% | 4.026 | no | 98.571 | -0.575 |
| 125.0 | 21.976 | 18.281 | 45.41% | 5.032 | no | 98.571 | -8.511 |
| 150.0 | 18.313 | 21.943 | 54.51% | 6.038 | no | 98.571 | -13.802 |

## Reading This

- A verifier-step-cost patch that saves less than the listed `step ms to save` cannot hit that target unless accepted depth also improves.
- Current MTP3 cannot reach `100 tok/s` at the measured step cost; even the optimistic rank-64 branch envelope tops out below `100 tok/s` before overhead.
- `125+ tok/s` requires deeper verified speculation or a large target-body step-cost reduction plus better accepted depth.
