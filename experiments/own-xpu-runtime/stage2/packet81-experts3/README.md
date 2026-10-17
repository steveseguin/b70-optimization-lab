# Packet81 routed-expert throughput round 3

CPU preparation of three exact-order input-load candidates, copied from
packet75 bundle sources. [Analysis](ANALYSIS.md) was committed first.
Production remains wide64, dense production, target HC production, draft-HC,
batch rollback, draft rank1, 24/24 layers, full BF16 KV and
`iq3-p49-split32-v1`. Packet49 is the device output oracle.

| View | Gate/up inputs | Down inputs |
| --- | --- | --- |
| production | original | original |
| gate-input-packed | packed uint32 vector | original |
| down-input-packed | original | packed uint32 vector |
| input-packed | packed uint32 vector | packed uint32 vector |

Each packed read fetches exactly the same eight BF16 elements as four uint32
words, then extracts the original sixteen-bit values. Physical/logical lanes,
quantization, individual FP32 products, chain order, reduction tree and output
rounding remain unchanged. Device inputs use existing aligned allocations;
K offsets are multiples of eight BF16 elements. No weight layout, SLM table,
extra buffer, persistent group, prompt reuse or compressed KV is introduced.

Offline BMG-G31 gate/up static loads: 51 to 27; down: 79 to 31.
Instructions: 1993 to 1897 and 2955 to 2755. All use 128 configured GRFs and
have no spills. This is compiler mechanism evidence, **not a speed result**.
[Candidate assembly report](register-report-candidate.json).

Both compilers pass two fresh runs per view, with 18 expert fixtures,
110,592 raw FP32 chain comparisons and 3,456 tree comparisons per run.
[Byte evidence](evidence/cpu-byte-identity.json),
[retained raw output and case logs](evidence/retained-cpu.json).
The eight full-size CPU startups exercise actual allocation, post-load
capture and draft initialization; operation type capture proves all selections
reach their intended kernels. The original memory limits pass; an undersized
head and five invalid selections fail as required.
[Full-size startup](evidence/full-shape.json). No model payload was read.

Shared wrapper source is referenced directly and pinned to the existing
reviewed v4-lanes bytes. 80 shared protocol checks and five packet checks pass.
[Python checks](evidence/python-tests.json). These CPU checks do not replace
native model identity or timing.

[Screen commands and queue proposals](WINDOW.md),
[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md),
[negative/deferred choices](DO-NOT-REPEAT.md), [rebuild and retention](RETENTION.md).
Only the entrypoints named there belong to this packet's supported screen path.
Other copied chain/submission helpers preserve bundle source context; they
are not a qualified packet81 record-chain or publication interface.
