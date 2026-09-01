# Qwen3.8 Flash-Next TP4 full-decode XPU graph component result

Date: 2026-08-31

Status: threshold-specific correctness negative; superseded as a production
prerequisite by the matched-protocol follow-up; no model load or reboot

The exact TP4 graph prerequisite failed safely. Ordinary eager XCCL passed the
changing-input CPU oracle. The first replay of an `XPUGraph` containing the
same 5,120-byte BF16 all-reduce also passed, but replay iteration 1 mismatched
on all four ranks. The fail-fast worker exits propagated through `torchrun`
with exit code 1. No timing is eligible.

This result directly rejects the `8192`-threshold collective protocol for a
compilation-free TP4 graph: every target step requires 97 collectives, and a
graph that is correct only on its first replay cannot serve inference.

An independent identity audit subsequently found that this arm set
`CCL_SYCL_ALLREDUCE_LL_THRESHOLD=8192`, selecting `Rt64_PCIE`, while the
protected Flash-Next endpoint retains the `4096` default and selects
`Rt64_128_PCIE` for its 5,120-byte reductions. This result must therefore not
be used to close the production protocol or the whole `FULL_DECODE_ONLY` route.
The exact matched follow-up is separately preregistered.

No checkpoint or server was loaded. All four B70s enumerated afterward, no
owned process survived, host memory and swap remained fully recovered, and the
bounded kernel-journal window contained no device fault. The host remains
eligible for further work without rebooting.

Raw evidence is under
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/20260831-xpu-graph-xccl-a1`.
The `torchrun.log` SHA-256 is
`947f4d5f2ba7f9442af0944a5bd6cce9075440c66db662325b45fa4d2ff98ab2`.
The structured result is
[`20260831-tp4-xpu-full-decode-graph-component-negative.json`](../data/20260831-tp4-xpu-full-decode-graph-component-negative.json).

Protected MTP0 `5.515783 tok/s` and MTP4 `20.727176 tok/s` results are
unchanged. Do not spend a full model load on the `8192` protocol.
