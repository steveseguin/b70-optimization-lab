# Qwen3.8 official-f01e TP1 eager control C1 startup failure

Date: 2026-08-31

Status: **failed infrastructure before health or any model request**

The direct model verifier passed, but the official image failed its initial
oneCCL all-reduce because the C1 container exposed the render devices without
mounting `/dev/dri/by-path`. oneCCL's `ze_fd_manager` therefore could not open
the device directory. The server never became healthy; no performance,
canary, or other model request was sent. This attempt carries no determinism,
quality, or speed conclusion.

The bounded correction for C1b is to add the same read-only
`/dev/dri/by-path` mount and video/render supplemental groups used by the
previously successful official-f01e runners. No model, runtime, execution,
request, metric, or comparison setting changes.

Structured record:
`../data/2026-08-31-qwen38-official-f01e-tp1-eager-control-c1-startup-failure.json`.

Raw evidence remains under
`/mnt/fast-ai/bench-results/qwen38-official-f01e-tp1-eager-control-20260831-c1`.
