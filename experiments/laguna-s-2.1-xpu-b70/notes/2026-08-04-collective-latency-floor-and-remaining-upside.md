# The collective latency floor, and what is actually left

Date: 2026-08-04 America/Toronto

Status: **measured. Standalone 4-rank XCCL benchmark plus six configuration
arms. Config-only tuning is exhausted; the remaining levers need code.**

## The floor

A standalone `all_gather_into_tensor` benchmark on the four B70s, no model
loaded, at and around the payload a 12-row decode step moves:

| rows | payload | us/call | GB/s |
| ---: | ---: | ---: | ---: |
| 1 | 6.0 KiB | 48.4 | 0.13 |
| **12** | **72.0 KiB** | **45.9** | **1.60** |
| 48 | 288.0 KiB | 53.6 | 5.51 |
| 192 | 1152.0 KiB | 175.3 | 6.73 |
| 768 | 4608.0 KiB | 689.8 | 6.84 |

Cost is **flat from 6 KiB to 72 KiB**, which is the definition of latency-bound.
Peak bandwidth tops out at **6.84 GB/s**, far below what PCIe should deliver.

oneCCL reports `provider: tcp`. Collectives between four GPUs in one chassis are
going over the TCP libfabric provider.

## Every configuration arm tried

| arm | result |
| :--- | :--- |
| baseline (ofi/tcp) | 45.9 us |
| `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0` | 44.7 us (-2.6%) |
| `CCL_ALLGATHERV=direct` | 44.5 us (-3.1%) |
| `CCL_ATL_SHM=1` | 51.7 us (worse) |
| `FI_PROVIDER=shm` | fails: "can't find suitable provider" |
| `FI_PROVIDER=shm` + `FI_HMEM=ze` | fails the same way |
| `CCL_ZE_ENABLE=1` + `CCL_ZE_IPC_EXCHANGE=drmfd` | errors |
| `CCL_ATL_TRANSPORT=mpi` | fails in `atl_mpi::init` -- needs mpiexec/PMI, which vLLM's own process spawner does not provide |
| `--all2all-backend naive` / `pplx` | removed upstream, silently fall back to `allgather_reducescatter` |

**Nothing moves it more than 3%.** The `shm` provider is the one that should win
on a single node and it will not initialise, because it does not advertise the
device-buffer (HMEM) support the XPU path requires.

## The gap that is left

In-situ, vLLM's allgatherv measures **~122 us** per call against this **~45 us**
standalone floor -- a **2.7x** gap that is not oneCCL's. Candidates: the
variable-length `allgatherv` versus plain `allgather`, contention with concurrent
compute, or several collectives in flight at once. Not yet isolated.

## Quantified upside

A decode step at 32,640 tokens measures 26.5 ms and carries ~98 allgatherv calls
plus ~14 allreduce, roughly two collectives per layer across 48 layers.

| change | step | est. tok/s | vs 39.589 |
| :--- | ---: | ---: | ---: |
| today | 26.5 ms | 39.6 | 1.00x |
| close the 2.7x vLLM-side gap to the floor | ~19 ms | ~55 | ~1.4x |
| remove EP collectives (TP-shard experts) | ~15.5 ms | ~68 | ~1.7x |
| both | ~13 ms | ~80 | ~2.0x |

Even both together land near **80 tok/s**, short of the 150 target at 32K. So
collective work is necessary but, on this evidence, not sufficient -- the
remaining time is attention (~6.2 ms/step) and host-side overhead.

## Why the obvious structural fix is not a free win

Disabling expert parallelism replaces ~98 latency-bound all2all collectives per
step with ~14 all-reduces, the largest single lever in the table. It is blocked
by a real dependency, not a policy: the M12 shared-elementwise kernel is built
around the expert-parallel layout, and the engine refuses to start without it
(`Laguna shared-elementwise selection requires the exact ... parallel identity`).

Relaxing that contract means disabling the fused kernel in order to measure the
configuration the fused kernel is part of -- exactly the confound that made the
earlier `q8` and `qdepth` arms uninterpretable. Doing this properly means
teaching the kernel a TP-sharded layout, which is kernel work.

## Boundaries

Standalone benchmark: no model, no quantisation, no speculation involved. The
26.5 ms step and 39.589 tok/s are prior cold-cache measurements, unchanged here.
The estimates in the upside table are arithmetic on measured components, clearly
labelled as estimates, and are not measurements. The protected
`125.4619731637751 tok/s` conventional short-decode record is untouched.
