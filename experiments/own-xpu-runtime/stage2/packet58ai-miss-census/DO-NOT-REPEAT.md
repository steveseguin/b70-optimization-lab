# Packet58ai boundaries

- Never infer miss counts from fills. Count the routed IDs against the published pointers.
- Never present split-partition timings as the original mixed kernel's internal stalls.
- Never convert subgroup clock cycles to milliseconds or compare clocks across subgroups.
- Preserve p60fusion, down-tile16, 21,552,729,600 cache bytes, overlap and BF16 KV in every view.
- B0 is the original mixed schedule with ordinary profiling events; B1 is explicitly serialized diagnostic partitioning.
- Events are retained at command invocation, outside capture, and queried after the existing drain. No added token fence.
- Different cache residency across instrumentation views is retained and labeled; never subtract their costs as if matched.
- Use the generous B0 miss-containing-kernel service ceiling for the decision, not a sum of extrapolated layer means.
- The 0.670 ms threshold is the owner's conservative +2% threshold. Exact arithmetic gives a slightly smaller 2% saving.
- Never promote this repeated diagnostic or use it to replace 30.396 tok/s.
- Do not queue or launch from preparation. The coordinator waits for both two-card queues to empty.
- Preserve parent packets, stage2/screen, live queues and shared ops unchanged.
- A failed device stage is not retried. Use the inherited graceful drain and fault evidence path.
