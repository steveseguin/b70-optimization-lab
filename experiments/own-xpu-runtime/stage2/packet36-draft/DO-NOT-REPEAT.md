# Packet36 do not repeat

| Approach | Finding | Revisit condition |
| --- | --- | --- |
| Put DRAFT inside HALF after waiting for rank0 | Adds draft serially: D+max(A,B). | Separate DRAFT overlaps rank0 completion/redo. |
| Draft with the previous guessed embedding | Makes draft cache speculative. | Separate rollback design and gates; outside this packet. |
| Reuse target streams/controls/scratch as writable draft state | Can invalidate exact target state or cached bindings. | Private allocations; immutable head only. |
| Use target prepare_token for draft embedding | Advances PLE histories. | Read a bounded immutable row directly. |
| Check cache position before disabled state | Failed provider later aborts target. | Permanently disabled provider returns before sequence check. |
| Label immediate return a stalled-provider test | Does not exercise waiting. | Bounded cooperative 50ms stall test plus permanent disable. |
| Treat stuck GPU kernel as recoverable provider error | Queue and allocations remain busy. | Owner failure, one cooperative stop, retain ownership. |
| Convert official norm offsets to BF16 gains | Adds a needless rounding boundary. | F32 1+w gains (or raw-offset equivalent kernel). |
| Use Q8 group32 for the packet31 group16 variant | Changes draft quantizer. | New measured variant; group16 is the tested choice. |
| Reuse packed IQ routed dispatch for expanded int8 | Wrong weight format. | New routed dense wrapper with explicit code/scale layout. |
| Generic adapter for draft activation/mix/combine | Carries unrelated operation branches into device kernels. | Compile-time draft operation wrappers, same arithmetic. |
| Inherit packet32 real_campaign parallelism | Four pipelines exceed this task's CPU process budget. | Five modes run serially here. |

Packet32's rollback, owner, fault and arithmetic exclusions remain binding.
