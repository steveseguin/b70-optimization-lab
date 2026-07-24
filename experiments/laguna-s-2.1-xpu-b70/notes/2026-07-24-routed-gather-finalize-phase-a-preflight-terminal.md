# Laguna routed gather/finalize Phase-A preflight terminal

Date: 2026-07-24 America/Toronto

Status: **terminal before runner; no retry, component evidence, endpoint, or
submission.**

## Outcome

The exact M=8 post-W2 gather/finalize candidate completed Stage 0 and received
one immutable Phase-A timing/exactness authorization:

- tooling commit:
  `1bc3db422daefd2c5e7fe915eaff8dfd850ec920`;
- packet-only commit:
  `180826bea272c73e6cf767df1b02fc0b80ef018a`;
- authorization packet SHA-256:
  `383ca2f804793047be3898a3e12a4772d6e5592385b0483b1edd6d0af529a39a`;
- candidate `_moe_C` SHA-256:
  `6a6794249421aceb51f14980a3e2c0b0a9d7b492abf2f8d25b129b86f099bc5b`;
  and
- fixture SHA-256:
  `0b1ea43d0a724cc64eaf6636b99076afd852846f79c06b4db264f2a511689259`.

The first and only authorized execution completed its five registered
discovery probes, then stopped on the first strict-idle sample at
2026-07-24 05:04 America/Toronto. The campaign root was never acquired.
The durable failure is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
gather-finalize-phase-a-1bc3db422-v1-preflight-failure.json
```

Its SHA-256 is
`bd91f212e4728cd410ea68df043394789ef903dcdf7245907553e6054dbc6d4b`
and its terminal status is `component_failed_stop_before_runner`.

## Root cause

The frozen coordinator required the JSON result of `xpu-smi ps -j` to be
exactly:

```json
{"process_list":[]}
```

The installed tool instead emits a top-level `device_util_by_proc_list`. A
read-only diagnostic immediately after the failure contained four rows for
the querying `xpu-smi` process itself, one per card, and no model or service
process. That process had exited by the subsequent host-process check. The
diagnostic raw SHA-256 was
`f47866b297acef6711ab08e9ee7d15d783d2d9b9492e537731b2ccaf2528ec7d`.

This was a harness-schema failure, not evidence that the candidate was
inexact, slow, or even imported. The fail-closed result is nevertheless
binding. The packet authorized one campaign and explicitly set
`retry_authorized=false`; it must not be rerun, replaced, or rescued after
observing the failure.

## What did and did not run

Ran:

- five read-only `xpu-smi discovery -j` mapping probes; and
- one read-only `xpu-smi ps -j` strict-idle sample.

Did not run:

- candidate or incumbent native-module import;
- Torch/XPU tensor allocation;
- any candidate, control, downstream, timing, or profiler primitive;
- model load, endpoint, generation, cold prompt, or benchmark;
- counter capture, payload construction, network access, LocalMaxxing
  submission, service change, or reboot.

The candidate therefore remains unmeasured. No performance or correctness
conclusion may be drawn from this terminal preflight.

## Prevention and next action

Future one-shot packets must test their idle-parser grammar against a retained
capture from the installed tool before authorization. A future coordinator
should launch `xpu-smi` with `Popen`, retain the child PID, accept only
observer rows bound to that exact PID and process name, and fail on every
other process row. Mock-only schema tests are insufficient.

The next Laguna experiment must be materially distinct and separately
preregistered. The current approved record remains
`33.89498511171744 tok/s`, LocalMaxxing
`cmrx6p5dv001bo4017hb7sixz`, at vLLM
`8936aac144929190c1e53f8b8624ca397ce16f5b` plus XPU kernels
`b6076ce1249ffee0e30bee528f4cd15c3bffb234`.
