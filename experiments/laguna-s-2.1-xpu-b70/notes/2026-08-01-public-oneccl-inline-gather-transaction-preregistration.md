# Laguna public-oneCCL inline-gather transaction screen

Date: 2026-08-01 America/Toronto

Status: **preregistered; diagnostic component only. No endpoint score is
authorized.**

## Motivation

The protected BF16-KV record remains `125.4619731637751 tok/s` conventional.
The row-0 tensor trace localized the prefix-24 failure to the first captured
target all-gather's consumer-visible output on ranks 1–3. All ranks match the
control through the rank-local layer-0 O projection, while rank 0 receives the
correct gathered output and nonzero ranks do not.

The current Laguna service maps the installed oneCCL `Gold-2021.17.2` runtime.
An independently pinned public oneCCL parent
`b52f40c07f0b140e6aba87548c80720a350a9827` / libccl
`4ceafd15c03ce46f11eeaf91781a92afebd3cecf` previously repaired a similarly
rank-asymmetric captured-collective failure on Qwen TP2. Its internal-NVMe
binary and kernel hashes match that promoted Qwen runtime:

- `libccl.so.1.0`:
  `43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700`;
- `kernels.spv`:
  `0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9`.

This is evidence for a bounded runtime A/B, not proof that the Qwen fix
transfers to Laguna.

## Transaction oracle

Add a standalone TP4 probe for the actual Laguna width-12 gather geometry. On
every replay it must:

1. change a fixed-address BF16 `[1,12,3072]` source on each rank;
2. capture the producer copy into a distinct fixed input;
3. capture `all_gather_into_tensor` into a fixed `[4,12,3072]` output;
4. capture the same literal rank-ordered BF16 additions used by the model;
5. compare both gathered and consumer-visible tensors against an exact
   changing-input oracle on every rank; and
6. record the actually mapped `libccl.so` path and hash.

The installed Python compatibility library legitimately maps its
`libccl.so.2` dependency, so the control requires exactly one match for the
expected installed-wrapper hash and records every dependency. The preloaded
public candidate must map the expected public library exclusively; any second
`libccl.so` mapping fails its identity gate.

Run exactly two fresh, bounded 512-replay arms in this order:

- installed oneCCL control;
- pinned public-oneCCL candidate using `LD_PRELOAD` and its matching
  `CCL_KERNEL_PATH`.

Each arm uses a fresh artifact directory, a 180-second external timeout, one
torchrun launch, and explicit post-run worker/idleness inspection. A timeout,
device error, incomplete rank set, wrong mapped library, or dirty teardown
stops the experiment. Do not retry, reset, reload, unbind, FLR, delete shared
memory, or reboot.

## Decision rule

- If the installed control fails and the public candidate passes `512/512` on
  all four ranks, the runtime candidate is admitted to one separately
  preregistered non-scored prefix-24 model smoke. It is not yet an endpoint
  optimization.
- If both pass, the standalone transaction does not reproduce the model
  dependency. Do not infer that the public runtime fixes Laguna; proceed only
  through a model-level prefix-24 diagnostic with all-rank parity if a more
  specific runtime mechanism is established.
- If the public candidate fails, close this runtime substitution for direct
  target-collective capture.
- No result from this component probe may be reported as token throughput.

The model, teacher, BF16 KV, width/depth, sampler, acceptance, graph topology,
and protected record sources remain untouched.
