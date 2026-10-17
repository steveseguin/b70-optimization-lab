# A367 diagnostic census: tracing feasibility

CPU reseal, October 17, 2026. This reseal ran no model, device probe or tracer
target. The coordinator's device evidence changes the October 16 plan.

## Device evidence and chosen arm

See [microtest results](../../../../../notes/2026-10-16-flash-next-trace-feasibility-microtests.md#device-results-2026-10-17-coordinator)
and `data/2026-10-17-flash-next-trace-feasibility/20261017T001502Z/`.

- Active at capture: 50/50 replays had 8/8 timestamped kernels.
- Paused at capture and resumed before replay: zero replay kernels, while eager
  kernels remained visible. Resume after readiness is therefore invalid.
- Paused four-rank oneCCL init took about 1 ms and its first 4 KB all-reduce about
  1 s, like control. The old Laguna init stall did not reproduce with these flags.
- All traced ranks completed work then segfaulted at exit (`ucs_handle_error`,
  address 0x40); control exited cleanly. Zero GPU fault lines were reported.
  The raw analyzer's older aggregate "partial/incomplete" verdict reflects its
  requirement for clean exits and agreement between both capture variants;
  the individual device observations above are the coordinator's interpretation.

Run **graph-census only next**. Eager remains secondary with separate admission;
graph-reference is optional because replay c supplies full-suite untraced timing.
Full-model overhead, memory and four-rank step coverage remain unmeasured.
Historical Laguna/DeepSeek stalls are not erased, but they do not override the
matched new microtests. Never reuse their failed host-timing/submission flag mix.


## October 17 profile crash and communicator audit

Coordinator report: run `a367c-20261017T002647Z`, 00:39–00:57 UTC, loaded all
four ranks and acknowledged the old resume trigger. Roughly ten seconds later,
all four workers segfaulted at address 0x140 in `determine_available_memory`:
`ProcessGroupXCCL::initXCCLComm` → `ccl::create_communicators` → `ccl_comm::init`
→ `allocate_buffers` → `coll_init` → SYCL wait → `urEventWait` →
`libur_adapter_level_zero_v2` → `libze_tracing_layer` → `libze_intel_gpu`.
Zero GPU fault lines; orderly teardown and full 305-second watch;
`census-run.json` has `passed=false` and `expected_tracer_exit_crash`. That label
does not make this startup failure valid. Original evidence remains at
`/mnt/raid-models/bench-results/a367c-20261017T002647Z/server.log` and
`census-run.json`. This CPU change incorporates the coordinator report; it
does not claim another device reproduction.

The earlier paused CCL test created its communicator at the first all-reduce
before resume; its later 64 MB all-reduce succeeded while tracing. One-card
event-wait tests with v1/v2 adapters, traced and untraced, did not crash. The
working hypothesis is lazy communicator creation under active L0 tracing,
not ordinary `urEventWait` alone.

The [source audit and complete group table](COMMUNICATOR-AUDIT.md) establishes
the post-profile/post-KV/pre-capture hook and finds no active source-visible
late group creation for this exact launch. Default WORLD is warmed before
load; TP and the MTP draft use their existing group in profiling. EP and the
separate coordinator WORLD device groups may remain unused. PP/DP/PCP/DCP are
singletons; PP broadcast siblings, EPLB, elastic scaling, KV transfer and
dynamic weight-update groups are absent. No blanket warm collective is added:
initializing unused groups would change allocations and memory use.
**Residual risk:** native XCCL/oneCCL may allocate resources or communicators
per stream, operation, dtype or size after this hook. The clean Python source
cannot prove otherwise. The microtest supports reuse, not full-model safety.

`feasibility/run_driver.py` now registers `ccl-create-after-resume` immediately
after `ccl-paused`. It holds all ranks before `init_process_group`, resumes,
then releases them to create the lazy communicator at the first all-reduce.
Expected outcome: SIGSEGV; retain actual per-rank exit codes and last stages,
and do not treat an unrelated nonzero exit as confirmation. No device run was
performed here. `--only` accepts one or multiple comma-separated steps and
preserves registered order, for example:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B experiments/own-xpu-runtime/stage1/packet4-prep/a367-census/feasibility/run_driver.py --only ccl-paused,ccl-create-after-resume
```

This is a future separately admitted device command. Add `--plan` for CPU-only
inspection. It never kills or retries; an overrun prints and keeps waiting.
The paused control now pauses before explicit communicator destruction. If it
finishes all collective work, completes pause/release, all ranks exit with only
zero/SIGSEGV codes, and no budget/control failure occurred, its failed exit
receipt is retained and the next registered reproduction may run. Other control
failures stop the sequence. Reproduction failure remains failure, never a clean
pass or an automatic retry. A single-step reproduction is also supported with
`--only ccl-create-after-resume`.

## Pinned ITT build

The old `build-unitrace` has `BUILD_WITH_ITT=0` and rejects
`--chrome-itt-logging`. Use `/home/steve/src/pti-gpu/build-unitrace-itt/`:
same PTI source `a5bab309f4ffdd78bd127035c46f5f75371160f8`, same options plus
`BUILD_WITH_ITT=1`. Preregistration pins both files:

- `unitrace`: `def24ca596afcb8bca952bb47cf5b1a35496656ab906a8aa531cdb26c1f6c2c7`
- `libunitrace_tool.so`: `114242e35621656bca60d3fa44d447ac0b1ba75f18505dc341b0a6772381da68`

`ldd` on both files found no further DSO from that build directory; the receipt
is `data/2026-10-17-flash-next-a367-census-reseal/tracer-identity.json`.
No tracer target, including `/bin/true`, is a CPU-only test: collector startup
calls device initialization. Only static inspection and `--plan` ran here.

## Window, storage and exit contract

Wrap only the server. Keep `--start-paused --session <unique>` plus
`--chrome-kernel-logging --chrome-itt-logging --verbose --pid` and
`--chrome-event-buffer-size 4096`. The source-pinned V2 capture-entry hook publishes four
`capture-ready-rank-R.json` files (rank/PID/monotonic) in local ext4 scratch,
after profiling and KV initialization. Each worker waits for `capture-go`,
printing and continuing after each 600-second wait budget; no exception or
kill. The supervisor resumes exactly once after all four distinct rank/PID
receipts, records acknowledgement, then writes go even if resume fails.
No loading-log resume remains. Failure invalidates graph attribution without
skipping requests or normal teardown. Cleanup also releases waiters.

Eager-census skips capture entirely. That secondary arm uses a census-only
`Worker.compile_or_warm_up_model` wrapper after the original returns, before
readiness, preserving its return value. It uses the same file handshake after
profiling/KV/warmup; it is never graph evidence. Graph-census alone is next.

Stay active through capture, readiness, 20-second plateau, 30-second sleep and
requests. Enable request ITT scopes just for the client; pause right after it
finishes, before normal shutdown destroys groups. Unexpected crashes and safety
trips can precede that normal pause; pausing does not unload the tracing layer.

Result directory: `/home/steve/.cache/a367-trace/<run-name>/`, local ext4,
outside scratch. Require 8 GiB free, soft-stop at 6 GiB of local trace files.
Local trace originals survive scratch cleanup. The coordinator copies them to
RAID after the full lifecycle, verifies every copied hash and runs analysis.
The timed sampler only stores rows in memory and queues them; a separate writer
appends to local scratch. After lifecycle its complete file must equal the rows,
then it is copied to output/samples.jsonl and hashed before scratch deletion.
Live-file checks are on a separate thread, never on the memory sampler.

Do not require server return code zero for traced runs. Record a nonzero exit
or segfault as `expected_tracer_exit_crash` with the microtest evidence path.
Require all session owners gone, completed requests, zero GPU fault lines
through the full 305-second watch, and complete four-rank ITT verify/kernel
evidence. No kill/escalation, restart or retry. Teardown overrun remains a failed
receipt and waits for owner recovery. `census_valid` is the final offline gate;
startup kernels outside request markers may leave whole-trace segmentation
incomplete without invalidating fully correlated request scopes.

The parser has been checked against a copy of the actual `graph-traced` Chrome
file: `PyTorch::...` ITT cpu_op X spans, H2D flow IDs and timestamped gpu_op
kernels. The 9,810-byte fixture preserves original event objects and indices;
the full 4,127,634-byte source hash and fixture provenance are in `fixtures/`.
The full file yielded 100 ITT iterations, eight flow-correlated kernels each,
zero unresolved sources. No GPU timestamp overlap is used to infer ownership.

## Step attribution contract

Host wall spans do **not** bound asynchronous GPU work. A forward can return
before its kernels execute; grouping GPU events by overlap with Python spans
would silently misattribute later work.

The defensible route uses optional host-only ITT spans around the actual target
forward/replay and draft invocation, recording rank, step sequence, phase and
actual M for model scopes or request batch B for the whole proposer scope,
from tensor **metadata only**. No tensor value read, synchronize,
operation replacement or arithmetic change is permitted. Under graph mode the
marker must surround the graph wrapper's replay call: the Python model forward
is not entered for each replay. The eager model/MTP forward wrappers alone are
insufficient to mark graph replays.

`trace_marks.py` implements these source-pinned runtime wrappers and
`census_entry.py` reuses the protected driver's spawn-safe cleanup bootstrap.
Request marker hooks remain inert until the supervisor creates `A367_CENSUS_MARKER_ACTIVE`; the startup capture rendezvous is independent of that request-only gate.
The ITT binding is `torch._C._itt`, not a profiler activation. Missing ITT,
unknown active graph runnable, unavailable rank or unreadable row metadata
fails closed. M=2 is labeled verify only when existing GDN host metadata proves
one speculative decode, two speculative tokens and no prefill; a short prefill
is labeled target. The draft proposer scope includes its staging, all model
calls and sampling; it is not a draft-model-only scope. Its `next_token_ids`
shape is request batch B, not model M: source
`vllm/v1/spec_decode/llm_base_proposer.py:522-524,557-583` derives the model
token count and padding later. Unknown runnable wrappers fail closed even if
they carry an attribute pointing to a recognized target model.
Nested forward scopes are suppressed. Twelve source dependencies are hash-pinned
in that module and checked in every spawned process. CPU tests validate wrapper
behavior with fake objects; actual marker emission remains a live-run check.

Marker labels are `A367|verify|M=2|seq=N`, `A367|draft|B=1|seq=N` for the
whole proposer, `A367|draft|M=<actual>|seq=N` for a standalone draft model
scope, or target labels for other shapes/contexts. B must never be reported as
model M. PTI prefixes ITT task labels with the domain
(`itt_collector.h:366-385`), e.g. `PyTorch::A367|verify|M=2|seq=N`. First active
scope writes `marker-rank-R-pid-P.json` with schema
`a367-census-marker-rank-v1`, rank, OS PID and the checked source pins.

PTI `tools/unitrace/src/chromelogger.h:809-845` emits `gpu_op` complete events
with `args.id` and `Flow_H2D_*` flow IDs; `:1810-1838` emits the matching host
flow source on the submission thread. The analysis must associate the host
flow source with its same-thread, rank-bound marker, then join by flow/kernel
ID to the device event. The GPU event may begin after the host marker ends.
Match worker OS PID from the per-process trace path to rank evidence: Chrome's
synthetic device `pid` is **not** the worker OS PID. Preserve the raw files.

Reject duplicate IDs, absent or conflicting marker membership, cross-rank ID
joins, incomplete steps and impossible durations from complete-step summaries.
Report their counts and reasons as unattributed evidence. Never infer M=2 from
an assumed 400-kernel count or classify draft merely from timeline gaps. A
sequence-only detector can be a labeled heuristic, not an exact census. Child
submission threads outside the marker scope likewise remain unattributed unless
an explicit tested correlation connects them. No per-step census is valid if
this coverage is inadequate. Tests should include a kernel executing after its
host scope, reused IDs in different process files, missing flows, nested spans
and ambiguous membership.

For each valid step report kernel count, sum of kernel durations, first-start
to last-end wall span, **union** of busy intervals and gaps in that union. The
sum can exceed span with overlapping streams; do not calculate idle as
span-minus-sum. Include all observed families and keep unknown names explicit.
Use the dispatch audit in
`notes/2026-10-16-flash-next-m2-glue-fusion-design.md` as the exact-preserving
boundary authority: no absent permutation kernels, no already-fused routed
SiLU/quant counted twice, preserve expert-map sentinels/order, BF16 materialized
rounding, stable QSA order, two one-row collectives, and state/rollback ordering.

## Planned size and host-memory risk

These are **unmeasured planning estimates**, originally request-only. The expanded active window includes startup/capture; the old 0.2–2 GiB range is not a bound:

- For roughly 60-100 verify steps, four ranks and up to roughly 1,000 target,
  draft, copy and supporting launches per cycle/rank, expect about 240,000-
  400,000 kernel events. Multiple flow/API records and long demangled names can
  bring output to roughly **0.2-2 GiB**. At the hard 2 x 128-token workload cap,
  a rejected draft on every step permits more cycles; the upper estimate must
  not be treated as an event or file-size guarantee.
- Reserve **1 GiB additional tracer host memory** as a planning allowance,
  with a plausible **0.25-1 GiB** working range. Neither is measured or a safe
  upper bound. PTI's default buffer is unlimited and initially allocates
  1,048,576 host/device records per tracing thread
  (`chromelogger.h:607-638`). The finite 4,096-event option bounds each ring's
  record slots and flushes when full (`:740-753`), but does not bound kernel
  maps, event pools, helper processes, strings or driver allocations.
- The replay generation need was **104,784,640 KiB**. At the measured replay start state, the
  minimum available memory remained approximately **1.9 GB above the reserve**.
  Adding a 1 GiB tracer allowance would reduce that remaining headroom to
  approximately **0.8 GB**, not create additional capacity. The approved
  start-floor exception does not increase available physical memory and does
  not waive existing live trips.
- Keep the whole planned write envelope below **10 GiB**, with raw traces
  budgeted at **2 GiB** plus logs, manifests and analysis. Monitor actual write
  growth through an independent disk watchdog (6 GiB local-trace soft stop, below the
  10 GiB planned budget); abort rather than
  truncate raw traces into a misleading complete census. Bound each parser
  input and process ranks one at a time after server teardown so Python JSON
  expansion is not concurrent with model/tracer memory.

For scale only, the retained DeepSeek host-only cross-check has four worker
Chrome files of 2,435,279 / 2,451,004 / 2,433,656 / 2,431,181 bytes for 24
intervals. Those ~9.75 MB do not measure device-trace memory or predict this
model's trace size. The estimates above require verification in an admitted run.
