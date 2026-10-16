# A367 diagnostic census: tracing feasibility

CPU review, 2026-10-16. No GPU process, model import, device probe or tracer
experiment was run for this review. These are feasibility findings and planning
estimates, not a measured census or a speed claim.

## Verdict and prior evidence

Per-kernel timestamps inside A367 `FULL_DECODE_ONLY` replay are **unproven on
this stack**. It would be incorrect to describe unitrace as categorically graph
blind: its current checked-in source contains graph capture/replay hooks. It
would also be incorrect to call a full-model eager census known-safe. The same
tracer has failed on four-rank collective workloads in both cases.

The selected executable is
`/home/steve/src/pti-gpu/build-unitrace/unitrace`, SHA256
`5aaca1f418a212a1d298cac27afb6c471bf1fcf47a1622e0c20d1a2cf43fc85a`.
PTI source HEAD is `a5bab309f4ffdd78bd127035c46f5f75371160f8`; the only
untracked source-tree entry observed was `build-unitrace/`. This binary identity
matches the prior-lane pin. A source capability is not proof that the retained
binary and deployed driver exercise it successfully.

Repository evidence:

- `experiments/laguna-s-2.1-xpu-b70/notes/2026-07-24-m8-replay-trace-retry-terminal-pti-failure.md`,
  Result and Disposition: eager initialization completed, then the first request
  with `--host-timing --device-timing --kernel-submission` exceeded the five-minute
  RPC timeout and repeatedly reported `Unable to query event for timestamps`.
  No complete output existed and **the graph arm never ran**. Do not repeat that
  unchanged instrumentation combination.
- `experiments/laguna-s-2.1-xpu-b70/notes/2026-08-05-KEY-the-serving-path-is-half-the-decode-step.md:244-282`:
  a start-paused device/submission trace stalled oneCCL initialization for
  15 minutes, before readiness or resume, and produced only 292 bytes. The
  first-replay resume hook was reached in a separate acknowledgement-mismatch
  attempt. Paused collection is therefore not zero-cost instrumentation.
- `experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-20-nospec-unitrace-attribution-crosscheck.md`,
  Tracer and bounded fallback: device timestamp mode serialized progress and
  killed a worker after about 43 steps. Host-only tracing succeeded, but did
  **not** produce a device decomposition. The configured graph path was
  PIECEWISE, not the A367 full-decode path.
- `notes/2026-08-10-vdr2-unitrace-profile.md`: filtered device timing did expose
  921 complete decode cycles on another runtime, but the controller missed an
  exact progress marker, and tracer teardown failed. This supports bounded,
  relative collection windows and strict lifecycle reporting, not transfer of
  that lane's graph visibility or timings to A367.
- `option4-decoder/tools/summarize_unitrace.py` counts host Level Zero submit
  boundaries from Chrome events. A single graph-submit event demonstrates
  submission compression, not visibility into its device kernels.

Local PTI source evidence (read-only):
`tools/unitrace/src/levelzero/ze_collector.h:4528-4537` has
`ShouldCaptureAppend`, which retains graph-capture commands even while paused;
`:5821-5855` handles `zeCommandListImmediateAppendCommandListsExp`. These hooks
make a conditional graph-trace feasibility arm reasonable, but do not erase the
full-model failures above.

## Preregistered arms and limits

Each arm requires its own explicit admission and fresh lifecycle. There is no
automatic retry or eager fallback after a failure.

1. **Graph reference:** certified `FULL_DECODE_ONLY`, no tracing. The fixed short
   requests provide diagnostic wall timing and output-token comparison only.
2. **Conditional graph trace:** unchanged graph/arithmetic path, bounded paused
   unitrace collection during the same request window. Success requires four
   rank-bound traces, actual device kernel timestamps, and defensible step
   correlation. Empty or submit-only traces mean visibility is unresolved; do
   not fabricate a graph census from them.
3. **Conditional eager census:** graph disabled, the same arithmetic selectors,
   model and client. Device timestamps are explicitly **eager**, not a graph
   performance decomposition. This also remains a feasibility experiment in
   light of the eager Laguna failure. Output differences are findings.

The machine-control implementation and which arms are executable are defined
by `preregistration.json` and the supervisor. Do not silently substitute a
host-only trace for the requested device census. Do not enable torch.profiler,
GPU events, CCL profiling, hardware metric sampling, or xpu-smi.

## Window control and output

The Laguna reference is
`experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_m8_replay_trace.sh` and
`profile_laguna_m8_replay_trace.py`. Wrap only the server executable, not the
lifecycle supervisor. Pass `--start-paused --session A367Census<alphanumeric>`;
resume with `unitrace --resume <session>` after readiness, plateau and the
30-second sleep; pause in a finally block after the last census request. Local
`tools/unitrace/README.md:894-928` specifies that these controls affect every
child process in the named session. Record return codes and acknowledgements.
A control child may add an `[INFO] Log is stored in ...` line; do not require
that stderr consists of a single acknowledgement line. The VDR2 note also
shows why an exact progress-log value is an unsafe stop trigger.

Use `--chrome-kernel-logging --chrome-itt-logging --verbose --pid` with finite
`--chrome-event-buffer-size 4096` and `--result-dir` under the RAID run path.
Kernel logging includes host/device flow correlation; device-only logging does
not provide enough host correlation for reliable asynchronous step ownership.
Do not add the historically failing host-timing/kernel-submission combination.
Local README lines 486-530 describe per-process `chrome_trace.json` output;
all artifacts and helper control logs must stay under the run directory.

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
Hooks remain inert until the supervisor creates `A367_CENSUS_MARKER_ACTIVE`.
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
Nested forward scopes are suppressed. Eight source dependencies are hash-pinned
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

These are deliberately conservative **unmeasured planning estimates**:

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
  growth through an independent disk watchdog (8 GiB soft stop, below the
  10 GiB planned budget); abort rather than
  truncate raw traces into a misleading complete census. Bound each parser
  input and process ranks one at a time after server teardown so Python JSON
  expansion is not concurrent with model/tracer memory.

For scale only, the retained DeepSeek host-only cross-check has four worker
Chrome files of 2,435,279 / 2,451,004 / 2,433,656 / 2,431,181 bytes for 24
intervals. Those ~9.75 MB do not measure device-trace memory or predict this
model's trace size. The estimates above require verification in an admitted run.
