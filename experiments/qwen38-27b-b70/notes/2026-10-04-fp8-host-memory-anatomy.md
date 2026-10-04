# What the two-card FP8 server's 9 GiB of host memory is, and why it cannot be handed back (2026-10-04)

## In plain words

A loaded two-card Qwen 27B server uses about 9 GiB of this machine's 15 GiB of ordinary memory, on top of what
sits on the cards. That leaves about 3 GiB free, which is why two research servers were stopped by the memory guard
on October 3. We checked whether that 9 GiB is leftover from loading the model and could simply be released. **It is
not. It is live working memory of the GPU runtime, and nothing we control can free it.** What we changed instead is
the guard: its floor goes from 2.5 GiB to 2 GiB, so a healthy server is no longer stopped with the machine in no
trouble.

## What was measured

One server at a time, started for the measurement and stopped straight after. Receipts:
[`../data/2026-10-04-fp8-host-memory/`](../data/2026-10-04-fp8-host-memory/).

| Process | Host memory | Largest pieces |
| --- | ---: | --- |
| API server | 1.37 GiB | allocator heap 0.76 GiB |
| engine core | 0.82 GiB | allocator heap 0.41 GiB |
| GPU worker, card 0 | 3.38 GiB | allocator heap 1.18 GiB, then anonymous mappings of 507, 457, 166 and 122 MiB |
| GPU worker, card 1 | 3.37 GiB | allocator heap 1.18 GiB, then 579, 507, 165 and 106 MiB |
| whole container | 8.95 GiB anonymous, 2.71 GiB file cache | host memory available with it loaded: 3.14 GiB |

Two questions, two short probes on a research server
([`../scripts/run-20261004-fp8-malloc-trim-probe.py`](../scripts/run-20261004-fp8-malloc-trim-probe.py), overlay
[`../overlays/b70-malloc-trim/`](../overlays/b70-malloc-trim/)):

1. **Is the heap just fragmentation left by the weight load?** No. Asking every process to return its free heap
   pages (`malloc_trim(0)`) took 2 to 4 ms each and gave back **0.2 GiB of 8.94** (workers 3.37 -> 3.35 and 3.34,
   API server 1.36 -> 1.26, engine 0.82 -> 0.78). The strict suite was 12/12 before and after, 90.22 and 90.30 tok/s.
2. **Are there host-side copies of tensors that could be dropped?** No. A census of every live CPU tensor found
   none in the API server and the engine, and ten tiny index tensors in each worker: **0.00 GiB**.

So the 3.4 GiB in each worker is native memory of the compute runtime: compiled kernels and their caches, the
Level Zero and oneDNN runtime state, the graph compiler's output. It is not reachable from Python and it is not
waste we can trim.

## What follows from it

- **The two-card server's host cost is about 9 GiB and stays there.** Plan around it: one such server leaves room
  for an agent session and little else.
- **Guard floor 2.5 -> 2 GiB** in [`../scripts/host_memory_guard.py`](../scripts/host_memory_guard.py). At 2.5 GiB
  the guard sat 0.6 GiB under a healthy server and fired twice at 2.4 GiB; a guard kill of a busy server is itself a
  GPU fault source. `earlyoom` remains the backstop at 1.2 GiB.
- **Do not attach a debugger from the host to a process inside the container.** The first attempt at probe 1 did
  that (`gdb -p`); the debugger cannot follow a process in another PID namespace, the container's first process
  died, and the whole server went down with it. No fault line was logged, but only by luck. The in-process overlay
  is the safe way.
