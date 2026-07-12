# Device-resident MTP3 phase-one result

## Result

The context-owned device staging and fixed three-step MTP loop are correct, but
they do not improve the strict realistic-suite throughput. The JIT strict run
passed every freshness/quality gate at `50.164 tok/s` median (tokens 1-100),
versus the retained fusion-stack region of roughly `50-52 tok/s`.

Evidence:

- strict result: `data/qwen36-27b-mtp-gguf-q4-b70-baselines/qwen27-device-unroll-jit-strict-20260712T213330Z.json`;
- median `50.16412408231635 tok/s`, p10 `42.97808448518369`, mean
  `49.205276991666246`;
- `realistic_final_gate.passed=true` and all twelve prompts had
  `cached_tokens=0`;
- production acceptance remained workload-correct (`43.6-75.7%` by prompt);
- the poisoned-host device-input test passed with exact staged/host output
  parity and stable staging buffers across graph rebuilds.

## What was implemented

- persistent candidate and `h_nextn` tensors owned by the MTP context;
- ordered same-device SYCL copies into the next M=1 graph input;
- three MTP graph submissions followed by one host materialization;
- strict default-off graph identity and lifecycle handling;
- a model-gated poisoned-host parity/lifetime test;
- launcher identity for `LLAMA_MTP_DEVICE_UNROLL`.

## Correctness issue found

The SYCL backend top-k tensor contains a leading scratch candidate. On the real
Qwen cycle the ordinary host path selected the following entry; copying entry
zero collapsed acceptance to zero. Selecting the production-equivalent entry
restored the exact first draft sequence (`12305,198,727` in the diagnostic
prompt) and normal acceptance. This is covered by the staging test.

## Decision

Retain the implementation default off as infrastructure, not as a promoted
speed path. Queueing the draft steps without intermediate host reads removes a
host boundary, but all draft graphs and their approximately `9.7 ms` of device
work remain serialized on the same queue before target verification. The
target M=4 verifier (`45.646 ms`) still dominates the cycle, so this phase
cannot cross 68 tok/s.

Further work must change device work, not merely its host submission pattern:
a materially faster M=4 verifier, a compatible higher-acceptance draft with a
larger useful block, or reduced target weight traffic/precision.
