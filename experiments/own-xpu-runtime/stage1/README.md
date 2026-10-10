# Stage 1 — packet index

The owner approved the objective and the reviewer accepted Stage 0 for CPU
work. The [ten-packet plan](../STAGE1-PLAN.md) remains the stage authority.
Each packet has its own gate; a CPU contract is not a working runtime.

| Packet | Status | Evidence |
| --- | --- | --- |
| 1 — CPU identity and tensor contract | PASS, 2026-10-10 | [Frozen identity, directory, checks and findings](packet1/README.md) |
| 1b — CPU arithmetic and loader parsers | CPU preparation passed, 2026-10-10; device arithmetic UNVERIFIED | [Frozen reference, parser tests and packet 4 fixtures schema](packet1b/README.md) |
| 3 prep — C++ resource owner | Host tests and SYCL compile only; native execution unauthorized | [Build receipt, teardown contract and first native command](packet3-prep/README.md) |
| 4 prep — fixture transport and CPU replay | Worker driver: 40 CPU tests pass; A367 stage, memory floor and host halt block the native window | [Driver, evidence and admission](packet4-prep/driver/README.md) |
| 2, 3 native, 4–10 | Not executed by this task | Separate scope, storage and native gates remain in the plan |

This lab-authored index summarizes packet 1's check receipt. No weight
acquisition, native work, device allocation or performance qualification is
authorized by this index.
