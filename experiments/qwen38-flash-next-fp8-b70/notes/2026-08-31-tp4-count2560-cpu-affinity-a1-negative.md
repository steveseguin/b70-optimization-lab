# Qwen3.8 Flash-Next TP4 CPU/L3 affinity A1 negative

Date: 2026-08-31
Status: bounded component performance negative; no endpoint claim

The four-arm `control-1 / pinned-1 / pinned-2 / control-2` gate completed on
the same boot immediately after HC-SiLU A2. This is the first executed proof of
the health-gated reuse policy: A2 closed cleanly, the next independent arm
passed a new preflight, and no reboot or boot-history exception was involved.

The affinity treatment did not improve the accepted ordinary-XCCL component:

- pair 1: `7.026607 ms` control versus `7.0898005 ms` pinned,
  `-0.8993%` median saving and `-0.5670%` p90 saving;
- pair 2: `6.985941 ms` control versus `7.07091 ms` pinned,
  `-1.2163%` median saving and `-1.1325%` p90 saving.

Both pairs missed the required `+5%` median and nonnegative p90 thresholds.
The explicit rank-process/oneCCL-worker CPU/L3 placement is therefore closed as
a component negative. It is not an endpoint throughput result.

The lifecycle finalizer passed: four-card compute/free-memory succeeded before
and after all arms, the postflight minimum free fraction was
`0.9907874892822146`, host memory and swap recovered, the bounded journal scan
was empty, and the complete evidence manifest verifies. The boot remains
healthy and eligible for independent work.

Evidence is preserved at
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260831-tp4-count2560-cpu-affinity-a1`.
The structured result is
[`20260831-tp4-count2560-cpu-affinity-a1-negative.json`](../data/20260831-tp4-count2560-cpu-affinity-a1-negative.json).
Protected TP4 MTP0 `5.515783 tok/s` and MTP4 `20.727176 tok/s` results are
unchanged.
