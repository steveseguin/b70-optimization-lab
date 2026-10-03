# Where the pipeline's CPU goes: threads spin in the GPU runtime's event wait (2026-10-03)

Server `encoder-server-gil-92p` (packet `prepared-encoder-gil-92a`, kernel
7.0.0-38, GuC 70.44.1, memory blocks 53-56 offline, lockup panic off), runner
`scripts/run-campaign-92p.sh`: warm 3 @209589, one 160-prompt arm @209689 at
the default switch interval. `sudo perf record -F 199 -g -p <server pid> --
sleep 40` taken 45 s into the arm; 42,984 samples. Text outputs in
`data/perf-92p/`; the raw `perf.data` is on the host under
`/home/steve/b70-host-diagnostics/run-92p/`.

## Result

| Where | Share of samples |
| --- | ---: |
| Kernel | 75.7 % |
| of which `entry_SYSCALL_64` / `SYSRET` (syscall entry and exit) | 48.2 % |
| `python3.12` (interpreter) | 8.8 % |
| `libze_intel_gpu` (Level Zero driver) | 3.8 % |
| `libtorch_cpu` + `libtorch_xpu` | 3.9 % |
| `libsycl` + UR adapter | 1.3 % |
| x264 / avcodec (preview save) | 1.0 % |

Five threads each take 16-19 % of the samples (about one core each, matching
`top -H`: 73-100 % each). Inclusive time per thread:

| Thread | In `ur::level_zero::urEventWait` | In `appendUSMMemcpy` (blocking copy) | In the interpreter |
| --- | ---: | ---: | ---: |
| 6637 | 87 % | 5 % | 1 % |
| 6638 | 79 % | 8 % | 1 % |
| 6696 | 60 % | 12 % | 17 % |
| 6695 | 61 % | 11 % | 17 % |
| 6807 | under 1 % | 60 % | 10 % |

(Percentages are of that thread's own samples. Thread roles are inferred,
not labelled: two event-wait-only threads look like the encode workers, the
two with interpreter time like the sampler workers, the copy-heavy one like
the eager decode worker.)

## Reading

1. The "3.8 CPU cores" that packet 92a measured are **busy-waiting**. The
   Unified Runtime's Level Zero adapter waits for a GPU event by polling in a
   `sched_yield` loop, so a thread that is only waiting for its GPU work to
   finish shows as a core at 100 %. It is not host work and it is not lock
   contention.
2. So every worker is, most of the time, **waiting for the GPU**: 60-87 % of
   each sampler and encode thread, and the decode thread is mostly inside
   blocking device copies. The pipeline is bound by GPU work completing, not
   by Python or by the host issuing work. This replaces the reading in the
   90c and 91b notes.
3. That leaves the 90c busy-window figure (sampler cards 41-45 % occupied)
   unexplained and unverified. The xe driver's own per-client engine counters
   (`/proc/<pid>/fdinfo`, `drm-cycles-ccs` and `drm-cycles-bcs`) are the
   independent check: cumulative compute-engine busy time for this server was
   about 243 s, 174 s, 210 s and 287 s on 0000:23, :27, :43 and :47 over a
   life that contained a 292 s arm, i.e. the busiest card was near
   saturation. `scripts/sample-gpu-engine-busy.py` samples those counters
   every two seconds; the 91c repeat campaign records them for the control
   and replica placements.
4. The copy engine is busy too (140-210 s of `bcs` time per card over the
   same life). Staging activations and decode outputs through host memory is
   not free and has never been in the budget.
5. A process split would not help a GPU-bound pipeline. Packet 92b stays
   useful only as a test of whether per-process contexts schedule better on a
   shared card; the levers that matter are which card carries what, and how
   much GPU work a clip costs.

Not established: the PCI-address-to-`xpu:N` mapping (assumed ascending), and
how much of each card's busy time is this pipeline's own queueing behind
itself on the single compute engine.
