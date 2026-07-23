# W1 N128 NVMe recovery: XCCL log-framing preflight abort

The fourth local-NVMe recovery root is closed as an infrastructure-only abort:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-nvme-postreboot-recovery-20260723T140038Z
```

It ran on clean boot `0b7f98a5-e50a-46a5-81ea-15938b55317a`, kernel
`7.0.0-28-generic`, with taint `0`. The gate verified all 118 local model
files, four-card discovery/mapping and strict idle, four oneAPI Level Zero
devices, and the exact four-device peer read.

The first XCCL command also exited zero. All four sequential device checks
reported `device_count 1` and `ok 2097152.0`. Each rank emitted exactly one
init marker, one barrier marker, and one exact `allreduce ok 4.0` marker.
However, `torchrun` multiplexed multiple rank writes onto the same physical
lines:

```text
rank 0 init okrank 1 init okrank 3 init okrank 2 init ok
```

The frozen parser required each marker to occupy a complete physical line, so
it rejected the valid zero-exit pass and failed closed with status 1. The
second XCCL pass, both N64 gates, N128, a model service, and model generation
did not run. Kernel delta contained only `-- No entries --`; the Xe reject
file was empty and kernel taint remained zero.

The evidence manifest verifies completely. Stable hashes are:

```text
evidence.sha256          7907353bc59879be89cfd719cfda537e011accb12a7365b439b042b29520866e
final-status.txt         be629cb74eb5804b8933e0e710f2374a0a20155c2725b56ac36fba089b767b9c
sycl-ls-verbose.log      a6c004432418cea7c58b444c44ccfc1d4c9d4ae9acbf39f6bf50ce2ee875c617
peer-read.log            8e4d7110a7999cc510c69d352aa6a69553d6f22d1f20f116eb0e8cf8a6b35752
xccl-pass-1.log          1fb7f3522b8b85c982563dc07dd35b213ec302203c767dfce02aef4f59f68fcd
kernel-delta.txt         19c4e28b2f54ea8f217db4e622b0a5c758efa7b77ce2dc0394b6d159568c0b2e
kernel-reject-events.txt e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

The correction changes only log framing: it still requires every rank's exact
init, barrier, and numeric all-reduce marker exactly once, but counts fixed
substrings instead of complete physical lines. The XCCL commands, ranks,
numeric expectations, timeouts, and two-pass requirement are unchanged.

The new recovery root is registered as:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-nvme-postreboot-recovery-20260723T140536Z
```

This retry is an infrastructure parser correction on the same clean boot, not
a performance-conditioned restart. A1 remains the first model generation
after a complete recovery pass.
