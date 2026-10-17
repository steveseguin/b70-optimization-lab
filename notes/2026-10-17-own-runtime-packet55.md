# Packet 55: one-card IQ3 feasibility preparation

The owner requested three measurements before choosing a one-card engine:
route locality, a new exact CPU expert implementation and expert-slab transfer
latency. Preparation is CPU-only on `steve-b70s`, nice 19, affinity
`4-15,20-31`. The coordinator owns every GPU window and quiet CPU throughput
window. Packet49d-round3, the existing oracle, sealed packets, services and
the memory fence at blocks 53–57 remain untouched.

`git pull --rebase` completed on main before work; no incoming change was
needed. Root free space was about 18 GB. Packet55 has a 1 GB total build cap,
serial compilation, compact route logs and bounded transfer buffers. No model
payload, GPU, sudo, service, power, swap or page-cache operation was performed
while writing the initial plan.

The [feasibility equations](../experiments/own-xpu-runtime/ONE-CARD-FEASIBILITY.md)
charge actual executed routes and same-card MTP work. Missing timings are
explicitly pending. The three measurements select a design; actual one-card
GPU layer timing, CPU mailbox and CPU/DMA contention still need integration
measurements before an end-to-end speed claim.

The initial dependency check found that packet49c loads its existing MTP
weights from `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`, while the owner's
packet55 weight-path allowance names only the three target GGUF shards under
the admitted IQ3 directory. A narrow question asks whether the coordinator may
reuse those existing hash-bound draft weights. Preparation does not read them.
Until resolved, a draft route window must refuse rather than silently widening
the admitted source paths.

Credit Niko1221 / Strata for the cache/CPU-miss idea, as already recorded in
ONE-CARD-DESIGN. The implementation is independent lab code and reuses only
the lab's arithmetic definitions, fixtures and safety mechanisms.

Detailed component checks, commands and retained evidence will be appended
as preparation completes. No route hit rate, CPU throughput, H2D bandwidth or
one-card speed has been measured in this preparation.
