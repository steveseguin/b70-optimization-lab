# Qwen3.8 Flash-Next TP4 production-protocol XPU graph preregistration

Date: 2026-08-31

Status: frozen before device execution

## Correction and question

The first graph probe used `CCL_SYCL_ALLREDUCE_LL_THRESHOLD=8192`, but the
protected endpoint uses the `4096` default for its 5,120-byte BF16 reduction.
The protocols are not interchangeable. This follow-up asks whether exact
changing-input graph replay works with the production threshold and whether
the public oneCCL `4ceafd1` graph-recording implementation repairs any failure
of the currently staged `2021.17.2` library.

## Frozen A/B

Run the existing four-rank BF16 `[1,2560]` probe for 100 changing inputs with
`CCL_SYCL_ALLREDUCE_LL_THRESHOLD=4096`:

1. current endpoint libccl SHA-256
   `ace144a390a53720b2743844decf127661c942b56f3b414900b9d8c11461acc3`;
2. public oneCCL `4ceafd1` libccl SHA-256
   `43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700`.

Each arm gets an unused evidence directory and bounded timeout. Eager output,
every graph replay, and the eager/graph hash series must match the exact CPU
oracle on all four ranks. A library arm is positive only if all 100 graph
replays pass on all ranks with more than one unique output hash. Timing is
diagnostic only.

If the public build alone passes, the next prerequisite is one graph holding
the target step's ordered 97 reductions. No model endpoint is authorized by
this component result alone. No checkpoint is loaded and no reboot is
authorized.
