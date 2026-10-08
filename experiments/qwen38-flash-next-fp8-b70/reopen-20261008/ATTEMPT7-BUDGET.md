# Attempt 6 host-memory correction and attempt 7 decision

2026-10-08, CPU-only on steve-b70s. **Do not prepare a threshold-only attempt
7.** The unchanged placement projects **100.623 GB steady pressure**, above
the owner's 97 GB criterion. The explicit staging allowance gives a
**100.891 GB loading scenario**, not a proven upper bound. No new launch,
GPU access, Docker operation, installation, secret access, Git commit/branch,
host setting change or port 8188 access occurred.

The important missing term was **pinned allocator rounding**. The intended
expert tensors total 51.118 GB, but their separate host allocations require
74.491 GB under the power-of-two allocator model. Attempt 6's samples closely
follow those rounded sizes. This replaces the earlier 77.955 GB forecast and
the claim that attempt 5 established removal of a Flash-Next device shadow.
Attempt 5 failed at init_device without any load_begin event.

## What GPUActive means here

GPUActive counts system-memory pages held for GPU objects, not VRAM usage,
CUDA-style utilization, or exclusively unintended device shadows. The kernel
[counter introduction](https://git.zx2c4.com/wireguard-linux/commit/fs/proc?h=devel&id=2232ba9c7931d5c1061f7f4e897b944ea39c3aa9)
distinguishes active GPU-object pages from reclaimable GPU page pools.
[TTM allocation accounting](https://code.googlesource.com/linux/torvalds/linux/+/dab01c597f6bd40e0efe7da967b8374ca1971b79/drivers/gpu/drm/ttm/ttm_pool.c)
charges system pages to NR_GPU_ACTIVE and transfers cached free pages to
NR_GPU_RECLAIM. The running distribution's exact xe/i915 patch set was not
available: these are upstream mechanism references, not an audit of that binary.
This host's saved logs identify xe; do not generalize this accounting to every
i915 version or every kind of externally pinned user page.

The [LTX note](../../ltx25-b70/notes/2026-10-04-host-ram-shadow-of-vram.md)
isolated device-buffer peer backing with a controlled allocation probe. This
lane intentionally asks for pinned CPU allocations. Disabling device deferred
backing cannot remove memory the application deliberately allocates on the CPU.
Attempt 4 still has a large residual compatible with the LTX mechanism, but
4 and 6 changed placement as well as environment: they are not a matched A/B.

The [PyTorch XPU allocator](https://raw.githubusercontent.com/pytorch/pytorch/v2.13.0/aten/src/ATen/xpu/CachingHostAllocator.cpp)
inherits the common host allocator and calls sycl::aligned_alloc_host.
The [common allocator](https://raw.githubusercontent.com/pytorch/pytorch/v2.13.0/aten/src/ATen/core/CachingHostAllocator.h)
rounds allocations to power-of-two sizes subject to its configuration.
The local 2.11 header also has unconditional PowerOf2Ceil at line 302;
it is supporting evidence, **not** the container's 2.13.0+xpu build identity.
No container binary or live allocator statistics were inspected in this task.
Applying that rounding to the actual receipts explains the observations below;
the rounded columns remain inferred reservations, not measured allocator counters.

## Correlation by loader phase

All values are decimal GB. Times are seconds since the first load_begin.
The [full JSON](evidence/attempt6-host-attribution.json) hashes its saved inputs;
the [per-sample CSV](evidence/attempt6-host-attribution.csv) keeps every requested
meminfo counter, phase, worker RSS and cumulative allocation count.

| Attempt / phase | Time | GPUActive measured | Expert payload receipted | Expert blocks inferred | Bound PLE cache | Host pressure measured |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 4, construction near refusal | 8.04 | 74.063 | 4.507 | 6.115 | 0 | 90.013 |
| 5, init_device / cancellation peak | — | 1.383 | 0 | 0 | 0 | 12.237 |
| 6, before construction | -0.27 | 1.383 | 0 | 0 | 0 | 12.399 |
| 6, construction | 2.23 | 14.568 | 7.527 | 10.939 | 0 | 29.971 |
| 6, construction | 5.73 | 41.180 | 26.090 | 37.648 | 0 | 57.180 |
| 6, rank 3 copying; others constructing | 6.73 | 47.705 | 30.022 | 43.084 | 1.074 | 64.195 |
| 6, same mixed phase | 10.73 | 71.721 | 45.937 | 66.840 | 1.074 | 88.562 |
| 6, first post-cancel sample | 11.23 | 73.063 | 46.960 | 68.451 | 1.074 | 90.060 |

At the last row, **68.451041 GB expert blocks + 2.147484 GB rounded input
embeddings + 1.073742 GB PLE cache + 0.001049 GB PLE step blocks +
1.390068 GB residual = 73.063383 GB GPUActive**. That residual is only
6.8 MB above the 1.383252 GB pre-construction reading. Earlier samples are
asynchronous to allocation-complete receipts; an in-flight allocation can be
charged before its receipt. This is much stronger evidence than comparing
GPUActive with raw tensor sizes or worker RSS alone. It does not identify
every remaining driver allocation.

At attempt 4's peak, the analogous rounded expert term was just 6.115 GB;
expert device payload already receipted was 56.520 GB. Its 74 GB GPUActive
cannot be explained by the small intended host allocations alone. Thus the
blanket statement that attempts 4 and 6 count only intended offload is also
incorrect. Attempt 6 is the evidence for the current pinned-host interpretation.

| Attempt / observation | AnonPages | Cached | Shmem | Unevictable | Mlocked |
| --- | ---: | ---: | ---: | ---: | ---: |
| 4, sampled pressure peak | 8.890831 | 5.197337 | 1.215439 | 0.003277 | 0.000131 |
| 5, sampled pressure peak | 6.414836 | 93.000598 | 0.003813 | 0.003277 | 0.000131 |
| 6, before construction | 6.567551 | 101.394915 | 0.003817 | 0.003277 | 0.000131 |
| 6, 5.73 s | 10.852094 | 48.851366 | 0.003817 | 0.003277 | 0.000131 |
| 6, sampled pressure peak | 11.351757 | 6.179217 | 0.003822 | 0.003277 | 0.000131 |

Flat Mlocked/Unevictable do not rule out driver-owned system pages. Cached
shrinks as those pages are allocated. Attempt 6's cgroup anon is 10.621 GB at
the anchor; worker RSS is 2.902/2.782/2.788/3.442 GB and contains shared/file
pages. These counters overlap and must not be added to GPUActive or pressure
as though all were disjoint. GPUActive returns to 114,688 bytes after teardown.

## How far loading got

The guard refused rank 1's next 196,608,000-byte w13 host tensor at 11.004 s:
current pressure 89.975808 GB, projected 90.172416 GB. That request rounds to
268,435,456 bytes, so the guard's payload-based projection was itself optimistic.
The independent sampler reached 90.059751 GB 229 ms later. This was not a
completed load or a plateau.

| Rank / container PID | Completed expert parameters | Constructed layers (zero based) | Expert payload still unallocated | Rounded expert blocks still needed | Other outstanding work |
| --- | ---: | --- | ---: | ---: | --- |
| 0 / 450 | 96/96 | 0–47 | 0 | 0 | PLE cache/metadata binding; target checkpoint loading |
| 1 / 477 | 78/96 | 0–38 | 2.541158 GB | 3.623879 GB | layers 39–47, later model tensors, PLE, target loading |
| 2 / 512 | 84/96 | 0–41 | 1.617101 GB | 2.415919 GB | layers 42–47, later model tensors, PLE, target loading |
| 3 / 547 | 96/96 | 0–47 | 0 | 0 | PLE bound; target checkpoint w13 copy interrupted |

All four input-embedding and step-buffer admissions occurred. Only rank 3
bound its 1 GiB PLE cache. No allocations-rank*.json exists: the complete-load
snapshot was never reached. MTP load, postprocessing completion, KV allocation,
compilation/capture and readiness remain unobserved. The staging ledger peaks
at 268,431,360 bytes and ends empty. This is a bounded staging pool, not tens
of GB of evidence for a disappearing transient. The receipts do **not** name
each checkpoint copy or its completion; exact checkpoint bytes/tensors still
to read on rank 3 are unknowable from this run. Allocation counts are not
weight-loading percentages.

## Honest host budget

| Retained component | Planned payload | Inferred / assumed host cost |
| --- | ---: | ---: |
| Rank 0 expert rows | 12.779520 GB | 18.924700 GB (17.625 GiB) |
| Rank 1 expert rows | 12.779520 GB | 18.522046 GB (17.25 GiB) |
| Rank 2 expert rows | 12.779520 GB | 18.522046 GB (17.25 GiB) |
| Rank 3 expert rows | 12.779520 GB | 18.522046 GB (17.25 GiB) |
| Input embeddings, four ranks | 1.271398 GB | 2.147484 GB |
| PLE cache, four ranks | 4 GiB | 4.294967 GB |
| PLE pinned step buffers | 0.000655 GB | 0.001049 GB |
| PLE metadata, four ranks | 1.736346 GB | 1.736346 GB |
| Private runtime, excluding bound PLE metadata | — | 10.186776 GB, from cgroup anon; attribution approximate |
| Other GPUActive residual | — | 1.390068 GB, measured residual retained |
| OS / initial host-use allowance | — | 4.969857 GB, saved post-hash observation |
| Other pressure residual | — | 1.405649 GB, anchor remainder; not another measured allocation |
| **Steady pressure scenario** | | **100.623034 GB** |
| Explicit staging, shared across ranks | | **+0.268435 GB** |
| **Loading scenario** | | **100.891470 GB** |

Equivalently, start at the observed 90.059751 GB and add the remaining
6.039798 GB expert blocks, 3.221225 GB PLE cache and 1.302260 GB metadata.
That retains the observed OS/runtime/driver residual instead of subtracting a
speculative shadow. It assumes no major net release or extra retention in the
remaining phases. Allowing an **additional assumed 2 GiB** of loader/capture
retention gives **103.038954 GB**. No full-run peak bound has been measured.

The mmap PLE payload is **51.200246 GB**, not a second pinned table. Its useful
page-cache working set depends on row misses and access locality; this load
did not measure those. A **4 GiB speed-cache allowance** remains an assumption.
Treat it as additional desired resident working memory: steady pressure plus
that allowance is **104.918002 GB**, loading plus it **105.186437 GB**. It is
not automatically 4 GiB more MemTotal-minus-MemAvailable, since Linux counts
reclaimable file pages as available. Do not add the existing 6.179 GB Cached
reading to the pressure again. Keeping the entire table hot would require
roughly 151.8 GB in this accounting scenario, beyond this host.

The corrected generic planner adds **24.249238 GB** of allocator padding,
separately from logical pins, and changes the previous 10 GB private/driver
allowance to **13 GB** (rounded above the roughly 12.98 GB anchor decomposition
for private runtime + GPU residual + other pressure). Its conservative
working-memory scenario is **105.203945 GB** including the 4 GiB active-file
allowance and staging. Removing those two allowances gives **100.640542 GB**
for steady pressure, consistent with the sample-anchored scenario above.
[Fresh planner output](evidence/attempt7-revised-host-prediction.json).
All required phase bounds remain null and admission stays REFUSED. Saved
attempt forecasts and raw receipts are preserved as historical evidence.

The exact watchdog line from saved MemTotal is **98.409329 GB** pressure
(124.179132 GB minus 24 GiB), not 97 GB. Even that line is below the current
steady estimate. The owner's 97 GB criterion is a useful tighter target.
A 96 GB guard therefore does not isolate an assumed harmless transient.

## Lossless alternatives, proposed only

| Total pinned PLE cache | Estimated host saving, including cache metadata | Steady pressure scenario |
| --- | ---: | ---: |
| 2 GiB | 2.375654 GB | 98.247381 GB |
| 1 GiB | 3.563481 GB | 97.059554 GB |
| 0.5 GiB | 4.157394 GB | 96.465640 GB |

Cache reduction preserves checkpoint bytes but can increase disk misses and
decode latency. At 0.5 GiB the modeled loading figure is already 96.734076 GB,
before unknown retention. Smaller cache alone gives little margin.

A stronger alternative is to choose expert counts at host allocation-size
boundaries. For example, 41 host rows require 256 MiB w13 + 128 MiB w2 blocks;
40 rows require 128 + 64 MiB. Moving one unchanged row to VRAM costs
4,915,200 bytes and saves **192 MiB** host memory.

The offline count-only proposal keeps rank 0 unchanged and moves
**62 / 64 / 62 rows** to VRAM on ranks 1 / 2 / 3. It saves
**2.415919 / 2.013266 / 2.315256 GB** host memory, costing
**0.304742 / 0.314573 / 0.304742 GB** VRAM. Total host saving **6.744441 GB**;
projected steady/loading pressure **93.878594 / 94.147029 GB**. Exact layer
counts are in the analysis JSON. No placement file has been changed; expert
IDs still need selection and the new maps, bytes and outputs need their gates.

At the existing unmeasured VRAM allowances this leaves roughly
**4.247 / 4.238 / 4.247 GiB** usable on ranks 1–3, preserving the 4 GiB reserve
even at utilization 0.90. Raising only those ranks to 0.92 would add
**0.6059 GiB (0.650580 GB) per rank** to the utilization line, not create more
physical free memory. Such a per-rank override is not wired into the shared
launcher; rank 0 must remain at 0.90 because attempt 5 rejected global 0.92.
Simply filling all newly allowed space can break the separate 4 GiB reserve.
This boundary-aware proposal need not spend that extra utilization headroom.

Full 16-bit KV stays at the certified **376,569,856 bytes per rank**. Reducing
KV is not part of these proposals. Combining the row proposal with a 2 GiB
PLE cache gives a further sensitivity of **91.502940 GB** steady pressure.
None of these estimates satisfies the existing MTP1 admission requirement
of measured plateau times 1.15 <=90 GB; a successful load-only observation
would not authorize generation or relaxation of that gate.

## Change, tests and command decision

The small planning change counts each pinned allocation's rounded size,
withdraws causal shadow credit, and retains the original guard/watchdog and
VRAM/output gates. The new CPU analyzer reconstructs phases and remaining
retained allocations from saved receipts. It does not contact a runtime.

The requested `--loading-ram-guard-gb 96` attempt-7 command is **not prepared**:
the task explicitly conditions it on a plateau <=97 GB, and that condition
fails. The existing CLI still correctly rejects values above 90. There is
therefore no runnable attempt-7 launch command with a placeholder health
receipt yet. A revised placement/cache contract, new CPU checks and updated
budget must precede preparation of that command. No cancellation-message
plumbing was changed on this branch of the decision; precise checkpoint bytes
remaining cannot be recovered from the existing nameless copy receipts.

Re-run the CPU analysis with:

```sh
python3 -B experiments/qwen38-flash-next-fp8-b70/reopen-20261008/analyze_host_budget.py \
  --output experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/attempt6-host-attribution.json
```

**201/201 CPU tests passed, zero skips**, including eight new attribution and
size-class regressions and all four logical-rank rehearsals. Results are in
[the test log](evidence/cpu-attempt7-budget-tests.log).
The four-rank rehearsal uses small CPU tensors and emulated XPU transport;
it establishes neither full-size memory fit nor native output quality.
