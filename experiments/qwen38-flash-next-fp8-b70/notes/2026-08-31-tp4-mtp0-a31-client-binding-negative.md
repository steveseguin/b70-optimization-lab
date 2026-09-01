# Qwen3.8 Flash-Next TP4 MTP0 A31 client-binding negative

Date: 2026-08-31
Status: orchestration negative before inference; no quality or speed result

A31 was the third accelerator experiment on boot
`aab4f613-55bd-4d10-b6c8-830a35d78b68`, after the A2 and affinity component
arms. It loaded all 131 local-NVMe checkpoint shards in `69.06 s`, reported the
expected `31.57 GiB` model memory per rank, selected the frozen M1 warps-8
configuration, completed warmup, and returned HTTP 200 from `/health`.

The client then failed before its first request with `supervisor identity
mismatch`. The new health lifecycle uses a tracked outer supervisor that runs
the inherited service supervisor from generated source. The client still
required the generated inner process command line to contain the tracked outer
script filename. That identity assumption is false even though the process is
owned by the correct outer supervisor and lock set.

The failure sentinel caused bounded service teardown. The outer finalizer
recorded the inner exit, restored host memory and swap, passed exact four-card
compute/free-memory at a minimum free fraction of `0.9907876089003552`, found no
bounded journal fault signature, and sealed a verifying evidence manifest. No
inference request ran, so this is not a model, quality, or performance result.

The fix is a new attempt whose client verifies the generated inner supervisor
through its exported outer-supervisor PID/start-time and held host/GPU locks.
The run must use new state, port, cache, evidence, and lifecycle paths. A reboot
is neither required nor useful.

Structured result:
[`20260831-tp4-mtp0-a31-client-binding-negative.json`](../data/20260831-tp4-mtp0-a31-client-binding-negative.json).
Protected TP4 MTP0 `5.515783 tok/s` and MTP4 `20.727176 tok/s` results remain
unchanged.
